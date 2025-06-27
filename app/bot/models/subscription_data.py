from aiogram.filters.callback_data import CallbackData
from typing import Optional

from app.bot.utils.navigation import NavSubscription


class SubscriptionData(CallbackData, prefix="subscription"):
    state: NavSubscription
    is_extend: bool = False
    is_change: bool = False
    user_id: int = 0
    devices: int = 0
    duration: int = 0
    price: Optional[float] = 0.0
    location: str = ""
    is_change_location: bool = False
