import logging
from aiogram import Router, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import delete

logger = logging.getLogger(__name__)

from app.bot.states.admin_states import AdminEditUserStates, AdminCreateUserStates
from app.bot.callback_data.admin_callback import AdminEditUserAction
from app.bot.keyboards.admin.user_editor_keyboards import (
    user_edit_actions_keyboard, 
    edit_subscription_keyboard, 
    location_selection_keyboard_for_admin,
    delete_user_options_keyboard,
    confirm_delete_action_keyboard,
    user_selection_list_keyboard,
    USERS_PER_PAGE
)
from app.bot.services.vpn import VPNService
from app.bot.services.server_pool import ServerPoolService
from app.bot.utils.navigation import NavAdminTools 
from app.bot.utils.constants import UNLIMITED
from app.db.models import User, Server, Transaction
from app.bot.models import ServicesContainer

router = Router(name="admin_user_editor")

async def get_total_users_count(session_maker: async_sessionmaker) -> int:
    async with session_maker() as session:
        all_users = await User.get_all(session) 
        return len(all_users)

@router.callback_query(F.data == NavAdminTools.USER_EDITOR)
async def handle_user_editor_entry(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession, session_maker: async_sessionmaker):
    await state.set_state(AdminEditUserStates.browsing_user_list)
    
    users_page = await User.get_all(session, limit=USERS_PER_PAGE, offset=0)
    total_users = await get_total_users_count(session_maker) 
    total_pages = (total_users + USERS_PER_PAGE - 1) // USERS_PER_PAGE

    if not users_page:
        # TODO: Add a specific message for no users found, maybe with just search and back buttons
        await callback.message.edit_text(_("user_editor:message:no_users_found_initial")) 
    else:
        await callback.message.edit_text(
            _("user_editor:prompt:select_user_or_search"),
            reply_markup=user_selection_list_keyboard(
                users=users_page, 
                current_page=0, 
                total_pages=total_pages
            )
        )
    await state.update_data(current_search_query=None, is_search_mode=False)
    await callback.answer()

@router.callback_query(AdminEditUserAction.filter(F.action == "select_user_from_list"), StateFilter(AdminEditUserStates.browsing_user_list))
async def handle_select_user_from_list(callback: types.CallbackQuery, state: FSMContext, callback_data: AdminEditUserAction, session: AsyncSession):
    target_user_id = callback_data.target_user_id
    if not target_user_id:
        await callback.answer(_("user_editor:error:no_target_user_id_selected"), show_alert=True)
        return

    target_user = await User.get(session, tg_id=target_user_id)

    if not target_user:
        await callback.message.edit_text(_("user_editor:error:user_not_found").format(user_id=target_user_id))
        await state.set_state(AdminEditUserStates.browsing_user_list)
        return

    await state.update_data(target_user_id=target_user.tg_id, target_user_vpn_id=target_user.vpn_id, target_user_server_id=target_user.server_id)
    await state.set_state(AdminEditUserStates.user_selected)
    
    reply_markup = user_edit_actions_keyboard(target_user_id=target_user.tg_id)
    await callback.message.edit_text(_("user_editor:prompt:user_selected").format(user_id=target_user.tg_id), reply_markup=reply_markup)
    await callback.answer()

@router.callback_query(AdminEditUserAction.filter(F.action.in_(["user_list_page", "back_to_user_list"])))
async def handle_user_list_navigation(
    callback: types.CallbackQuery, 
    state: FSMContext, 
    callback_data: AdminEditUserAction, 
    session: AsyncSession, 
    session_maker: async_sessionmaker
):
    current_page = callback_data.page if callback_data.page is not None else 0
    data = await state.get_data()
    search_query = data.get("current_search_query")
    is_search_mode = data.get("is_search_mode", False)

    if callback_data.action == "back_to_user_list":
        search_query = None
        is_search_mode = False
        current_page = 0
        await state.update_data(current_search_query=None, is_search_mode=False)
        await state.set_state(AdminEditUserStates.browsing_user_list)

    if callback_data.action == "user_list_page":
         await state.set_state(AdminEditUserStates.browsing_user_list)

    offset = current_page * USERS_PER_PAGE

    if is_search_mode and search_query:
        users_page = await User.search_users(session, query_text=search_query, limit=USERS_PER_PAGE, offset=offset)
        async with session_maker() as count_session:
             all_search_results_for_count = await User.search_users(count_session, query_text=search_query)
        total_pages = (len(all_search_results_for_count) + USERS_PER_PAGE - 1) // USERS_PER_PAGE
        list_title = _("user_editor:message:search_results_for").format(query=search_query)
    else:
        users_page = await User.get_all(session, limit=USERS_PER_PAGE, offset=offset)
        total_users = await get_total_users_count(session_maker)
        total_pages = (total_users + USERS_PER_PAGE - 1) // USERS_PER_PAGE
        list_title = _("user_editor:prompt:select_user_or_search")
    
    if not users_page and current_page == 0:
        msg_text = _("user_editor:message:no_users_found_initial") if not is_search_mode else _("user_editor:message:no_users_found_search").format(query=search_query)
        # Keyboard should probably just have search/back button
    else:
        msg_text = list_title

    await callback.message.edit_text(
        text=msg_text,
        reply_markup=user_selection_list_keyboard(
            users=users_page,
            current_page=current_page,
            total_pages=total_pages, 
            is_search_results=is_search_mode,
            search_query=search_query
        )
    )
    await callback.answer()

# Handler for "Search User" button
@router.callback_query(AdminEditUserAction.filter(F.action == "search_user_prompt"), StateFilter(AdminEditUserStates.browsing_user_list))
async def handle_search_user_prompt(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminEditUserStates.waiting_for_search_query)
    await callback.message.edit_text(_("user_editor:prompt:enter_search_query"))
    await callback.answer()

# Handler for receiving search query
@router.message(StateFilter(AdminEditUserStates.waiting_for_search_query), F.text)
async def handle_user_search_query(
    message: types.Message, 
    state: FSMContext, 
    session: AsyncSession, 
    session_maker: async_sessionmaker
):
    search_query = message.text
    if not search_query or len(search_query) < 1: # Basic validation
        await message.answer(_("user_editor:error:search_query_too_short"))
        # Remain in waiting_for_search_query state
        return

    await state.update_data(current_search_query=search_query, is_search_mode=True)
    await state.set_state(AdminEditUserStates.browsing_user_list) # Switch back to browsing to display results

    users_page = await User.search_users(session, query_text=search_query, limit=USERS_PER_PAGE, offset=0)
    
    async with session_maker() as count_session:
        all_search_results_for_count = await User.search_users(count_session, query_text=search_query) 
    total_pages = (len(all_search_results_for_count) + USERS_PER_PAGE - 1) // USERS_PER_PAGE
    
    if not users_page:
        await message.answer(
            _("user_editor:message:no_users_found_search").format(query=search_query),
            reply_markup=user_selection_list_keyboard(
                users=[], 
                current_page=0, 
                total_pages=0, 
                is_search_results=True, 
                search_query=search_query
            )
        )
    else:
        await message.answer(
            _("user_editor:message:search_results_for").format(query=search_query),
            reply_markup=user_selection_list_keyboard(
                users=users_page, 
                current_page=0, 
                total_pages=total_pages, 
                is_search_results=True, 
                search_query=search_query
            )
        )

# Handler for "View Info" button
@router.callback_query(AdminEditUserAction.filter(F.action == "view_info"), StateFilter(AdminEditUserStates.user_selected))
async def handle_view_user_info(
    callback: types.CallbackQuery, 
    state: FSMContext, 
    session_maker: async_sessionmaker,
    vpn: VPNService
):
    data = await state.get_data()
    target_user_id = data.get("target_user_id")

    if not target_user_id:
        await callback.message.edit_text(_("user_editor:error:state_lost_user_id"))
        await state.clear()
        return

    # Get user from DB for the most current data
    async with session_maker() as session:
        user = await User.get(session, tg_id=target_user_id)
    
    if not user:
        await callback.message.edit_text(_("user_editor:error:user_not_found").format(user_id=target_user_id))
        return

    # Try to get fresh user info from Telegram and update DB if needed
    try:
        chat = await callback.bot.get_chat(target_user_id)
        if user.username != chat.username or user.first_name != chat.first_name:
            async with session_maker() as update_session:
                user_to_update = await User.get(update_session, tg_id=target_user_id)
                if user_to_update:
                    user_to_update.username = chat.username
                    user_to_update.first_name = chat.first_name
                    await update_session.commit()
                    user.username = chat.username # Refresh local object
                    logger.info(f"Updated user {target_user_id} info from Telegram.")
    except Exception as e:
        logger.warning(f"Could not fetch/update user info for {target_user_id} on view: {e}. Using DB values.")

    # Format username and language for display
    username_str = f"@{user.username}" if user.username else _("status:not_available")
    lang_code_str = user.language_code or 'ru' # Default to 'ru' if None

    # Server and Location Info
    server_name_str = _("status:not_assigned")
    server_location_str = _("status:not_applicable")

    if user.server_id:
        async with session_maker() as session:
            server = await Server.get_by_id(session, user.server_id)
        if server:
            server_name_str = server.name
            server_location_str = server.location or _("status:location_not_set")
        else:
            server_name_str = _("user_editor:info:server_id_not_found").format(server_id=user.server_id)
            server_location_str = _("status:not_found")

    user_info_parts = [
        _("user_editor:info:tg_id").format(tg_id=user.tg_id),
        _("user_editor:info:username").format(username=username_str),
        _("user_editor:info:language_code").format(lang_code=lang_code_str),
        _("user_editor:info:vpn_id").format(vpn_id=user.vpn_id or _("status:not_set")),
        _("user_editor:info:server_name").format(server_name=server_name_str),
        _("user_editor:info:server_location").format(location=server_location_str),
    ]

    # Get 3x-ui client data
    client_data_message = _("user_editor:info:xui_data_unavailable")
    if user.server_id and user.vpn_id:
        client = await vpn.is_client_exists(user)
        is_enabled = client.enable if client else False
        logger.info(f"Client {user.tg_id} enable state from X-UI: {is_enabled}")
        
        client_data = await vpn.get_client_data(user=user)
        if client_data:
            expiry_time_str = client_data.expiry_time_str or _("status:unlimited_or_not_set")
            traffic_total_str = client_data.traffic_total or _("status:unlimited")
            traffic_remaining_str = client_data.traffic_remaining or _("status:unlimited")
            max_devices_val = client_data.max_devices
            max_devices_str = str(max_devices_val) if max_devices_val != UNLIMITED else _("status:unlimited")
            
            if not is_enabled:
                status_text = "❌ " + _("status:disabled")
            elif client_data.has_subscription_expired:
                status_text = "❌ " + _("status:expired")
            else:
                status_text = "✅ " + _("status:active")
            
            client_data_message = _("user_editor:info:xui_data").format(
                devices=max_devices_str,
                expiry_time=expiry_time_str,
                traffic_total=traffic_total_str,
                traffic_remaining=traffic_remaining_str,
                status=status_text
            )
        else:
            client_data_message = _("user_editor:info:xui_data_fetch_failed")
            
    user_info_parts.append("\n" + client_data_message)
    
    full_info_message = "\n".join(user_info_parts)
    await callback.message.edit_text(full_info_message, reply_markup=callback.message.reply_markup)
    await callback.answer()

# Handler for "🔧 Изменить подписку" button
@router.callback_query(AdminEditUserAction.filter(F.action == "edit_sub"), StateFilter(AdminEditUserStates.user_selected))
async def handle_edit_subscription_entry(
    callback: types.CallbackQuery, 
    state: FSMContext, 
    callback_data: AdminEditUserAction,
    services: ServicesContainer,
    session_maker: async_sessionmaker
):
    target_user_id = callback_data.target_user_id
    
    # Get the real client state
    is_enabled = False
    async with session_maker() as session:
        user = await User.get(session, tg_id=target_user_id)
        if user and user.vpn_id:
            client = await services.vpn.is_client_exists(user)
            if client:
                is_enabled = client.enable
                logger.info(f"Client {target_user_id} enable state from X-UI: {is_enabled}")

    await state.set_state(AdminEditUserStates.waiting_for_edit_subscription_action)
    
    # Use the real state for the keyboard
    reply_markup = edit_subscription_keyboard(target_user_id=target_user_id, is_enabled=is_enabled)
    await callback.message.edit_text(
        _("user_editor:prompt:edit_subscription_menu").format(user_id=target_user_id), 
        reply_markup=reply_markup
    )
    await callback.answer()

# Handler for "Включить/Отключить подписку" button
@router.callback_query(AdminEditUserAction.filter(F.action == "toggle_sub_status"), StateFilter(AdminEditUserStates.waiting_for_edit_subscription_action))
async def handle_toggle_client_status(
    callback: types.CallbackQuery,
    state: FSMContext,
    callback_data: AdminEditUserAction,
    vpn: VPNService,
    session_maker: async_sessionmaker
):
    await callback.answer() # Acknowledge immediately
    target_user_id = callback_data.target_user_id
    enable_action = callback_data.new_status == 1

    async with session_maker() as session:
        user = await User.get(session, tg_id=target_user_id)
    
    if not user:
        await callback.message.edit_text(_("user_editor:error:user_not_found_in_db").format(user_id=target_user_id))
        return

    # First attempt to toggle the status
    success = False
    if enable_action:
        success = await vpn.enable_client(user)
    else:
        success = await vpn.disable_client(user)
    
    if success:
        # After successful toggle, verify the actual client state
        await callback.message.edit_text(_("user_editor:info:verifying_status").format(user_id=target_user_id))
        
        # Give X-UI a moment to update the state
        import asyncio
        await asyncio.sleep(2)  # Increased delay to ensure X-UI updates
        
        # Get the real client state after toggle
        client = await vpn.is_client_exists(user)
        actual_state = False
        if client:
            actual_state = client.enable
            logger.info(f"Client {target_user_id} enable state from X-UI after toggle: {actual_state}")
            
        # Use the actual verified state for the UI update
        action_text = _("status:enabled") if actual_state else _("status:disabled")
        await callback.message.edit_text(
            _("user_editor:success:subscription_status_changed").format(user_id=target_user_id, status=action_text),
            reply_markup=edit_subscription_keyboard(target_user_id=target_user_id, is_enabled=actual_state)
        )
    else:
        await callback.message.edit_text(
            _("user_editor:error:subscription_status_change_failed").format(user_id=target_user_id),
            reply_markup=callback.message.reply_markup # Keep old keyboard
        )

# Handler for "Back to user actions" (from edit_subscription_keyboard, delete_options_keyboard, location_selection_keyboard_for_admin)
@router.callback_query(
    AdminEditUserAction.filter(F.action == "back_to_user_actions"), 
    StateFilter(
        AdminEditUserStates.waiting_for_edit_subscription_action,
        AdminEditUserStates.waiting_for_delete_option,
        AdminEditUserStates.waiting_for_new_location_selection
        # Добавьте сюда другие состояния, если из них тоже есть кнопка "Назад" с action="back_to_user_actions"
    )
)
async def handle_back_to_user_actions(callback: types.CallbackQuery, state: FSMContext, callback_data: AdminEditUserAction):
    target_user_id = callback_data.target_user_id
    await state.set_state(AdminEditUserStates.user_selected)
    reply_markup = user_edit_actions_keyboard(target_user_id=target_user_id)
    await callback.message.edit_text(_("user_editor:prompt:user_selected").format(user_id=target_user_id), reply_markup=reply_markup)
    await callback.answer()

# Handler for "Изменить кол-во устройств" button (prompt for new count)
@router.callback_query(AdminEditUserAction.filter(F.action == "change_devices_prompt"), StateFilter(AdminEditUserStates.waiting_for_edit_subscription_action))
async def handle_change_devices_prompt(callback: types.CallbackQuery, state: FSMContext, callback_data: AdminEditUserAction):
    target_user_id = callback_data.target_user_id 
    # await state.update_data(target_user_id=target_user_id) # Already in state
    await state.set_state(AdminEditUserStates.waiting_for_new_device_count)
    await callback.message.edit_text(_("user_editor:prompt:enter_new_device_count").format(user_id=target_user_id))
    await callback.answer()

# Handler for receiving new device count
@router.message(StateFilter(AdminEditUserStates.waiting_for_new_device_count), F.text)
async def handle_new_device_count_input(
    message: types.Message, 
    state: FSMContext, 
    session_maker: async_sessionmaker, 
    services: ServicesContainer
):
    if not message.text.isdigit() or int(message.text) < 0:
        await message.answer(_("user_editor:error:invalid_device_count"))
        return

    new_device_count = int(message.text)
    data = await state.get_data()
    target_user_id = data.get("target_user_id")

    if not target_user_id:
        await message.answer(_("user_editor:error:state_lost_user_id_generic"))
        await state.clear()
        return

    async with session_maker() as session:
        db_user = await User.get(session, tg_id=target_user_id)
        if not db_user:
            await message.answer(_("user_editor:error:user_not_found_in_db").format(user_id=target_user_id))
            return

    success = await services.vpn.update_client(
        user=db_user, 
        devices=new_device_count,
        replace_devices=True
    )

    if success:
        await message.answer(_("user_editor:success:device_count_updated").format(user_id=target_user_id, count=new_device_count))
    else:
        await message.answer(_("user_editor:error:device_count_update_failed").format(user_id=target_user_id))
    
    # Go back to the user actions menu
    await state.set_state(AdminEditUserStates.user_selected)
    reply_markup = user_edit_actions_keyboard(target_user_id=target_user_id) # type: ignore
    await message.answer(_("user_editor:prompt:user_selected").format(user_id=target_user_id), reply_markup=reply_markup)

# Handler for "📍 Сменить локацию" button (prompt)
@router.callback_query(AdminEditUserAction.filter(F.action == "change_loc_prompt"), StateFilter(AdminEditUserStates.user_selected))
async def handle_change_location_prompt(
    callback: types.CallbackQuery,
    state: FSMContext,
    callback_data: AdminEditUserAction,
    session: AsyncSession,
    services: ServicesContainer,
):
    target_user_id = callback_data.target_user_id
    user = await User.get(session, tg_id=target_user_id)
    if not user or not user.server_id:
        await callback.answer(_("user_editor:error:no_sub_for_loc_change"), show_alert=True)
        return
    
    current_server = await Server.get_by_id(session, user.server_id)
    if not current_server:
        await callback.answer(_("user_editor:error:current_server_not_found"), show_alert=True)
        return
        
    all_servers = await services.server_pool.get_all_servers()
    available_locations = sorted(list(set(s.location for s in all_servers if s.online and s.location != current_server.location)))

    if not available_locations:
        await callback.answer(_("user_editor:error:no_other_locations_available"), show_alert=True)
        return

    await state.set_state(AdminEditUserStates.waiting_for_new_location_selection)
    await callback.message.edit_text(
        _("user_editor:prompt:select_new_location").format(user_id=target_user_id),
        reply_markup=location_selection_keyboard_for_admin(
            target_user_id=target_user_id,
            available_locations=available_locations
        )
    )
    await callback.answer()

# Handler for selecting a new location
@router.callback_query(AdminEditUserAction.filter(F.action == "confirm_change_location"), StateFilter(AdminEditUserStates.waiting_for_new_location_selection))
async def handle_confirm_change_location(
    callback: types.CallbackQuery,
    state: FSMContext,
    callback_data: AdminEditUserAction,
    session: AsyncSession,
    services: ServicesContainer,
):
    data = await state.get_data()
    target_user_id = data.get("target_user_id")

    if not target_user_id:
        await callback.answer(_("user_editor:error:state_lost_user_id"), show_alert=True)
        await state.clear() 
        return

    user = await User.get(session, tg_id=target_user_id)
    if not user:
        await callback.answer(_("user_editor:error:user_not_found_in_db").format(user_id=target_user_id), show_alert=True)
        await state.clear()
        return

    try:
        location_idx = int(callback_data.new_location_idx)
    except (ValueError, TypeError):
        await callback.answer(_("user_editor:error:invalid_location_id"), show_alert=True)
        return

    all_servers = await services.server_pool.get_all_servers()
    current_server = await Server.get_by_id(session, user.server_id)
    available_locations = sorted(list(set(s.location for s in all_servers if s.online and s.location != (current_server.location if current_server else None))))

    if not 0 <= location_idx < len(available_locations):
        await callback.answer(_("user_editor:error:location_index_out_of_bounds"), show_alert=True)
        return
        
    selected_location_name = available_locations[location_idx]

    client = await services.vpn.is_client_exists(user, session=session)
    if not client:
        await callback.answer(_("user_editor:error:no_client_on_server_for_loc_change"), show_alert=True)
        return

    current_devices = await services.vpn.get_limit_ip(user=user, client=client)
    if current_devices is None: # Can be 0 for unlimited, but None is an error
        await callback.answer(_("user_editor:error:failed_to_get_device_count"), show_alert=True)
        return

    try:
        success = await services.vpn.change_client_location(
            user=user,
            new_location_name=selected_location_name,
            current_devices=current_devices,
            session=session,
        )
        if success:
            await callback.message.edit_text(
                _("user_editor:prompt:user_selected").format(user_id=user.tg_id), 
                reply_markup=user_edit_actions_keyboard(user.tg_id)
            )
            await callback.answer(_("user_editor:success:location_changed").format(user_id=target_user_id, location=selected_location_name), show_alert=True)

        else:
            await callback.answer(_("user_editor:error:failed_to_change_location").format(user_id=target_user_id, location=selected_location_name), show_alert=True)
    
    except Exception as e:
        logger.error(f"Error changing location for user {user.tg_id} via admin panel: {e}", exc_info=True)
        await callback.answer(_("user_editor:error:failed_to_change_location_exception"), show_alert=True)

    await state.set_state(AdminEditUserStates.user_selected)

# Handler for "Продлить подписку" button (prompt for duration)
@router.callback_query(AdminEditUserAction.filter(F.action == "extend_duration_prompt"), StateFilter(AdminEditUserStates.waiting_for_edit_subscription_action))
async def handle_extend_duration_prompt(callback: types.CallbackQuery, state: FSMContext, callback_data: AdminEditUserAction):
    target_user_id = callback_data.target_user_id
    await state.set_state(AdminEditUserStates.waiting_for_new_duration_days)
    await callback.message.edit_text(_("user_editor:prompt:enter_duration_days_to_add").format(user_id=target_user_id))
    await callback.answer()

# Handler for receiving new duration days
@router.message(StateFilter(AdminEditUserStates.waiting_for_new_duration_days), F.text)
async def handle_new_duration_days_input(
    message: types.Message, 
    state: FSMContext, 
    session_maker: async_sessionmaker, 
    services: ServicesContainer
):
    try:
        days = int(message.text)
        if days < 0:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer(_("admin_tools:user_editor:invalid_days_positive"))
        return

    days_to_add = int(message.text)
    data = await state.get_data()
    target_user_id = data.get("target_user_id")

    if not target_user_id:
        await message.answer(_("user_editor:error:state_lost_user_id_generic"))
        await state.clear()
        return

    async with session_maker() as session:
        db_user = await User.get(session, tg_id=target_user_id)
        if not db_user:
            await message.answer(_("user_editor:error:user_not_found_in_db").format(user_id=target_user_id))
            return

    success = await services.vpn.update_client(
        user=db_user, 
        duration=days_to_add,
        replace_duration=False
    )

    if success:
        if days_to_add == 0:
            await message.answer(_("user_editor:success:duration_set_unlimited").format(user_id=target_user_id))
        else:
            await message.answer(_("user_editor:success:duration_updated").format(user_id=target_user_id, days=days_to_add))
    else:
        await message.answer(_("user_editor:error:duration_update_failed").format(user_id=target_user_id))
    
    # Go back to the user actions menu
    await state.set_state(AdminEditUserStates.user_selected)
    reply_markup = user_edit_actions_keyboard(target_user_id=target_user_id) # type: ignore
    await message.answer(_("user_editor:prompt:user_selected").format(user_id=target_user_id), reply_markup=reply_markup)

# Handler for "Delete User" button.
@router.callback_query(
    AdminEditUserAction.filter(F.action == "delete_user_prompt"), 
    StateFilter(AdminEditUserStates.user_selected)
)
async def handle_delete_user_prompt(
    callback: types.CallbackQuery, 
    state: FSMContext, 
    callback_data: AdminEditUserAction
):
    """
    Handles the initial "Delete User" button press from the user actions menu.
    Prompts the admin to choose what exactly to delete.
    """
    current_state = await state.get_state()
    if current_state != AdminEditUserStates.user_selected:
        await callback.answer(_("user_editor:error:wrong_state"), show_alert=True)
        return

    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    
    await state.set_state(AdminEditUserStates.waiting_for_delete_option)

    await callback.message.edit_text(
        _("user_editor:prompt:delete_options").format(user_id=target_user_id),
        reply_markup=delete_user_options_keyboard(target_user_id=target_user_id)
    )
    await callback.answer()

@router.callback_query(
    AdminEditUserAction.filter(F.action.in_(["confirm_delete_xui", "confirm_delete_db", "confirm_delete_all"])), 
    StateFilter(AdminEditUserStates.waiting_for_delete_option)
)
async def handle_delete_option_selected(
    callback: types.CallbackQuery, 
    state: FSMContext, 
    callback_data: AdminEditUserAction
):
    target_user_id = callback_data.target_user_id
    # Extract action: 'confirm_delete_xui' -> 'xui'
    action_prefix = "confirm_delete_"
    delete_type = callback_data.action[len(action_prefix):]

    await state.update_data(target_user_id=target_user_id, delete_action_type=delete_type)
    await state.set_state(AdminEditUserStates.waiting_for_delete_confirmation)

    confirmation_texts = {
        "xui": _("user_editor:prompt:confirm_delete_xui").format(user_id=target_user_id),
        "db": _("user_editor:prompt:confirm_delete_db").format(user_id=target_user_id),
        "all": _("user_editor:prompt:confirm_delete_all").format(user_id=target_user_id),
    }
    
    reply_markup = confirm_delete_action_keyboard(target_user_id=target_user_id, delete_type=delete_type)
    await callback.message.edit_text(confirmation_texts.get(delete_type, _("user_editor:prompt:confirm_delete_generic").format(user_id=target_user_id)), reply_markup=reply_markup)
    await callback.answer()

# Handler for "Да, удалить" button (executes the deletion)
@router.callback_query(AdminEditUserAction.filter(F.action == "execute_delete"), StateFilter(AdminEditUserStates.waiting_for_delete_confirmation))
async def handle_execute_delete_action(
    callback: types.CallbackQuery, 
    state: FSMContext, 
    callback_data: AdminEditUserAction,
    vpn: VPNService,
    session_maker: async_sessionmaker
):
    target_user_id = callback_data.target_user_id
    delete_type = callback_data.delete_action_type
    messages = []

    async with session_maker() as session:
        user = await User.get(session, tg_id=target_user_id)
        if not user:
            await callback.message.edit_text(_("user_editor:error:user_not_found_for_delete").format(user_id=target_user_id))
            await state.set_state(AdminEditUserStates.browsing_user_list)
            return

    delete_xui_success = False
    if delete_type in ["xui", "all"]:
        if user.vpn_id and user.server_id:
            delete_xui_success = await vpn.delete_client(user=user)
            if delete_xui_success:
                messages.append(_("user_editor:success:deleted_from_xui").format(user_id=target_user_id))
                if delete_type == "xui":
                    async with session_maker() as session_update:
                        user_to_update = await User.get(session_update, tg_id=target_user_id)
                        if user_to_update:
                            user_to_update.server_id = None
                            user_to_update.vpn_id = None
                            await session_update.commit()
            else:
                messages.append(_("user_editor:error:delete_from_xui_failed").format(user_id=target_user_id))
        else:
            messages.append(_("user_editor:info:cannot_delete_from_xui_no_data").format(user_id=target_user_id))
            delete_xui_success = True # Treat as success if there was nothing to delete

    delete_db_success = False
    if delete_type in ["db", "all"]:
        try:
            async with session_maker() as session_delete:
                user_to_delete = await User.get(session_delete, tg_id=target_user_id)
                if user_to_delete:
                    await session_delete.execute(
                        delete(Transaction).where(Transaction.tg_id == target_user_id)
                    )
                    await session_delete.delete(user_to_delete)
                    await session_delete.commit()
                    
                    check_user = await User.get(session_delete, tg_id=target_user_id)
                    if check_user:
                        delete_db_success = False
                        messages.append(_("user_editor:error:delete_from_db_failed").format(user_id=target_user_id))
                    else:
                        delete_db_success = True
                        messages.append(_("user_editor:success:deleted_from_db").format(user_id=target_user_id))
                else:
                    messages.append(_("user_editor:info:user_already_not_in_db").format(user_id=target_user_id))
                    delete_db_success = True
        except Exception as e:
            logger.error(f"Exception during DB delete for user {target_user_id}: {e}", exc_info=True)
            delete_db_success = False
            messages.append(_("user_editor:error:delete_from_db_failed").format(user_id=target_user_id))

    final_message_text = "\n".join(messages) if messages else _("user_editor:error:delete_action_inconclusive")
    await callback.message.edit_text(final_message_text)
        
    await state.set_state(AdminEditUserStates.browsing_user_list)
    await show_user_list(callback.message, session_maker)

async def show_user_list(message: types.Message, session_maker: async_sessionmaker):
    async with session_maker() as session_list:
        users_page = await User.get_all(session_list, limit=USERS_PER_PAGE, offset=0)
        total_users = await get_total_users_count(session_maker)
        total_pages = (total_users + USERS_PER_PAGE - 1) // USERS_PER_PAGE

        if not users_page:
            await message.answer(_("user_editor:message:no_users_found_initial"))
        else:
            await message.answer(
                _("user_editor:prompt:select_user_or_search"),
                reply_markup=user_selection_list_keyboard(
                    users=users_page,
                    current_page=0,
                    total_pages=total_pages
                )
            )

# Go back to previous state (likely user selection or main admin menu)
@router.callback_query(AdminEditUserAction.filter(F.action == "back_to_delete_options"), StateFilter(AdminEditUserStates.waiting_for_delete_confirmation))
async def handle_back_to_delete_options(callback: types.CallbackQuery, state: FSMContext, callback_data: AdminEditUserAction):
    target_user_id = callback_data.target_user_id
    await state.set_state(AdminEditUserStates.waiting_for_delete_option)
    reply_markup = delete_user_options_keyboard(target_user_id=target_user_id)
    await callback.message.edit_text(_("user_editor:prompt:delete_options").format(user_id=target_user_id), reply_markup=reply_markup)
    await callback.answer()

def confirm_creation_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("user_editor:button:confirm_creation"), # ✅ Да, создать
            callback_data=AdminEditUserAction(action="execute_creation").pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("user_editor:button:cancel_creation"), # ❌ Отменить
            callback_data=AdminEditUserAction(action="back_to_user_list").pack()
        )
    )
    return builder.as_markup()

# [CREATE USER FLOW]

# Step 1: Prompt for user ID
@router.callback_query(AdminEditUserAction.filter(F.action == "create_user_prompt"))
async def handle_create_user_prompt(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminCreateUserStates.waiting_for_user_identifier)
    await callback.message.edit_text(_("user_editor:prompt:enter_new_user_id"))
    await callback.answer()

# Step 2: Receive user ID, prompt for location
@router.message(StateFilter(AdminCreateUserStates.waiting_for_user_identifier), F.text)
async def handle_create_user_identifier(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
    services: ServicesContainer,
):
    identifier = message.text.strip()
    if identifier.startswith('@'):
        # For now, we only support ID. Username support is complex.
        await message.answer(_("user_editor:error:username_not_supported"))
        return
        
    if not identifier.isdigit():
        await message.answer(_("user_editor:error:invalid_user_id_format"))
        return

    target_user_id = int(identifier)
    existing_user = await User.get(session, tg_id=target_user_id)
    if existing_user and existing_user.vpn_id:
        await message.answer(_("user_editor:error:user_already_exists_with_sub").format(user_id=target_user_id))
        return
    
    all_servers = await services.server_pool.get_all_servers()
    available_locations = sorted(list(set(s.location for s in all_servers if s.online)))

    if not available_locations:
        await message.answer(_("user_editor:error:no_locations_for_creation"))
        await state.clear()
        return

    await state.update_data(target_user_id=target_user_id)
    await state.set_state(AdminCreateUserStates.waiting_for_location)
    await message.answer(
        _("user_editor:prompt:select_location_for_new_user"),
        reply_markup=location_selection_keyboard_for_admin(
            target_user_id=target_user_id, # Not really needed here, but keyboard requires it
            available_locations=available_locations
        )
    )

# Step 3: Receive location, prompt for devices
@router.callback_query(AdminEditUserAction.filter(F.action == "confirm_change_location"), StateFilter(AdminCreateUserStates.waiting_for_location))
async def handle_create_user_location(
    callback: types.CallbackQuery,
    state: FSMContext,
    callback_data: AdminEditUserAction,
    services: ServicesContainer,
):
    await callback.answer()
    location_idx_str = callback_data.new_location_idx
    
    all_servers = await services.server_pool.get_all_servers()
    available_locations = sorted(list(set(s.location for s in all_servers if s.online)))

    try:
        location_idx = int(location_idx_str)
        location_name = available_locations[location_idx]
    except (ValueError, IndexError, TypeError):
        await callback.message.edit_text(_("user_editor:error:invalid_location_selection"))
        return
        
    await state.update_data(location=location_name)
    await state.set_state(AdminCreateUserStates.waiting_for_devices)
    await callback.message.edit_text(_("user_editor:prompt:enter_devices_for_new_user"))

# Step 4: Receive devices, prompt for duration
@router.message(StateFilter(AdminCreateUserStates.waiting_for_devices), F.text)
async def handle_create_user_devices(message: types.Message, state: FSMContext):
    try:
        devices = int(message.text)
        if devices < 0:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer(_("user_editor:error:invalid_devices_positive"))
        return

    await state.update_data(devices=devices)
    await state.set_state(AdminCreateUserStates.waiting_for_duration)
    await message.answer(_("user_editor:prompt:enter_duration_for_new_user"))

# Step 5: Receive duration, prompt for confirmation
@router.message(StateFilter(AdminCreateUserStates.waiting_for_duration), F.text)
async def handle_create_user_duration(message: types.Message, state: FSMContext):
    try:
        days = int(message.text)
        if days < 0:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer(_("user_editor:error:invalid_days_positive"))
        return
        
    await state.update_data(duration=days)
    
    data = await state.get_data()
    devices = data.get('devices')
    duration = data.get('duration')
    
    confirmation_text = _("user_editor:prompt:confirm_creation_details").format(
        user_id=data.get('target_user_id'),
        location=data.get('location'),
        devices_str=devices,
        duration_str=_("status:unlimited") if duration == 0 else _('{n} days').format(n=duration)
    )
    
    await state.set_state(AdminCreateUserStates.confirming_creation)
    await message.answer(confirmation_text, reply_markup=confirm_creation_keyboard())

# Step 6: Execute creation
@router.callback_query(AdminEditUserAction.filter(F.action == "execute_creation"), StateFilter(AdminCreateUserStates.confirming_creation))
async def handle_execute_creation(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession, services: ServicesContainer):
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    devices = data.get("devices")
    duration = data.get("duration")
    location = data.get("location")

    if not all([target_user_id, location, devices is not None, duration is not None]):
        await callback.message.edit_text(_("user_editor:error:state_lost_data_for_creation"))
        await state.clear()
        return
        
    await callback.message.edit_text(_("user_editor:info:processing_creation").format(user_id=target_user_id))
    
    user = await User.get(session, tg_id=target_user_id)
    if not user:
        try:
            chat = await callback.bot.get_chat(target_user_id)
            username = chat.username
            first_name = chat.first_name or f"User {target_user_id}"
        except Exception as e:
            logger.warning(f"Could not fetch chat info for {target_user_id}: {e}. Using default values.")
            username = None
            first_name = f"User {target_user_id}"

        user = User(
            tg_id=target_user_id,
            username=username,
            first_name=first_name
        )

    created_user = await services.vpn.create_client(
        user=user,
        devices=devices,
        duration=duration,
        location_name=location,
        session=session,
    )

    if created_user:
        await callback.message.edit_text(_("user_editor:success:user_created").format(
            user_id=created_user.tg_id, 
            server_id=created_user.server_id, 
            vpn_id=created_user.vpn_id
        ))
    else:
        await callback.message.edit_text(_("user_editor:error:user_creation_failed").format(user_id=target_user_id))
        
    await state.clear()
    # Optionally, can show user list again here

# [END CREATE USER FLOW]