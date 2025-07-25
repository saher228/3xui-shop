from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.bot.services import VPNService

import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.config import Config
from app.db.models import Referral, User

logger = logging.getLogger(__name__)


class SubscriptionService:
    def __init__(
        self,
        config: Config,
        session_factory: async_sessionmaker,
        vpn_service: VPNService,
    ) -> None:
        self.config = config
        self.session_factory = session_factory
        self.vpn_service = vpn_service
        logger.info("Subscription Service initialized")

    async def is_trial_available(self, user: User) -> bool:
        if not self.config.shop.TRIAL_ENABLED or user.is_trial_used:
            return False

        client = await self.vpn_service.is_client_exists(user)
        if client:
            return False

        async with self.session_factory() as session:
            referral = await Referral.get_referral(session, user.tg_id)

        return not referral or (referral and not self.config.shop.REFERRED_TRIAL_ENABLED)

    async def gift_trial(self, user: User, session: AsyncSession) -> User | None:
        if not await self.is_trial_available(user=user):
            logger.warning(
                f"Failed to activate trial for user {user.tg_id}. Trial period is not available."
            )
            return None

        trial_used = await User.update_trial_status(
            session=session, tg_id=user.tg_id, used=True
        )
        if not trial_used:
            logger.critical(f"Failed to update trial status for user {user.tg_id}.")
            return None

        user.is_trial_used = True
        
        logger.info(f"Begun giving trial period for user {user.tg_id}.")
        updated_user = await self.vpn_service.process_bonus_days(
            user,
            duration=self.config.shop.TRIAL_PERIOD,
            devices=self.config.shop.BONUS_DEVICES_COUNT,
            session=session,
        )

        if updated_user:
            logger.info(
                f"Successfully gave {self.config.shop.TRIAL_PERIOD} days to a user {user.tg_id}"
            )
            return updated_user

        await User.update_trial_status(session=session, tg_id=user.tg_id, used=False)

        logger.warning(f"Failed to apply trial period for user {user.tg_id} due to failure.")
        return None
