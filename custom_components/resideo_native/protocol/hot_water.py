"""Nested Jasper DHW zone reported by the legacy mobile locations API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .device import Thermostat

DHW_BOOST_MINUTES = (30, 60, 90)
DHW_MODES = ("auto", "on", "off", "boost")


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _boolean(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


@dataclass
class HotWaterZone:
    """DHW shares its parent thermostat's command address and connection."""

    thermostat: Thermostat
    raw: dict[str, Any]

    @property
    def values(self) -> dict[str, Any]:
        return self.raw["dhw"]

    @property
    def online(self) -> bool:
        return self.thermostat.online and self.raw.get("isAlive") is not False

    @property
    def can_control(self) -> bool:
        """Enable only the legacy model whose app command flow was traced."""
        model = self.thermostat.raw.get("deviceType") or self.thermostat.model
        return str(model).strip().casefold() == "jasper"

    @property
    def state(self) -> str | None:
        value = self.values.get("dhwState")
        return value if value in ("On", "Off") else None

    @property
    def status(self) -> str | None:
        return _text(self.values.get("status"))

    @property
    def operation_mode(self) -> str | None:
        """Keep schedule selection distinct from its current on/off state."""
        if self.status == "NoHold":
            return "auto"
        if self.status == "TemporaryHold" and self.state == "On":
            return "boost"
        if self.status in ("PermanentHold", "TemporaryHold") and self.state:
            return self.state.lower()
        # Vacation or a future status must not be presented as a manual mode.
        return None

    @property
    def attributes(self) -> dict[str, Any]:
        """Whitelisted status fields, without account or device identifiers."""
        vacation = self.values.get("vacationHold")
        schedule = self.raw.get("currentSchedulePeriod")
        duration = self.values.get("boostDuration")
        return {
            "dhw_state": self.state,
            "status": self.status,
            "boost_duration": duration
            if type(duration) is int and duration >= 0
            else None,
            "vacation_hold_enabled": (
                _boolean(vacation.get("enabled"))
                if isinstance(vacation, dict)
                else None
            ),
            "geo_boost_enabled": _boolean(self.values.get("geoBoostEnabled")),
            "next_period_time": _text(self.values.get("nextPeriodTime")),
            "schedule_day": _text(schedule.get("day"))
            if isinstance(schedule, dict)
            else None,
            "schedule_period": (
                _text(schedule.get("period")) if isinstance(schedule, dict) else None
            ),
        }
