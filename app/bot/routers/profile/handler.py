from __future__ import annotations
import asyncio
import logging
from typing import Optional
import io

import qrcode
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, BufferedInputFile
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.models import ClientData
from app.bot.services import ServicesContainer
from app.bot.utils.constants import PREVIOUS_CALLBACK_KEY
from app.bot.utils.navigation import NavProfile
from app.bot.utils.qrcode import generate_qr_code
from app.db.models import User, Server

from .keyboard import buy_subscription_keyboard, profile_keyboard

logger = logging.getLogger(__name__)
router = Router(name=__name__)


async def prepare_message(
    user: User, 
    client_data: ClientData | None, 
    server_location: Optional[str],
    is_enabled: bool
) -> str:
    profile = _("profile:message:main").format(name=user.first_name, id=user.tg_id)

    if not client_data:
        subscription = _("profile:message:subscription_none")
        return profile + subscription

    status_text = "✅ " + _("status:active") if is_enabled else "❌ " + _("status:disabled")
    location_text = server_location or _("status:location_not_set")

    subscription = _("profile:message:subscription_with_location").format(
    devices=client_data.max_devices,
    location=location_text,
    status=status_text
    )
    
    subscription += (
        _("profile:message:subscription_expiry_time").format(expiry_time=client_data.expiry_time_str)
        if not client_data.has_subscription_expired
        else _("profile:message:subscription_expired")
    )

    statistics = _("profile:message:statistics").format(
        total=client_data.traffic_used,
        up=client_data.traffic_up,
        down=client_data.traffic_down,
    )

    return profile + subscription + statistics


@router.callback_query(F.data == NavProfile.MAIN)
async def callback_profile(
    callback: CallbackQuery,
    user: User,
    services: ServicesContainer,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    user = await User.get(session, user.tg_id)
    logger.info(f"User {user.tg_id} opened profile page.")
    await state.update_data({PREVIOUS_CALLBACK_KEY: NavProfile.MAIN})

    client_data = None
    server_location_str: Optional[str] = None
    is_enabled = False

    if user.server_id:
        server = await Server.get_by_id(session, user.server_id)
        if server:
            server_location_str = server.location
        else:
            logger.warning(f"User {user.tg_id} has server_id {user.server_id} but server not found in DB.")

        client = await services.vpn.is_client_exists(user)
        if client:
            is_enabled = client.enable
            client_data = await services.vpn.get_client_data(user)
            
            if not client_data:
                await services.notification.show_popup(
                    callback=callback,
                    text=_("subscription:popup:error_fetching_data"),
                )
                return

    reply_markup = (
        profile_keyboard()
        if client_data and not client_data.has_subscription_expired
        else buy_subscription_keyboard()
    )

    try:
        await callback.message.edit_text(
            text=await prepare_message(
                user=user, 
                client_data=client_data, 
                server_location=server_location_str,
                is_enabled=is_enabled
            ),
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error updating profile message for user {user.tg_id}: {e}")
        await callback.message.answer(
            text=await prepare_message(
                user=user,
                client_data=client_data,
                server_location=server_location_str,
                is_enabled=is_enabled
            ),
            reply_markup=reply_markup,
        )


@router.callback_query(F.data == NavProfile.SHOW_KEY)
async def callback_show_key(
    callback: CallbackQuery,
    user: User,
    services: ServicesContainer,
    session: AsyncSession,
) -> None:
    logger.info(f"User {user.tg_id} requested their key.")
    await callback.answer()

    key = await services.vpn.get_key(user, session=session)
    if not key:
        await services.notification.show_popup(
            callback=callback,
            text=_("subscription:popup:error_generating_key"),
        )
        return

    qr_image_bytes = generate_qr_code(key)
    qr_code_file = BufferedInputFile(qr_image_bytes.read(), filename="qr_code.png")
    
    caption = _("profile:message:key_vless").format(key=key)

    sent_message = await callback.message.answer_photo(
        photo=qr_code_file,
        caption=caption,
        parse_mode="HTML"
    )

    await asyncio.sleep(10)
    try:
        await sent_message.delete()
    except Exception as e:
        logger.warning(f"Could not delete key message for user {user.tg_id}: {e}")
