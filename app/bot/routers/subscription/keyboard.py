from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.bot.services import PlanService

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.models import SubscriptionData
from app.bot.models.plan import Plan
from app.bot.payment_gateways import PaymentGateway
from app.bot.routers.misc.keyboard import (
    back_button,
    back_to_main_menu_button,
    close_notification_button,
)
from app.bot.utils.constants import Currency
from app.bot.utils.formatting import format_device_count, format_subscription_period
from app.bot.utils.navigation import NavDownload, NavMain, NavSubscription
from app.db.models import Server


def change_subscription_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=_("subscription:button:change"),
        callback_data=NavSubscription.CHANGE,
    )


def subscription_keyboard(
    has_subscription: bool,
    callback_data: SubscriptionData,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if not has_subscription:
        buy_cb = callback_data.model_copy(deep=True)
        buy_cb.state = NavSubscription.PROCESS 
        buy_cb.is_change = False
        buy_cb.is_extend = False
        builder.button(
            text=_("subscription:button:buy"),
            callback_data=buy_cb.pack(),
        )
    else:
        extend_cb = callback_data.model_copy(deep=True)
        extend_cb.state = NavSubscription.EXTEND
        extend_cb.is_extend = True
        extend_cb.is_change = False
        builder.button(
            text=_("subscription:button:extend"),
            callback_data=extend_cb.pack(),
        )

        change_cb = callback_data.model_copy(deep=True)
        change_cb.state = NavSubscription.CHANGE
        change_cb.is_change = True
        change_cb.is_extend = False
        builder.button(
            text=_("subscription:button:change"),
            callback_data=change_cb.pack(),
        )

        change_location_cb = callback_data.model_copy(deep=True)
        change_location_cb.state = NavSubscription.CHANGE_LOCATION
        change_location_cb.is_change_location = True
        change_location_cb.is_change = False
        change_location_cb.is_extend = False
        change_location_cb.devices = 0
        change_location_cb.duration = 0
        change_location_cb.price = 0
        builder.button(
            text=_("subscription:button:change_location_only"),
            callback_data=change_location_cb.pack(),
        )

    promocode_cb = callback_data.model_copy(deep=True)
    promocode_cb.state = NavSubscription.PROMOCODE
    promocode_cb.is_change = False 
    promocode_cb.is_extend = False
    builder.button(
        text=_("subscription:button:activate_promocode"),
        callback_data=promocode_cb.pack(),
    )
    builder.adjust(1)
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def devices_keyboard(
    plans: list[Plan],
    callback_data: SubscriptionData,
    current_devices: Optional[int] = None
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    base_device_choice_cb = callback_data.model_copy(deep=True)
    base_device_choice_cb.state = NavSubscription.DEVICES 
    base_device_choice_cb.location = "" 
    base_device_choice_cb.duration = 0 

    for plan in plans:
        if plan.devices == current_devices:
            continue
            
        cb_data = callback_data.model_copy(deep=True)
        cb_data.devices = plan.devices
        cb_data.state = NavSubscription.DEVICES
        builder.row(
            InlineKeyboardButton(
            text=format_device_count(plan.devices),
                callback_data=cb_data.pack(),
            )
        )

    builder.adjust(2)
    main_sub_cb = callback_data.model_copy(deep=True) 
    main_sub_cb.state = NavSubscription.MAIN
    main_sub_cb.devices = 0 
    main_sub_cb.location = ""
    main_sub_cb.duration = 0
    builder.row(
        InlineKeyboardButton(
            text=_("misc:button:back"), 
            callback_data=main_sub_cb.pack()
        )
    )
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def duration_keyboard(
    plan_service: PlanService,
    callback_data: SubscriptionData,
    currency: str,
    prorated_prices: Optional[dict[int, float]] = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    durations = plan_service.get_durations()
    currency_obj: Currency = Currency.from_code(currency)

    base_duration_choice_cb = callback_data.model_copy(deep=True)
    base_duration_choice_cb.state = NavSubscription.DURATION 

    for duration_val in durations:
        duration_button_callback_data = base_duration_choice_cb.model_copy(deep=True)
        duration_button_callback_data.duration = duration_val
        
        period = format_subscription_period(duration_val)
        plan = plan_service.get_plan(duration_button_callback_data.devices) 
        
        if not plan:
            continue

        display_price: Optional[float] = None
        final_price_for_callback: Optional[float] = None

        if callback_data.is_change and prorated_prices is not None and duration_val in prorated_prices:
            display_price = prorated_prices[duration_val]
            final_price_for_callback = display_price 
        else:
            standard_price = plan.get_price(currency=currency_obj, duration=duration_val)
            display_price = standard_price
            final_price_for_callback = standard_price

        if final_price_for_callback is not None:
            duration_button_callback_data.price = round(final_price_for_callback, 2)
        builder.button(
                text=f"{period} | {display_price:.2f} {currency_obj.symbol}",
                callback_data=duration_button_callback_data.pack(),
        )
    builder.adjust(2)

    if callback_data.is_extend:
        main_sub_cb = callback_data.model_copy(deep=True)
        main_sub_cb.state = NavSubscription.MAIN
        main_sub_cb.devices = 0 
        main_sub_cb.location = ""
        main_sub_cb.duration = 0
        main_sub_cb.is_extend = False
        main_sub_cb.is_change = False
        builder.row(
            InlineKeyboardButton(
                text=_("misc:button:back"),
                callback_data=main_sub_cb.pack()
            )
        )
    elif callback_data.is_change:
        back_to_devices_cb = callback_data.model_copy(deep=True)
        back_to_devices_cb.state = NavSubscription.DEVICES
        back_to_devices_cb.devices = 0
        back_to_devices_cb.location = ""
        back_to_devices_cb.duration = 0
        builder.row(
            InlineKeyboardButton(
                text=_("subscription:button:back_to_devices"),
                callback_data=back_to_devices_cb.pack(),
            )
        )
    else:
        back_to_location_cb = callback_data.model_copy(deep=True) 
        back_to_location_cb.state = NavSubscription.LOCATION
        back_to_location_cb.location = ""
        back_to_location_cb.duration = 0
        
        builder.row(
            InlineKeyboardButton(
                text=_("subscription:button:back_to_location"),
                callback_data=back_to_location_cb.pack(),
            )
        )
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def pay_keyboard(pay_url: str, callback_data: SubscriptionData) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text=_("subscription:button:pay"), url=pay_url))

    callback_data.state = NavSubscription.DURATION
    builder.row(
        back_button(
            callback_data.pack(),
            text=_("subscription:button:change_payment_method"),
        )
    )
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def payment_method_keyboard(
    plan: Plan,
    callback_data: SubscriptionData,
    gateways: list[PaymentGateway],
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    base_gateway_choice_cb = callback_data.model_copy(deep=True)

    for gateway in gateways:
        price = plan.get_price(currency=gateway.currency, duration=base_gateway_choice_cb.duration)
        if price is None:
            continue
        gateway_button_callback = base_gateway_choice_cb.model_copy(deep=True)
        gateway_button_callback.state = gateway.callback 
        builder.row(
            InlineKeyboardButton(
                text=f"{gateway.name} | {price} {gateway.currency.symbol}",
                callback_data=gateway_button_callback.pack(),
            )
        )

    back_to_duration_callback = callback_data.model_copy(deep=True) 
    back_to_duration_callback.state = NavSubscription.DURATION 
    back_to_duration_callback.duration = 0 

    builder.row(
        InlineKeyboardButton(
            text=_("subscription:button:change_duration"),
            callback_data=back_to_duration_callback.pack(),
        )
    )
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def payment_success_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=_("subscription:button:download_app"),
            callback_data=NavMain.REDIRECT_TO_DOWNLOAD,
        )
    )

    builder.row(close_notification_button())
    return builder.as_markup()


def trial_success_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=_("subscription:button:connect"),
            callback_data=NavDownload.MAIN,
        )
    )

    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def promocode_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(back_button(NavSubscription.MAIN))
    builder.row(back_to_main_menu_button())
    return builder.as_markup()


def location_keyboard(
    servers: List[Server], 
    callback_data: SubscriptionData,
    current_location: Optional[str] = None
) -> InlineKeyboardMarkup: 
    builder = InlineKeyboardBuilder()

    unique_location_names = sorted(list(set(s.location for s in servers if s.location and s.online)))

    base_location_choice_cb = callback_data.model_copy(deep=True)
    base_location_choice_cb.state = NavSubscription.LOCATION
    base_location_choice_cb.duration = 0 
    
    for idx, location_name in enumerate(unique_location_names):
        if location_name == current_location:
            continue

        cb_data = base_location_choice_cb.model_copy(deep=True)
        cb_data.location = str(idx) 
        
        builder.row(
            InlineKeyboardButton(
                text=location_name, 
                callback_data=cb_data.pack(),
            )
        )
    builder.adjust(1)

    back_cb = callback_data.model_copy(deep=True)
    if callback_data.is_change_location:
        back_cb.state = NavSubscription.MAIN
        back_cb.is_change_location = False
        back_cb.devices = 0 
        back_cb.location = ""
    elif callback_data.is_change:
        back_cb.state = NavSubscription.DEVICES
        back_cb.devices = 0
        back_cb.location = ""
    else:
        back_cb.state = NavSubscription.DEVICES
        back_cb.devices = 0
        back_cb.location = ""
    builder.row(
        InlineKeyboardButton(
            text=_("misc:button:back"), 
            callback_data=back_cb.pack(),
        )
    )
    builder.row(back_to_main_menu_button())
    return builder.as_markup()
