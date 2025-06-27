import time

from aiogram.utils.i18n import gettext as _

from app.bot.utils.constants import UNLIMITED
from app.bot.utils.formatting import format_remaining_time, format_size
from app.bot.utils.time import get_current_timestamp


class ClientData:
    def __init__(
        self,
        max_devices: int,
        traffic_total: int,
        traffic_remaining: int,
        traffic_used: int,
        traffic_up: int,
        traffic_down: int,
        expiry_timestamp: int,
        expiry_time_str: str,
    ) -> None:
        self._max_devices = max_devices
        self._traffic_total = traffic_total
        self._traffic_remaining = traffic_remaining
        self._traffic_used = traffic_used
        self._traffic_up = traffic_up
        self._traffic_down = traffic_down
        self._expiry_timestamp = expiry_timestamp
        self._expiry_time_str = expiry_time_str

    def __str__(self) -> str:
        return (
            f"ClientData(max_devices={self._max_devices}, traffic_total={self._traffic_total}, "
            f"traffic_remaining={self._traffic_remaining}, traffic_used={self._traffic_used}, "
            f"traffic_up={self._traffic_up}, traffic_down={self._traffic_down}, "
            f"expiry_timestamp={self._expiry_timestamp}, expiry_time_str={self._expiry_time_str})"
        )

    @property
    def max_devices(self) -> str:
        devices = self._max_devices
        if devices == -1:
            return UNLIMITED
        return devices

    @property
    def traffic_total(self) -> str:
        return format_size(self._traffic_total)

    @property
    def traffic_remaining(self) -> str:
        return format_size(self._traffic_remaining)

    @property
    def traffic_used(self) -> str:
        return format_size(self._traffic_used)

    @property
    def traffic_up(self) -> str:
        return format_size(self._traffic_up)

    @property
    def traffic_down(self) -> str:
        return format_size(self._traffic_down)

    @property
    def expiry_timestamp(self) -> int:
        return self._expiry_timestamp

    @property
    def expiry_time_str(self) -> str:
        return self._expiry_time_str

    @property
    def has_subscription_expired(self) -> bool:
        if self.expiry_timestamp > 0:
            return self.expiry_timestamp < get_current_timestamp()
        return False
