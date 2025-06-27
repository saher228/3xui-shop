import logging
import uuid
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.types import User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import User

logger = logging.getLogger(__name__)


class DBSessionMiddleware(BaseMiddleware):
    def __init__(self, session: async_sessionmaker) -> None:
        self.session = session
        logger.debug("Database Session Middleware initialized.")

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session: AsyncSession
        async with self.session() as session:
            tg_user: TelegramUser | None = data.get("event_from_user")

            if tg_user and not tg_user.is_bot:
                user = await User.get(session=session, tg_id=tg_user.id)
                is_new_user = False

                if not user:
                    is_new_user = True
                    user = await User.create(
                        session=session,
                        tg_id=tg_user.id,
                        vpn_id=str(uuid.uuid4()),
                        first_name=tg_user.first_name,
                        username=tg_user.username,
                        language_code=tg_user.language_code or "ru",
                    )
                    logger.info(f"New user {user.tg_id} created.")
                elif user.language_code != "ru":
                    await User.update_language_code(session, user.tg_id, "ru")
                    user.language_code = "ru"
                    logger.debug(f"Updated language code to 'ru' for user {user.tg_id}")

                data["user"] = user
                data["is_new_user"] = is_new_user
            
            data["session"] = session
            data["session_maker"] = self.session

            return await handler(event, data)
