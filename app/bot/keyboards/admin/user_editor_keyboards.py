from aiogram.types import InlineKeyboardButton
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callback_data.admin_callback import AdminEditUserAction
from app.bot.utils.navigation import NavAdminTools 
from app.db.models import Server, User
from typing import List, Optional

USERS_PER_PAGE = 10

def user_selection_list_keyboard(
    users: List[User],
    current_page: int,
    total_pages: int,
    is_search_results: bool = False,
    search_query: Optional[str] = None
) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()

    for user in users:
        builder.row(
            InlineKeyboardButton(
                text=user.display_name, 
                callback_data=AdminEditUserAction(
                    action="select_user_from_list", 
                    target_user_id=user.tg_id
                ).pack()
            )
        )
    
    pagination_buttons = []
    if current_page > 0:
        pagination_buttons.append(
            InlineKeyboardButton(
                text=_("button:previous_page"),
                callback_data=AdminEditUserAction(
                    action="user_list_page", 
                    page=current_page - 1,
                ).pack()
            )
        )
    
    if current_page < total_pages - 1:
        pagination_buttons.append(
            InlineKeyboardButton(
                text=_("button:next_page"),
                callback_data=AdminEditUserAction(
                    action="user_list_page", 
                    page=current_page + 1,
                ).pack()
            )
        )
    if pagination_buttons:
        builder.row(*pagination_buttons)

    if not is_search_results:
        builder.row(
            InlineKeyboardButton(
                text=_("user_editor:button:search_user"),
                callback_data=AdminEditUserAction(action="search_user_prompt").pack()
            )
        )
        builder.row(
             InlineKeyboardButton(
                text=_("user_editor:button:create_user"),
                callback_data=AdminEditUserAction(action="create_user_prompt").pack()
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text=_("user_editor:button:back_to_full_list"),
                callback_data=AdminEditUserAction(action="back_to_user_list", page=0).pack()
            )
        )

    builder.row(
        InlineKeyboardButton(
            text=_("button:admin_tools"),
            callback_data=NavAdminTools.MAIN 
        )
    )
    return builder.as_markup()

def user_edit_actions_keyboard(target_user_id: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=_("user_editor:button:view_info"),
            callback_data=AdminEditUserAction(action="view_info", target_user_id=target_user_id).pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("user_editor:button:edit_subscription"),
            callback_data=AdminEditUserAction(action="edit_sub", target_user_id=target_user_id).pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("user_editor:button:change_location"),
            callback_data=AdminEditUserAction(action="change_loc_prompt", target_user_id=target_user_id).pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("user_editor:button:delete_user"),
            callback_data=AdminEditUserAction(action="delete_user_prompt", target_user_id=target_user_id).pack()
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text=_("button:back"),
            callback_data=AdminEditUserAction(action="back_to_user_list", target_user_id=target_user_id).pack() 
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("button:admin_tools"),
            callback_data=NavAdminTools.MAIN 
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("button:to_main_menu"),
            callback_data="main_menu"
        )
    )
    return builder.as_markup()

def edit_subscription_keyboard(target_user_id: int, is_enabled: bool) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()

    if is_enabled:
        builder.row(
            InlineKeyboardButton(
                text=_("user_editor:button:disable_subscription"),
                callback_data=AdminEditUserAction(action="toggle_sub_status", target_user_id=target_user_id, new_status=0).pack()
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text=_("user_editor:button:enable_subscription"),
                callback_data=AdminEditUserAction(action="toggle_sub_status", target_user_id=target_user_id, new_status=1).pack()
            )
        )

    builder.row(
        InlineKeyboardButton(
            text=_("user_editor:button:change_devices"),
            callback_data=AdminEditUserAction(action="change_devices_prompt", target_user_id=target_user_id).pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("user_editor:button:extend_duration"),
            callback_data=AdminEditUserAction(action="extend_duration_prompt", target_user_id=target_user_id).pack()
        )
    )
    # TODO: Add "Set new expiry date" later if needed
    # builder.row(
    #     InlineKeyboardButton(
    #         text=_("user_editor:button:set_expiry"),
    #         callback_data=AdminEditUserAction(action="set_expiry_prompt", target_user_id=target_user_id).pack()
    #     )
    # )

    builder.row(
        InlineKeyboardButton(
            text=_("button:back"),
            callback_data=AdminEditUserAction(action="back_to_user_actions", target_user_id=target_user_id).pack()
        )
    )
    return builder.as_markup()

def location_selection_keyboard_for_admin(target_user_id: int, available_locations: List[str]) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()

    if not available_locations:
        builder.row(
            InlineKeyboardButton(
                text=_("user_editor:label:no_other_locations"),
                callback_data="do_nothing_no_locations"
            )
        )
    else:
        for index, location_name in enumerate(available_locations):
            builder.row(
                InlineKeyboardButton(
                    text=location_name,
                    callback_data=AdminEditUserAction(
                        action="confirm_change_location", 
                        target_user_id=target_user_id, 
                        new_location_idx=str(index) 
                    ).pack()
                )
            )
    
    builder.row(
        InlineKeyboardButton(
            text=_("button:back"),
            callback_data=AdminEditUserAction(action="back_to_user_actions", target_user_id=target_user_id).pack()
        )
    )
    return builder.as_markup()

def delete_user_options_keyboard(target_user_id: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("user_editor:button:delete_from_xui"),
            callback_data=AdminEditUserAction(action="confirm_delete_xui", target_user_id=target_user_id).pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("user_editor:button:delete_from_db"),
            callback_data=AdminEditUserAction(action="confirm_delete_db", target_user_id=target_user_id).pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("user_editor:button:delete_everywhere"),
            callback_data=AdminEditUserAction(action="confirm_delete_all", target_user_id=target_user_id).pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("button:back"),
            callback_data=AdminEditUserAction(action="back_to_user_actions", target_user_id=target_user_id).pack()
        )
    )
    return builder.as_markup()

def confirm_delete_action_keyboard(target_user_id: int, delete_type: str) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("user_editor:button:confirm_delete_yes"),
            callback_data=AdminEditUserAction(action="execute_delete", target_user_id=target_user_id, delete_action_type=delete_type).pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("user_editor:button:confirm_delete_no"),
            callback_data=AdminEditUserAction(action="delete_user_prompt", target_user_id=target_user_id).pack() 
        )
    )
    return builder.as_markup() 