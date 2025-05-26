import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.models import ClientData, ServicesContainer, SubscriptionData
from app.bot.payment_gateways import GatewayFactory
from app.bot.utils.navigation import NavSubscription
from app.config import Config
from app.db.models import User

from .keyboard import (
    devices_keyboard,
    duration_keyboard,
    location_keyboard,
    payment_method_keyboard,
    subscription_keyboard,
)

logger = logging.getLogger(__name__)
router = Router(name=__name__)


async def show_subscription(
    callback: CallbackQuery,
    client_data: ClientData | None,
    callback_data: SubscriptionData,
) -> None:
    if client_data:

        if client_data.has_subscription_expired:
            text = _("subscription:message:expired")
        else:
            text = _("subscription:message:active").format(
                devices=client_data.max_devices,
                expiry_time=client_data.expiry_time,
            )
    else:
        text = _("subscription:message:not_active")

    await callback.message.edit_text(
        text=text,
        reply_markup=subscription_keyboard(
            has_subscription=client_data,
            callback_data=callback_data,
        ),
    )


@router.callback_query(F.data == NavSubscription.MAIN)
async def callback_subscription_entry(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} triggered main subscription menu entry (NavSubscription.MAIN string).")
    await state.set_state(None)

    client_data = None
    if user.server_id:
        client_data = await services.vpn.get_client_data(user)
        if not client_data:
            await services.notification.show_popup(
                callback=callback,
                text=_("subscription:popup:error_fetching_data"),
            )
            return

    fresh_callback_data = SubscriptionData(
        state=NavSubscription.MAIN, 
        user_id=user.tg_id,
        devices=0,
        location="",
        duration=0,
        is_change=False,
        is_extend=False
    )
    await show_subscription(callback=callback, client_data=client_data, callback_data=fresh_callback_data)


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.MAIN))
async def callback_subscription_main_menu(
    callback: CallbackQuery,
    user: User, 
    state: FSMContext,
    callback_data: SubscriptionData, 
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} returned to subscription main menu. Callback: {callback_data.model_dump_json(exclude_none=True)}")
    await state.set_state(None)

    client_data = None
    if user.server_id:
        client_data = await services.vpn.get_client_data(user)

    callback_data_for_menu = callback_data.model_copy(deep=True)
    callback_data_for_menu.state = NavSubscription.MAIN 
    callback_data_for_menu.devices = 0
    callback_data_for_menu.location = ""
    callback_data_for_menu.duration = 0
    callback_data_for_menu.is_change = False 
    callback_data_for_menu.is_extend = False

    await show_subscription(callback=callback, client_data=client_data, callback_data=callback_data_for_menu)


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.EXTEND))
async def callback_subscription_extend(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    config: Config,
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} started extend subscription.")
    client = await services.vpn.is_client_exists(user)

    current_devices = await services.vpn.get_limit_ip(user=user, client=client)
    if not services.plan.get_plan(current_devices):
        await services.notification.show_popup(
            callback=callback,
            text=_("subscription:popup:error_fetching_plan"),
        )
        return

    callback_data.devices = current_devices
    callback_data.state = NavSubscription.DURATION
    callback_data.is_extend = True
    await callback.message.edit_text(
        text=_("subscription:message:duration"),
        reply_markup=duration_keyboard(
            plan_service=services.plan,
            callback_data=callback_data,
            currency=config.shop.CURRENCY,
        ),
    )


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.CHANGE))
async def callback_subscription_change(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} started change subscription.")
    callback_data.state = NavSubscription.DEVICES
    callback_data.is_change = True
    await callback.message.edit_text(
        text=_("subscription:message:devices"),
        reply_markup=devices_keyboard(services.plan.get_all_plans(), callback_data),
    )


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.PROCESS))
async def callback_subscription_process(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} started subscription process. Callback: {callback_data.model_dump_json(exclude_none=True)}")

    to_devices_cb = callback_data.model_copy(deep=True)
    to_devices_cb.state = NavSubscription.DEVICES
    to_devices_cb.devices = 0
    to_devices_cb.location = ""
    to_devices_cb.duration = 0
    
    await callback.message.edit_text(
        text=_("subscription:message:devices"),
        reply_markup=devices_keyboard(services.plan.get_all_plans(), to_devices_cb),
    )


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.DEVICES))
async def callback_devices_selected(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} in devices/location stage. Callback: {callback_data.model_dump_json(exclude_none=True)}")

    if callback_data.devices == 0:
        logger.info(f"User {user.tg_id} needs to select devices. Showing devices keyboard.")
        current_cb_for_devices_display = callback_data.model_copy(deep=True)
        current_cb_for_devices_display.location = ""
        current_cb_for_devices_display.duration = 0
        await callback.message.edit_text(
            text=_("subscription:message:devices"),
            reply_markup=devices_keyboard(services.plan.get_all_plans(), current_cb_for_devices_display),
        )
        return
    
    logger.info(f"User {user.tg_id} selected devices: {callback_data.devices}. Proceeding to location selection.")
    servers = await services.server_pool.get_all_servers()
    if not servers:
        await services.notification.show_popup(callback=callback, text=_("subscription:popup:no_available_servers"), cache_time=120)
        return

    to_location_cb = callback_data.model_copy(deep=True)
    to_location_cb.state = NavSubscription.LOCATION
    to_location_cb.location = ""
    to_location_cb.duration = 0
    await callback.message.edit_text(
        text=_("subscription:message:location"),
        reply_markup=location_keyboard(servers, to_location_cb),
    )


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.LOCATION))
async def callback_location_selected(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    config: Config,
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} in location/duration stage. Callback: {callback_data.model_dump_json(exclude_none=True)}")

    if callback_data.location == "":
        logger.info(f"User {user.tg_id} needs to select location. Showing location keyboard.")
        servers = await services.server_pool.get_all_servers()
        if not servers:
            await services.notification.show_popup(callback=callback, text=_("subscription:popup:no_available_servers"), cache_time=120)
            return
        await callback.message.edit_text(
            text=_("subscription:message:location"),
            reply_markup=location_keyboard(servers, callback_data),
        )
        return

    try:
        location_idx = int(callback_data.location)
    except ValueError:
        logger.error(f"Invalid location index: {callback_data.location} for user {user.tg_id}")
        await services.notification.show_popup(callback=callback, text=_("misc:popup:error_unexpected"), cache_time=5)
        return

    all_servers = await services.server_pool.get_all_servers()
    unique_location_names = sorted(list(set(s.location for s in all_servers if s.location and s.online)))

    if not 0 <= location_idx < len(unique_location_names):
        logger.error(f"Location index {location_idx} out of bounds for user {user.tg_id}")
        await services.notification.show_popup(callback=callback, text=_("misc:popup:error_unexpected"), cache_time=5)
        return
        
    selected_location_name = unique_location_names[location_idx]
    logger.info(f"User {user.tg_id} selected location index: {location_idx}, name: {selected_location_name}")

    available_server = next((s for s in all_servers if s.location == selected_location_name and s.online), None)
            
    if not available_server:
        logger.warning(f"No available server for location: {selected_location_name} for user {user.tg_id}")
        await services.notification.show_popup(callback=callback, text=_("subscription:popup:no_available_servers_location"), cache_time=120)
        return
    
    to_duration_cb = callback_data.model_copy(deep=True)
    to_duration_cb.state = NavSubscription.DURATION
    to_duration_cb.duration = 0
    await callback.message.edit_text(
        text=_("subscription:message:duration"),
        reply_markup=duration_keyboard(
            plan_service=services.plan,
            callback_data=to_duration_cb,
            currency=config.shop.CURRENCY,
        ),
    )


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.DURATION))
async def callback_duration_selected(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    config: Config,
    services: ServicesContainer,
    gateway_factory: GatewayFactory,
) -> None:
    logger.info(f"User {user.tg_id} in duration/payment stage. Callback: {callback_data.model_dump_json(exclude_none=True)}")

    if callback_data.devices == 0 or not callback_data.location:
        logger.warning(f"User {user.tg_id} reached duration stage with incomplete data. Redirecting to device selection.")
        cb_to_devices = callback_data.model_copy(deep=True)
        cb_to_devices.state = NavSubscription.DEVICES
        cb_to_devices.devices = 0
        cb_to_devices.location = ""
        cb_to_devices.duration = 0
        await callback.message.edit_text(text=_("subscription:message:devices"), reply_markup=devices_keyboard(services.plan.get_all_plans(), cb_to_devices))
        return

    if callback_data.duration == 0:
        logger.info(f"User {user.tg_id} needs to select duration. Showing duration keyboard.")
        await callback.message.edit_text(
            text=_("subscription:message:duration"),
            reply_markup=duration_keyboard(
                plan_service=services.plan,
                callback_data=callback_data, 
                currency=config.shop.CURRENCY,
            ),
        )
        return
    
    logger.info(f"User {user.tg_id} selected duration: {callback_data.duration}. Proceeding to payment method selection.")
    to_payment_cb = callback_data.model_copy(deep=True)
    to_payment_cb.state = NavSubscription.PAY
    await callback.message.edit_text(
        text=_("subscription:message:payment_method"),
        reply_markup=payment_method_keyboard(
            plan=services.plan.get_plan(to_payment_cb.devices),
            callback_data=to_payment_cb,
            gateways=gateway_factory.get_gateways(),
        ),
    )
