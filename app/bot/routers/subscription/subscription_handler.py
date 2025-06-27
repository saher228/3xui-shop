import logging
from typing import Optional
import time

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.i18n import gettext as _
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.models import ClientData, ServicesContainer, SubscriptionData
from app.bot.payment_gateways import GatewayFactory
from app.bot.utils.navigation import NavSubscription
from app.bot.utils.constants import Currency
from app.config import Config
from app.db.models import User, Server, Promocode
from app.bot.states.subscription_states import SubscriptionStates

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
    callback: CallbackQuery | types.Message,
    client_data: ClientData | None,
    callback_data: SubscriptionData,
    server_location: Optional[str],
) -> None:
    text: str
    if client_data:
        if not client_data.has_subscription_expired:
            if server_location:
                text = _("subscription:message:active_with_location").format(
                    devices=client_data.max_devices,
                    expiry_time=client_data.expiry_time_str,
                    location=server_location
                )
            else:
                text = _("subscription:message:active").format(
                    devices=client_data.max_devices,
                    expiry_time=client_data.expiry_time_str,
                )
        else:
            text = _("subscription:message:expired")
    else:
        text = _("subscription:message:not_active")

    markup = subscription_keyboard(
            has_subscription=bool(client_data and not client_data.has_subscription_expired),
            callback_data=callback_data,
    )

    if isinstance(callback, CallbackQuery):
        await callback.message.edit_text(text=text, reply_markup=markup)
    else:
        await callback.answer(text=text, reply_markup=markup)


@router.callback_query(F.data == NavSubscription.MAIN)
async def callback_subscription_entry(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    services: ServicesContainer,
    session: AsyncSession,
) -> None:
    logger.info(f"User {user.tg_id} triggered main subscription menu entry (NavSubscription.MAIN string).")
    await state.set_state(None)

    client_data = None
    server_location: Optional[str] = None
    if user.server_id:
        server = await Server.get_by_id(session, user.server_id)
        if server:
            server_location = server.location
        
        client_data = await services.vpn.get_client_data(user, session=session)
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
    await show_subscription(callback=callback, client_data=client_data, callback_data=fresh_callback_data, server_location=server_location)


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.MAIN))
async def callback_subscription_main_menu(
    callback: CallbackQuery,
    user: User, 
    state: FSMContext,
    callback_data: SubscriptionData, 
    services: ServicesContainer,
    session: AsyncSession,
) -> None:
    logger.info(f"User {user.tg_id} returned to subscription main menu. Callback: {callback_data.model_dump_json(exclude_none=True)}")
    await state.set_state(None)

    client_data = None
    server_location: Optional[str] = None
    if user.server_id:
        server = await Server.get_by_id(session, user.server_id)
        if server:
            server_location = server.location
        client_data = await services.vpn.get_client_data(user, session=session)

    callback_data_for_menu = callback_data.model_copy(deep=True)
    callback_data_for_menu.state = NavSubscription.MAIN 
    callback_data_for_menu.devices = 0
    callback_data_for_menu.location = ""
    callback_data_for_menu.duration = 0
    callback_data_for_menu.is_change = False 
    callback_data_for_menu.is_extend = False

    await show_subscription(callback=callback, client_data=client_data, callback_data=callback_data_for_menu, server_location=server_location)


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.EXTEND))
async def callback_subscription_extend(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    config: Config,
    services: ServicesContainer,
    session: AsyncSession,
) -> None:
    logger.info(f"User {user.tg_id} started extend subscription.")
    client = await services.vpn.is_client_exists(user, session=session)

    current_devices = 0
    current_location_name: Optional[str] = None
    if user.server_id and client:
        current_devices = await services.vpn.get_limit_ip(user=user, client=client)
        server = await Server.get_by_id(session, user.server_id)
        if server:
            current_location_name = server.location
            logger.info(f"User {user.tg_id} extending. Current location name set to: {current_location_name}")
        else:
            logger.warning(f"User {user.tg_id} extending, has server_id {user.server_id} but server not found.")
    else:
        logger.warning(f"User {user.tg_id} trying to extend but no server_id or client not found.")
        await services.notification.show_popup(callback, _("subscription:popup:cannot_extend_no_active_sub"))
        cb_to_main = callback_data.model_copy(deep=True)
        cb_to_main.state = NavSubscription.MAIN
        cb_to_main.devices = 0; cb_to_main.location = ""; cb_to_main.duration = 0; cb_to_main.is_change = False; cb_to_main.is_extend = False
        client_data_for_main = await services.vpn.get_client_data(user, session=session) if user.server_id else None
        server_location_for_main: Optional[str] = None
        if user.server_id:
            server_for_main = await Server.get_by_id(session, user.server_id)
            if server_for_main: server_location_for_main = server_for_main.location
        await show_subscription(callback, client_data_for_main, cb_to_main, server_location_for_main)
        return

    if not services.plan.get_plan(current_devices) or current_devices == 0:
        logger.warning(f"User {user.tg_id} trying to extend, but current plan ({current_devices} devices) is invalid or devices are 0.")
        await services.notification.show_popup(
            callback=callback,
            text=_("subscription:popup:error_fetching_plan"),
        )
        cb_to_main = callback_data.model_copy(deep=True); cb_to_main.state = NavSubscription.MAIN; cb_to_main.devices = 0; cb_to_main.location = ""; cb_to_main.duration = 0; cb_to_main.is_change = False; cb_to_main.is_extend = False
        client_data_for_main = await services.vpn.get_client_data(user, session=session) if user.server_id else None
        server_location_for_main: Optional[str] = None
        if user.server_id:
            server_for_main_plan_error = await Server.get_by_id(session, user.server_id)
            if server_for_main_plan_error: server_location_for_main = server_for_main_plan_error.location
        await show_subscription(callback, client_data_for_main, cb_to_main, server_location_for_main)
        return

    location_idx_str = ""
    if current_location_name:
        all_servers = await services.server_pool.get_all_servers()
        online_servers = [s for s in all_servers if s.location and s.online]
        try:
            idx = [s.location for s in online_servers].index(current_location_name)
            location_idx_str = str(idx)
            logger.info(f"User {user.tg_id} extending. Current location '{current_location_name}' has index {location_idx_str} in unique_online_locations.")
        except ValueError:
            logger.warning(f"User {user.tg_id} extending. Current location '{current_location_name}' not found in unique_online_locations. Will use empty string for location_idx_str.")

    callback_data.devices = current_devices
    callback_data.location = location_idx_str
    callback_data.state = NavSubscription.DURATION
    callback_data.is_extend = True
    logger.info(f"User {user.tg_id} extending. Devices: {current_devices}, Location Index: '{callback_data.location}'. Proceeding to duration selection. CB: {callback_data.model_dump_json(exclude_none=True)}")
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
    session: AsyncSession,
    state: FSMContext,
) -> None:
    logger.info(f"User {user.tg_id} started change subscription. Initial cb: {callback_data.model_dump_json(exclude_none=True)}")

    client_exists = await services.vpn.is_client_exists(user, session=session)
    current_devices = 0
    if user.server_id and client_exists:
        try:
            client = client_exists 
            if not client:
                 client = await services.vpn.get_client_by_user_id(user.tg_id)

            if client: 
                current_devices = await services.vpn.get_limit_ip(user=user, client=client)
            else: 
                logger.warning(f"User {user.tg_id} has server_id but client object could not be retrieved for changing subscription.")

        except Exception as e:
            logger.error(f"Error fetching current_devices for user {user.tg_id} during change subscription: {e}")
            pass

    if current_devices == 0:
        logger.warning(f"User {user.tg_id} trying to change subscription but no active subscription or current_devices is 0. User has server_id: {bool(user.server_id)}")
        await services.notification.show_popup(
            callback=callback,
            text=_("subscription:popup:cannot_change_no_active_sub"),
        )
        cb_to_main = callback_data.model_copy(deep=True)
        cb_to_main.state = NavSubscription.MAIN
        cb_to_main.devices = 0; cb_to_main.location = ""; cb_to_main.duration = 0; cb_to_main.is_change = False; cb_to_main.is_extend = False
        
        client_data_for_main = await services.vpn.get_client_data(user, session=session)
        server_location_for_main: Optional[str] = None
        if user.server_id: 
            server = await Server.get_by_id(session, user.server_id)
            if server:
                server_location_for_main = server.location

        await show_subscription(callback=callback, client_data=client_data_for_main, callback_data=cb_to_main, server_location=server_location_for_main)
        return

    await state.update_data(original_devices_for_change=current_devices)

    callback_data.devices = current_devices
    callback_data.is_change = True
    callback_data.state = NavSubscription.DEVICES
    callback_data.devices = 0  
    callback_data.location = "" 
    callback_data.duration = 0 

    logger.info(f"User {user.tg_id} changing subscription (current_devices={current_devices}), proceeding to device selection. Callback: {callback_data.model_dump_json(exclude_none=True)}")
    await callback.message.edit_text(
        text=_("subscription:message:devices"),
        reply_markup=devices_keyboard(
            plans=services.plan.get_all_plans(),
            callback_data=callback_data,
            current_devices=current_devices,
        ),
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
        reply_markup=devices_keyboard(
            plans=services.plan.get_all_plans(),
            callback_data=to_devices_cb,
            current_devices=to_devices_cb.devices,
        ),
    )


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.DEVICES))
async def callback_devices_selected(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    services: ServicesContainer,
    config: Config,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    logger.info(
        f"User {user.tg_id} in devices stage. Callback: {callback_data.model_dump_json(exclude_none=True)}"
    )

    if callback_data.devices == 0:
        logger.info(
            f"User {user.tg_id} needs to select devices. Showing devices keyboard."
        )

        fsm_data = await state.get_data()
        original_devices = fsm_data.get("original_devices_for_change")

        current_cb_for_devices_display = callback_data.model_copy(deep=True)
        current_cb_for_devices_display.duration = 0
        await callback.message.edit_text(
            text=_("subscription:message:devices"),
            reply_markup=devices_keyboard(
                plans=services.plan.get_all_plans(),
                callback_data=current_cb_for_devices_display,
                current_devices=original_devices,
            ),
        )
        return

    logger.info(f"User {user.tg_id} selected {callback_data.devices} devices.")

    if callback_data.is_change:
        logger.info(f"User {user.tg_id} changing subscription. Skipping location selection.")
        
        server = await Server.get_by_id(session, user.server_id)
        if server and server.location:
            all_servers = await services.server_pool.get_all_servers()
            online_servers = [s for s in all_servers if s.location and s.online]
            try:
                idx = [s.location for s in online_servers].index(server.location)
                callback_data.location = str(idx)
                logger.info(f"User {user.tg_id} changing subscription. Set location to index {idx} ({server.location})")
            except ValueError:
                logger.warning(f"User {user.tg_id} changing subscription. Could not find index for current location {server.location}. Using first available.")
                callback_data.location = "0"
        else:
            callback_data.location = "0"
            logger.warning(f"User {user.tg_id} changing subscription. Could not determine current location. Defaulting to index 0.")

        callback_data.state = NavSubscription.DURATION
        await callback.message.edit_text(
            text=_("subscription:message:duration"),
            reply_markup=duration_keyboard(
                plan_service=services.plan,
                callback_data=callback_data,
                currency=config.shop.CURRENCY,
            ),
        )
        return

    all_servers = await services.server_pool.get_all_servers()
    online_servers = [s for s in all_servers if s.location and s.online]
    unique_online_locations = sorted(
        list(set(s.location for s in online_servers))
    )

    if len(unique_online_locations) > 1:
        logger.info(
            f"User {user.tg_id} has multiple locations to choose from. Showing location keyboard."
        )
        callback_data.state = NavSubscription.LOCATION
        await callback.message.edit_text(
            text=_("subscription:message:location"),
            reply_markup=location_keyboard(
                servers=online_servers,
                callback_data=callback_data,
            ),
        )
    else:
        logger.info(
            f"User {user.tg_id} has only one or zero locations available. Skipping location selection."
        )
        callback_data.state = NavSubscription.DURATION
        callback_data.location = "0"
        await callback.message.edit_text(
            text=_("subscription:message:duration"),
            reply_markup=duration_keyboard(
                plan_service=services.plan,
                callback_data=callback_data,
                currency=config.shop.CURRENCY,
            ),
        )


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.LOCATION))
async def callback_location_selected(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    config: Config,
    services: ServicesContainer,
    session: AsyncSession,
) -> None:
    logger.info(f"User {user.tg_id} in location/duration stage. Callback: {callback_data.model_dump_json(exclude_none=True)}")

    if callback_data.location == "":
        logger.info(f"User {user.tg_id} needs to select location. Showing location keyboard.")
        all_servers = await services.server_pool.get_all_servers()
        online_servers = [s for s in all_servers if s.location and s.online]

        if not online_servers:
            await services.notification.show_popup(callback=callback, text=_("subscription:popup:no_available_servers"), cache_time=120)
            return
        await callback.message.edit_text(
            text=_("subscription:message:location"),
            reply_markup=location_keyboard(
                servers=online_servers,
                callback_data=callback_data
            ),
        )
        return

    try:
        location_idx = int(callback_data.location)
    except ValueError:
        logger.error(f"Invalid location index: {callback_data.location} for user {user.tg_id}")
        await services.notification.show_popup(callback=callback, text=_("misc:popup:error_unexpected"), cache_time=5)
        return

    all_servers = await services.server_pool.get_all_servers()
    online_servers = [s for s in all_servers if s.location and s.online]
    unique_location_names = sorted(list(set(s.location for s in online_servers if s.location and s.online)))

    if not 0 <= location_idx < len(unique_location_names):
        logger.error(f"Location index {location_idx} out of bounds for user {user.tg_id}")
        await services.notification.show_popup(callback=callback, text=_("misc:popup:error_unexpected"), cache_time=5)
        return
        
    selected_location_name = unique_location_names[location_idx]
    logger.info(f"User {user.tg_id} selected location index: {location_idx}, name: {selected_location_name}")

    server_to_test_login = next((s for s in online_servers if s.location == selected_location_name and s.online), None)
    
    if server_to_test_login:
        logger.info(f"User {user.tg_id}: Attempting test login to server '{server_to_test_login.name}' (ID: {server_to_test_login.id}) in location '{selected_location_name}'.")
        from py3xui import AsyncApi
        test_api = AsyncApi(
            host=server_to_test_login.host,
            username=config.xui.USERNAME,
            password=config.xui.PASSWORD,
            token=config.xui.TOKEN,
            logger=logging.getLogger(f"xui_test_login_{server_to_test_login.name}"),
        )
        try:
            await test_api.login()
            logger.info(f"User {user.tg_id}: Test login to server '{server_to_test_login.name}' SUCCEEDED.")
        except Exception as e:
            logger.warning(f"User {user.tg_id}: Test login to server '{server_to_test_login.name}' FAILED. Error: {e}. Proceeding with subscription flow.")
    else:
        logger.warning(f"User {user.tg_id}: No online server found in location '{selected_location_name}' to perform a test login. This was checked before, but good to note.")


    available_server = next((s for s in online_servers if s.location == selected_location_name and s.online), None)
            
    if not available_server:
        logger.warning(f"No available server for location: {selected_location_name} for user {user.tg_id}")
        await services.notification.show_popup(callback=callback, text=_("subscription:popup:no_available_servers_location"), cache_time=120)
        return
    
    if callback_data.is_change_location:
        logger.info(f"User {user.tg_id} confirmed location change to {selected_location_name}. Devices: {callback_data.devices}")
        if callback_data.devices == 0:
            logger.error(f"User {user.tg_id} in change_location flow but devices are 0 in callback_data. This should not happen.")
            await services.notification.show_popup(callback, _("misc:popup:error_unexpected"))
            return

        try:
            success = await services.vpn.change_client_location(
                user=user,
                new_location_name=selected_location_name,
                current_devices=callback_data.devices,
                session=session,
            )
            if success:
                await services.notification.show_popup(callback, _("subscription:popup:location_changed_successfully").format(location=selected_location_name))
            else:
                logger.error(f"Error changing location for user {user.tg_id} to {selected_location_name}: Could not change location.")
                await services.notification.show_popup(callback, _("subscription:popup:error_changing_location"))

            cb_to_main = callback_data.model_copy(deep=True)
            cb_to_main.state = NavSubscription.MAIN
            cb_to_main.devices = 0; cb_to_main.location = ""; cb_to_main.duration = 0; cb_to_main.price = 0
            cb_to_main.is_change = False; cb_to_main.is_extend = False; cb_to_main.is_change_location = False

            client_data_after_change = await services.vpn.get_client_data(user, session=session)
            updated_server_location: Optional[str] = None
            if user.server_id:
                current_server = await Server.get_by_id(session, user.server_id)
                if current_server:
                    updated_server_location = current_server.location

            await show_subscription(callback, client_data_after_change, cb_to_main, updated_server_location)
            return

        except Exception as e:
            logger.error(f"Error changing location for user {user.tg_id} to {selected_location_name}: {e}", exc_info=True)
            await services.notification.show_popup(callback, _("subscription:popup:error_changing_location"))

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
    session: AsyncSession,
) -> None:
    logger.info(f"User {user.tg_id} in duration/payment stage. Current Callback: {callback_data.model_dump_json(exclude_none=True)}")

    incomplete_data = False
    if callback_data.is_extend:
        if callback_data.devices == 0:
            incomplete_data = True
            logger.warning(f"User {user.tg_id} [Extend Flow] reached duration stage with devices=0. Redirecting to main subscription menu as device count should be pre-filled.")
            cb_to_main = callback_data.model_copy(deep=True); cb_to_main.state = NavSubscription.MAIN; cb_to_main.devices = 0; cb_to_main.location = ""; cb_to_main.duration = 0; cb_to_main.is_change = False; cb_to_main.is_extend = False
            client_data_for_main = await services.vpn.get_client_data(user, session=session) if user.server_id else None
            await show_subscription(callback, client_data_for_main, cb_to_main, None) 
            return
    elif callback_data.devices == 0 or not callback_data.location:
        incomplete_data = True
        logger.warning(f"User {user.tg_id} [New/Change Flow] reached duration stage with incomplete data (devices: {callback_data.devices}, location: '{callback_data.location}'). Redirecting to device selection.")
        cb_to_devices = callback_data.model_copy(deep=True)
        cb_to_devices.state = NavSubscription.DEVICES
        cb_to_devices.devices = 0
        cb_to_devices.location = ""
        cb_to_devices.duration = 0
        await callback.message.edit_text(text=_("subscription:message:devices"), reply_markup=devices_keyboard(services.plan.get_all_plans(), cb_to_devices))
        return

    prorated_prices_for_keyboard: Optional[dict[int, float]] = None

    if callback_data.is_change:
        logger.info(f"User {user.tg_id} is changing subscription. Attempting to calculate prorated prices.")
        current_client_data = await services.vpn.get_client_data(user, session=session)
        currency_obj = Currency.from_code(config.shop.CURRENCY) 

        if current_client_data and not current_client_data.has_subscription_expired and hasattr(current_client_data, '_expiry_time') and hasattr(current_client_data, '_max_devices'):
            try:
                current_expiry_ms = float(current_client_data._expiry_time) 
                current_devices_raw = int(current_client_data._max_devices)
                
                now_ms = time.time() * 1000
                remaining_ms = current_expiry_ms - now_ms
                
                if remaining_ms > 0 and current_devices_raw > 0:
                    remaining_days = remaining_ms / (1000 * 60 * 60 * 24)
                    logger.info(f"User {user.tg_id}: Current subscription has {remaining_days:.2f} remaining days, {current_devices_raw} devices.")

                    old_plan_ref_duration_days = 30
                    old_plan_obj = services.plan.get_plan(current_devices_raw)
                    
                    if old_plan_obj:
                        old_plan_price_for_ref_duration = old_plan_obj.get_price(currency=currency_obj, duration=old_plan_ref_duration_days)
                        if old_plan_price_for_ref_duration is not None and old_plan_price_for_ref_duration > 0:
                            daily_rate_old_plan = old_plan_price_for_ref_duration / old_plan_ref_duration_days
                            value_remaining = daily_rate_old_plan * remaining_days
                            logger.info(f"User {user.tg_id}: Daily rate of old plan (dev:{current_devices_raw}, dur:{old_plan_ref_duration_days}d, price:{old_plan_price_for_ref_duration}) = {daily_rate_old_plan:.4f}. Remaining value = {value_remaining:.2f} {currency_obj.code}")
                            
                            prorated_prices_for_keyboard = {}
                            new_plan_obj = services.plan.get_plan(callback_data.devices)
                            if new_plan_obj:
                                for duration_option_days in services.plan.get_durations():
                                    full_price_new_option = new_plan_obj.get_price(currency=currency_obj, duration=duration_option_days)
                                    if full_price_new_option is not None:
                                        additional_payment = max(0, full_price_new_option - value_remaining)
                                        prorated_prices_for_keyboard[duration_option_days] = round(additional_payment, 2)
                                logger.info(f"User {user.tg_id}: Calculated prorated prices: {prorated_prices_for_keyboard}")
                            else:
                                logger.warning(f"User {user.tg_id}: Could not find new plan for {callback_data.devices} devices during proration.")
                        else:
                            logger.warning(f"User {user.tg_id}: Could not get a valid price for old plan (dev:{current_devices_raw}, dur:{old_plan_ref_duration_days}d) for proration.")
                    else:
                        logger.warning(f"User {user.tg_id}: Could not find old plan for {current_devices_raw} devices for proration.")
                else:
                    logger.info(f"User {user.tg_id}: No proration. Remaining ms: {remaining_ms}, current devices: {current_devices_raw}")
            except Exception as e:
                logger.error(f"User {user.tg_id}: Error during proration calculation: {e}", exc_info=True)
        else:
            logger.warning(f"User {user.tg_id}: Cannot perform proration. No current_client_data, or expired, or missing _expiry_time/_max_devices. Client data: {current_client_data}")

    if callback_data.duration == 0: 
        logger.info(f"User {user.tg_id} needs to select duration. Showing duration keyboard. Prorated prices to pass: {prorated_prices_for_keyboard}")
        await callback.message.edit_text(
            text=_("subscription:message:duration"),
            reply_markup=duration_keyboard(
                plan_service=services.plan,
                callback_data=callback_data, 
                currency=config.shop.CURRENCY,
                prorated_prices=prorated_prices_for_keyboard
            ),
        )
        return
    
    logger.info(f"User {user.tg_id} selected duration: {callback_data.duration}. Price in callback_data: {callback_data.price}. Proceeding to payment method selection.")
    
    to_payment_cb = callback_data.model_copy(deep=True)
    to_payment_cb.state = NavSubscription.PAY 
    new_selected_plan = services.plan.get_plan(to_payment_cb.devices)
    if not new_selected_plan:
        logger.error(f"User {user.tg_id}: Could not find plan for {to_payment_cb.devices} devices before showing payment methods.")
        await services.notification.show_popup(callback, _("misc:popup:error_unexpected"))
        return

    await callback.message.edit_text(
        text=_("subscription:message:payment_method"),
        reply_markup=payment_method_keyboard(
            plan=new_selected_plan,
            callback_data=to_payment_cb,
            gateways=gateway_factory.get_gateways(),
        ),
    )


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.CHANGE_LOCATION))
async def callback_change_location_start(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    services: ServicesContainer,
    session: AsyncSession,
) -> None:
    logger.info(f"User {user.tg_id} initiated change location only. CB: {callback_data.model_dump_json(exclude_none=True)}")

    current_user_server_location: Optional[str] = None
    if not user.server_id:
        logger.warning(f"User {user.tg_id} tried to change location without an active subscription.")
        await services.notification.show_popup(callback, _("subscription:popup:no_active_sub_for_location_change"))
        cb_to_main = callback_data.model_copy(deep=True); cb_to_main.state = NavSubscription.MAIN; cb_to_main.devices = 0; cb_to_main.location = ""; cb_to_main.duration = 0; cb_to_main.is_change = False; cb_to_main.is_extend = False; cb_to_main.is_change_location = False
        client_data_for_main = None
        await show_subscription(callback, client_data_for_main, cb_to_main, None) 
        return
    else:
        current_server = await Server.get_by_id(session, user.server_id)
        if current_server:
            current_user_server_location = current_server.location
        else:
            logger.warning(f"User {user.tg_id} has server_id {user.server_id}, but server not found in DB when trying to get current location for change_location_start.")

    client = await services.vpn.is_client_exists(user, session=session)
    if not client:
        logger.error(f"User {user.tg_id} has server_id {user.server_id} but client not found on server for location change.")
        await services.notification.show_popup(callback, _("subscription:popup:error_fetching_data"))
        return
    
    current_devices = await services.vpn.get_limit_ip(user=user, client=client)
    if current_devices is None:
        logger.error(f"User {user.tg_id} has an active sub but could not determine device count, cannot change location.")
        await services.notification.show_popup(callback, _("subscription:popup:error_fetching_data"))
        return

    callback_data.devices = current_devices if current_devices != 0 else -1
    callback_data.is_change_location = True
    all_servers = await services.server_pool.get_all_servers()
    online_servers = [s for s in all_servers if s.location and s.online]

    if not online_servers:
        await services.notification.show_popup(callback=callback, text=_("subscription:popup:no_available_servers"), cache_time=120)
        return

    cb_for_location_sel = callback_data.model_copy(deep=True)
    cb_for_location_sel.state = NavSubscription.LOCATION
    cb_for_location_sel.location = ""

    logger.info(f"User {user.tg_id} proceeding to select new location (current_devices={current_devices}, current_location_on_server='{current_user_server_location}'). CB for keyboard: {cb_for_location_sel.model_dump_json(exclude_none=True)}")
    await callback.message.edit_text(
        text=_("subscription:message:location"),
        reply_markup=location_keyboard(
            servers=online_servers, 
            callback_data=cb_for_location_sel,
            current_location=current_user_server_location
        ),
    )


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.PROMOCODE))
async def callback_promocode_start(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    callback_data: SubscriptionData,
    services: ServicesContainer,
) -> None:
    logger.info(f"User {user.tg_id} initiated promocode activation. CB: {callback_data.model_dump_json(exclude_none=True)}")
    await state.set_state(SubscriptionStates.WAITING_FOR_PROMOCODE)
    await callback.message.edit_text(_("subscription:message:enter_promocode"))
    await callback.answer()


@router.message(SubscriptionStates.WAITING_FOR_PROMOCODE, F.text)
async def handle_promocode_input(
    message: types.Message,
    user: User,
    state: FSMContext,
    services: ServicesContainer,
    session: AsyncSession,
) -> None:
    promocode_text = message.text.strip().upper()
    logger.info(f"User {user.tg_id} entered promocode: '{promocode_text}'")

    promocode = await Promocode.get(session, code=promocode_text)

    if not promocode:
        await message.answer(_("promocode:ntf:activate_invalid"))
        return

    if promocode.is_activated:
        await message.answer(_("promocode:ntf:activate_invalid"))
        return


    client_data = await services.vpn.get_client_data(user, session=session)
    if not client_data or client_data.has_subscription_expired:
        await message.answer(_("promocode:ntf:no_active_sub_for_promo"))
        return

    success = await services.vpn.activate_promocode(user, promocode, session=session)

    if success:
        await Promocode.set_activated(session, code=promocode.code, user_id=user.tg_id)
        await message.answer(
            _("promocode:message:activated_success").format(
                promocode=promocode.code,
                duration=f"{promocode.duration} дней"
            )
        )
    else:
        await message.answer(_("promocode:ntf:activate_failed"))

    await state.clear()
    
    server_location: Optional[str] = None
    if user.server_id:
        server = await Server.get_by_id(session, user.server_id)
        if server:
            server_location = server.location
    
    updated_client_data = await services.vpn.get_client_data(user, session=session)

    fresh_callback_data = SubscriptionData(state=NavSubscription.MAIN, user_id=user.tg_id)
    
    await show_subscription(
        callback=message,
        client_data=updated_client_data, 
        callback_data=fresh_callback_data, 
        server_location=server_location
    )
