import logging
import asyncio
import io

import qrcode
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, BufferedInputFile
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.models import ServicesContainer
from app.bot.routers.subscription.keyboard import trial_success_keyboard
from app.bot.utils.constants import MAIN_MESSAGE_ID_KEY, PREVIOUS_CALLBACK_KEY
from app.bot.utils.formatting import format_subscription_period
from app.bot.utils.navigation import NavMain, NavSubscription
from app.config import Config
from app.db.models import User

logger = logging.getLogger(__name__)
router = Router(name=__name__)


@router.callback_query(F.data == NavSubscription.GET_TRIAL)
async def callback_get_trial(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    services: ServicesContainer,
    config: Config,
    session: AsyncSession,
) -> None:
    logger.info(f"User {user.tg_id} triggered getting non-referral trial period.")
    await state.update_data({PREVIOUS_CALLBACK_KEY: NavMain.MAIN_MENU})

    is_trial_available = await services.subscription.is_trial_available(user=user)
    if not is_trial_available:
        await services.notification.show_popup(
            callback=callback, text=_("subscription:popup:trial_unavailable_for_user")
        )
        return

    trial_period = config.shop.TRIAL_PERIOD
    updated_user = await services.subscription.gift_trial(user=user, session=session)

    main_message_id = await state.get_value(MAIN_MESSAGE_ID_KEY)
    if updated_user:
        await callback.bot.edit_message_text(
            text=_("subscription:ntf:trial_activate_success").format(
                duration=format_subscription_period(trial_period),
            ),
            chat_id=callback.message.chat.id,
            message_id=main_message_id,
            reply_markup=trial_success_keyboard(),
        )
        
        key = await services.vpn.get_key(updated_user, session=session)
        if key:
            qr_image = qrcode.make(key)
            img_byte_arr = io.BytesIO()
            qr_image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            qr_code_file = BufferedInputFile(img_byte_arr.read(), filename="qr_code.png")
            
            key_text = _("profile:message:key")
            message = await callback.message.answer_photo(
                photo=qr_code_file,
                caption=key_text.format(key=key, seconds_text=_("10 seconds")),
            )

            for seconds in range(9, 0, -1):
                seconds_text = _("1 second", "{} seconds", seconds).format(seconds)
                await asyncio.sleep(1)
                try:
                    await message.edit_caption(caption=key_text.format(key=key, seconds_text=seconds_text))
                except Exception as e:
                    logger.debug(f"Failed to edit caption, probably message was deleted by user. {e}")
                    break
            
            try:
                await message.delete()
            except Exception as e:
                logger.debug(f"Failed to delete message, probably already deleted. {e}")
    else:
        text = _("subscription:popup:trial_activate_failed")
        await services.notification.show_popup(callback=callback, text=text)
