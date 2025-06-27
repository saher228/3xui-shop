from aiogram.filters.callback_data import CallbackData
from typing import Optional

# Existing AdminMenuCB could be here

class AdminEditUserAction(CallbackData, prefix="admin_edit_user_action"):
    action: str
    target_user_id: Optional[int] = None
    new_location_idx: Optional[str] = None
    delete_action_type: Optional[str] = None
    page: Optional[int] = None
    new_status: Optional[int] = None

class AdminEditUserNavigate(CallbackData, prefix="admin_edit_user_nav"):
    step: str