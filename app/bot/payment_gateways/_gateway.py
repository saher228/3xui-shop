import logging
from abc import ABC, abstractmethod
from typing import Optional

from aiogram import Bot
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.utils.i18n import I18n
from aiogram.utils.i18n import gettext as _
from aiogram.utils.i18n import lazy_gettext as __
from aiohttp.web import Application
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.models import ServicesContainer, SubscriptionData
from app.bot.routers.main_menu.handler import redirect_to_main_menu
from app.bot.utils.constants import (
    DEFAULT_LANGUAGE,
    EVENT_PAYMENT_CANCELED_TAG,
    EVENT_PAYMENT_SUCCEEDED_TAG,
    MESSAGE_EFFECT_IDS,
    Currency,
    TransactionStatus,
)
from app.bot.utils.formatting import format_device_count, format_subscription_period
from app.config import Config
from app.db.models import Transaction, User

logger = logging.getLogger(__name__)

from app.bot.models import SubscriptionData
from app.bot.utils.constants import Currency


class PaymentGateway(ABC):
    name: str
    currency: Currency
    callback: str

    def __init__(
        self,
        app: Application,
        config: Config,
        session: async_sessionmaker,
        storage: RedisStorage,
        bot: Bot,
        i18n: I18n,
        services: ServicesContainer,
    ) -> None:
        self.app = app
        self.config = config
        self.session = session
        self.storage = storage
        self.bot = bot
        self.i18n = i18n
        self.services = services

    @abstractmethod
    async def create_payment(self, data: SubscriptionData) -> str:
        pass

    @abstractmethod
    async def handle_payment_succeeded(self, payment_id: str) -> None:
        pass

    @abstractmethod
    async def handle_payment_canceled(self, payment_id: str) -> None:
        pass

    async def _on_payment_succeeded(self, payment_id: str) -> None:
        logger.info(f"Payment succeeded {payment_id}")

        async with self.session() as session:
            transaction = await Transaction.get_by_id(session=session, payment_id=payment_id)
            if not transaction:
                logger.error(f"Transaction {payment_id} not found.")
                return

            if transaction.status == TransactionStatus.COMPLETED:
                logger.info(f"Transaction {payment_id} already processed. Skipping.")
                return

            subscription_data = SubscriptionData.unpack(transaction.subscription)
            logger.debug(f"Subscription data unpacked: {subscription_data}")

            user = await User.get(session, subscription_data.user_id)
            if not user:
                logger.error(f"User {subscription_data.user_id} not found.")
                return

            transaction.tg_id = user.tg_id
            transaction.status = TransactionStatus.COMPLETED
            await session.commit()
            
            await self.services.notification.notify_developer(
                text=EVENT_PAYMENT_SUCCEEDED_TAG
                + "\n\n"
                + _("payment:event:payment_succeeded").format(
                    payment_id=payment_id,
                    user_id=user.tg_id,
                    devices=format_device_count(subscription_data.devices),
                    duration=format_subscription_period(subscription_data.duration),
                ),
            )

            try:
                await self.services.referral.add_referrers_rewards_on_payment(
                    referred_tg_id=user.tg_id,
                    payment_amount=float(subscription_data.price),
                    payment_id=payment_id,
                )
            except Exception as e:
                logger.warning(f"No referral found for user {user.tg_id} on payment event: {e}")

            location_name = None
            if subscription_data.location:
                location_name = await self.services.server_pool.get_location_name_by_index(
                    subscription_data.location
                )
                logger.info(
                    f"Resolved location index '{subscription_data.location}' to name '{location_name}' "
                    f"for payment {payment_id}, user {user.tg_id}."
                )

            try:
                if subscription_data.is_extend:
                    await self.services.vpn.extend_subscription(
                        user=user,
                        devices=subscription_data.devices,
                        duration=subscription_data.duration,
                    )
                    logger.info(f"Subscription extended for user {user.tg_id}")
                elif subscription_data.is_change:
                    await self.services.vpn.change_subscription(
                        user=user,
                        devices=subscription_data.devices,
                        duration=subscription_data.duration,
                        session=session,
                        location_name=location_name,
                    )
                    logger.info(f"Subscription changed for user {user.tg_id}")
                else:
                    updated_user = await self.services.vpn.create_subscription(
                        user=user,
                        devices=subscription_data.devices,
                        duration=subscription_data.duration,
                        session=session,
                        location_name=location_name,
                    )
                    if updated_user:
                        logger.info(f"Subscription created for user {user.tg_id}")
                    else:
                        logger.error(f"Failed to create subscription for user {user.tg_id}")
                        return

                # Send VPN key to user
                key = await self.services.vpn.get_key(user, session=session)
                if not key:
                    logger.error(f"Failed to get VPN key for user {user.tg_id}")
                    return

                # Send notification about successful payment
                await self.services.notification.notify_by_id(
                    chat_id=user.tg_id,
                    text=_("payment:ntf:payment_success").format(
                        devices=format_device_count(subscription_data.devices),
                        duration=format_subscription_period(subscription_data.duration)
                    ),
                    message_effect_id=MESSAGE_EFFECT_IDS["🎉"],
                )

                # Send VPN key
                await self.services.notification.notify_purchase_success(
                    user_id=user.tg_id,
                    key=key,
                    duration=subscription_data.duration,
                    devices=subscription_data.devices,
                    is_change=subscription_data.is_change,
                    is_extend=subscription_data.is_extend,
                )

                # Try to delete the payment confirmation message
                try:
                    # Get the state from storage
                    state = await self.storage.get_data(chat=user.tg_id)
                    payment_message_id = state.get("payment_message_id")
                    if payment_message_id:
                        await self.bot.delete_message(chat_id=user.tg_id, message_id=payment_message_id)
                except Exception as e:
                    logger.warning(f"Could not delete payment confirmation message for user {user.tg_id}: {e}")

                await redirect_to_main_menu(
                    bot=self.bot,
                    user=user,
                    storage=self.storage,
                    services=self.services,
                    config=self.config,
                )

            except Exception as e:
                logger.error(f"Error processing payment {payment_id} for user {user.tg_id}: {e}")
                raise

    async def _on_payment_canceled(self, payment_id: str) -> None:
        logger.info(f"Payment canceled {payment_id}")
        async with self.session() as session:
            transaction = await Transaction.get_by_id(session=session, payment_id=payment_id)
            if not transaction:
                logger.error(f"Transaction {payment_id} not found.")
                return

            if transaction.status == TransactionStatus.COMPLETED:
                logger.info(f"Transaction {payment_id} is already completed. Ignoring cancellation.")
                return

            data = SubscriptionData.unpack(transaction.subscription)
            if not data:
                logger.error(f"Could not unpack subscription data for transaction {payment_id}")
                return

            await Transaction.update(
                session=session,
                payment_id=payment_id,
                status=TransactionStatus.CANCELED,
            )

            await self.services.notification.notify_developer(
                text=EVENT_PAYMENT_CANCELED_TAG
                + "\n\n"
                + _("payment:event:payment_canceled").format(
                    payment_id=payment_id,
                    user_id=data.user_id,
                    devices=format_device_count(data.devices),
                    duration=format_subscription_period(data.duration),
                ),
            )
