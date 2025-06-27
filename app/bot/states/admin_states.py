from aiogram.fsm.state import State, StatesGroup


class AdminMenuStates(StatesGroup):
    main_menu = State()
    # ... other admin states


# Новый класс состояний для редактирования пользователей
class AdminEditUserStates(StatesGroup):
    browsing_user_list = State()
    user_selected = State() # Main menu for a selected user
    waiting_for_search_query = State()
    waiting_for_user_id = State() # For entering user ID manually
    
    # States for "Edit Subscription"
    waiting_for_edit_subscription_action = State() # After clicking "Edit Subscription", showing device/duration options
    waiting_for_new_device_count = State()
    waiting_for_new_duration_days = State()
    # waiting_for_new_expiry_choice = State() # For choosing extend/set new date
    # waiting_for_new_absolute_expiry_date = State() # If setting a new date

    # States for "Change Location"
    waiting_for_new_location_selection = State()

    # States for "Delete User"
    waiting_for_delete_option = State()
    waiting_for_delete_confirmation = State()
    processing_deletion = State() # State during deletion process to prevent double-clicking

    # Состояния для конкретных действий редактирования будут добавлены позже

class AdminCreateUserStates(StatesGroup):
    waiting_for_user_identifier = State()
    waiting_for_location = State()
    waiting_for_devices = State()
    waiting_for_duration = State()
    confirming_creation = State()

# Ensure other existing states are preserved if this file is being appended to.
# If this is a new file, the above is fine.
# If AdminMenuStates already exists, I'm adding AdminEditUserStates to the same file. 