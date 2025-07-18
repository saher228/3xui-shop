import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.is_dev import IsDev
from app.bot.models import ServicesContainer, SubscriptionData
from app.bot.payment_gateways import GatewayFactory
from app.bot.utils.constants import TransactionStatus
from app.bot.utils.formatting import format_subscription_period
from app.bot.utils.navigation import NavSubscription
from app.db.models import Transaction, User

from .keyboard import pay_keyboard

logger = logging.getLogger(__name__)
router = Router(name=__name__)


class PaymentState(StatesGroup):
    processing = State()


@router.callback_query(SubscriptionData.filter(F.state.startswith(NavSubscription.PAY)))
async def callback_payment_method_selected(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    services: ServicesContainer,
    bot: Bot,
    gateway_factory: GatewayFactory,
    state: FSMContext,
) -> None:
    if await state.get_state() == PaymentState.processing:
        logger.debug(f"User {user.tg_id} is already processing payment.")
        return

    await state.set_state(PaymentState.processing)

    try:
        method = callback_data.state
        devices = callback_data.devices
        duration = callback_data.duration
        logger.info(f"User {user.tg_id} selected payment method: {method}")
        logger.info(f"User {user.tg_id} selected {devices} devices and {duration} days. CB price: {callback_data.price}, is_change: {callback_data.is_change}")
        gateway = gateway_factory.get_gateway(method)
        
        final_price_for_payment: float
        if callback_data.is_change and callback_data.price is not None and callback_data.price > 0:
            final_price_for_payment = callback_data.price
            logger.info(f"User {user.tg_id} [Change Flow]: Using pre-calculated (prorated) price from callback_data: {final_price_for_payment:.2f}")
        else:
            plan = services.plan.get_plan(devices)
            if not plan:
                logger.error(f"User {user.tg_id}: Plan not found for {devices} devices when creating payment link.")
                await services.notification.show_popup(callback=callback, text=_("payment:popup:error"))
                await state.set_state(None)
                return
            standard_price = plan.get_price(currency=gateway.currency, duration=duration)
            if standard_price is None:
                logger.error(f"User {user.tg_id}: Could not get price for plan {devices}d/{duration}days, currency {gateway.currency.code}")
                await services.notification.show_popup(callback=callback, text=_("payment:popup:error"))
                await state.set_state(None)
                return
            final_price_for_payment = standard_price
            callback_data.price = final_price_for_payment 
            logger.info(f"User {user.tg_id} [Non-Change or 0 Prorated]: Using standard price: {final_price_for_payment:.2f}")

        if final_price_for_payment <= 0 and not (gateway.name == "Telegram Stars" and final_price_for_payment == 0):
             logger.warning(f"User {user.tg_id}: Final price for payment is {final_price_for_payment}. No payment link will be generated if not Telegram Stars.")

        pay_url = await gateway.create_payment(callback_data)

        if callback_data.is_extend:
            text = _("payment:message:order_extend")
        elif callback_data.is_change:
            text = _("payment:message:order_change")
        else:
            text = _("payment:message:order")

        message = await callback.message.edit_text(
            text=text.format(
                devices=devices,
                duration=format_subscription_period(duration),
                price=final_price_for_payment,
                currency=gateway.currency.symbol,
            ),
            reply_markup=pay_keyboard(pay_url=pay_url, callback_data=callback_data),
        )
        await state.update_data(payment_message_id=message.message_id)
    except Exception as exception:
        logger.error(f"Error processing payment: {exception}")
        await services.notification.show_popup(callback=callback, text=_("payment:popup:error"))
    finally:
        await state.set_state(None)


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery, user: User) -> None:
    logger.info(f"Pre-checkout query received from user {user.tg_id}")
    if pre_checkout_query.invoice_payload:
        await pre_checkout_query.answer(ok=True)
    else:
        await pre_checkout_query.answer(ok=False)


@router.message(F.successful_payment)
async def successful_payment(
    message: Message,
    user: User,
    session: AsyncSession,
    bot: Bot,
    gateway_factory: GatewayFactory,
) -> None:
    if await IsDev()(user_id=user.tg_id):
        await bot.refund_star_payment(
            user_id=user.tg_id,
            telegram_payment_charge_id=message.successful_payment.telegram_payment_charge_id,
        )

    data = SubscriptionData.unpack(message.successful_payment.invoice_payload)
    transaction = await Transaction.create(
        session=session,
        tg_id=user.tg_id,
        subscription=data.pack(),
        payment_id=message.successful_payment.telegram_payment_charge_id,
        status=TransactionStatus.COMPLETED,
    )

    gateway = gateway_factory.get_gateway(NavSubscription.PAY_TELEGRAM_STARS)
    await gateway.handle_payment_succeeded(payment_id=transaction.payment_id)
