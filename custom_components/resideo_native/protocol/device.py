"""Interpret the legacy CHAPI thermostat model recovered from APK 6.21.1."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from .errors import CommandError, InvalidResponse

# APK framework/utils/r.java and p373qi/d.java g()/u(): these legacy
# models exchange absolute temperatures in Fahrenheit. thermostat.units is
# the preferred display setting, also retained in outgoing command bodies.
_FAHRENHEIT_WIRE_MODELS = frozenset(
    {"flycatcher", "jasper", "storm", "focus pro", "houdini", "blackbeard"}
)


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if isfinite(result) else None
    except (TypeError, ValueError):
        return None


@dataclass
class Thermostat:
    location_id: str
    location_name: str
    device_id: str
    raw: dict[str, Any]

    @property
    def name(self) -> str:
        settings = self.raw.get("deviceSettings") or {}
        return str(
            self.raw.get("userDefinedDeviceName")
            or settings.get("userDefinedName")
            or self.raw.get("name")
            or "Thermostat"
        )

    @property
    def model(self) -> str:
        return str(
            self.raw.get("deviceModel") or self.raw.get("deviceType") or "Honeywell Home thermostat"
        )

    @property
    def thermostat(self) -> dict[str, Any]:
        return self.raw.get("thermostat") or {}

    @property
    def values(self) -> dict[str, Any]:
        return self.thermostat.get("changeableValues") or {}

    @property
    def unit(self) -> str | None:
        """Preferred display unit, not necessarily the API's numeric unit."""
        units = self.thermostat.get("units")
        return units if units in ("Celsius", "Fahrenheit") else None

    @property
    def wire_unit(self) -> str | None:
        """Match the native app's model-specific temperature encoding."""
        model = self.raw.get("deviceType") or self.raw.get("deviceModel") or ""
        if self.unit and str(model).strip().casefold() in _FAHRENHEIT_WIRE_MODELS:
            return "Fahrenheit"
        return self.unit

    def _temperature_from_wire(self, value: Any) -> float | None:
        temperature = number(value)
        if temperature is None or self.unit is None:
            return None
        if self.wire_unit == "Fahrenheit" and self.unit == "Celsius":
            return round((temperature - 32) * 5 / 9, 6)
        return temperature

    def temperature_to_wire(self, value: float) -> float:
        """Encode a validated setpoint in the same way as the official app."""
        if self.wire_unit == "Fahrenheit" and self.unit == "Celsius":
            return round(value * 9 / 5 + 32, 6)
        return value

    @property
    def online(self) -> bool:
        # Missing status is not interpreted as explicitly disconnected.
        return self.raw.get("isAlive") is not False

    @property
    def current_temperature(self) -> float | None:
        return self._temperature_from_wire(self.thermostat.get("indoorTemperature"))

    def setpoint(self, kind: str) -> float | None:
        return self._temperature_from_wire(self.values.get(f"{kind}Setpoint"))

    @property
    def humidity(self) -> float | None:
        if self.raw.get("displayIndoorHumidity") is False:
            return None
        value = number(self.thermostat.get("indoorHumidity"))
        return value if value is not None and 0 <= value <= 100 else None

    @property
    def mode(self) -> str | None:
        if self.values.get("autoChangeoverActive") is True:
            return "Auto"
        value = self.values.get("mode")
        return value if isinstance(value, str) else None

    @property
    def allowed_modes(self) -> list[str]:
        modes = self.thermostat.get("allowedModes")
        if isinstance(modes, list):
            return [mode for mode in modes if isinstance(mode, str)]
        return [self.mode] if self.mode else []

    @property
    def operation(self) -> str | None:
        status = self.thermostat.get("operationStatus") or {}
        mode = status.get("mode")
        return mode if isinstance(mode, str) else None

    def temperature_limits(self, kind: str) -> tuple[float | None, float | None]:
        prefix = "Heat" if kind == "heat" else "Cool"
        return self._temperature_from_wire(
            self.thermostat.get(f"min{prefix}Setpoint")
        ), self._temperature_from_wire(self.thermostat.get(f"max{prefix}Setpoint"))

    def validate_temperature(self, temperature: Any, kind: str) -> float:
        value = number(temperature)
        if value is None or self.unit is None:
            raise CommandError("A valid temperature and thermostat temperature unit are required")
        low, high = self.temperature_limits(kind)
        # Refuse commands when a server schema change removes safety bounds.
        if low is None or high is None or low > high:
            raise CommandError("Resideo did not report valid temperature limits")
        if not low <= value <= high:
            raise CommandError("Requested temperature is outside the thermostat's limits")
        if not self.online:
            raise CommandError("The thermostat is offline")
        return value


def parse_locations(payload: Any) -> dict[str, Thermostat]:
    """Parse api/v4/locations (a top-level array), ignoring other products."""
    if not isinstance(payload, list):
        raise InvalidResponse("Resideo returned an unexpected locations response")
    result: dict[str, Thermostat] = {}
    for location in payload:
        if not isinstance(location, dict):
            raise InvalidResponse("Resideo returned an invalid location")
        devices = location.get("devices", [])
        if not isinstance(devices, list):
            raise InvalidResponse("Resideo returned an invalid device list")
        location_id = location.get("locationID")
        for raw in devices:
            if not isinstance(raw, dict) or str(raw.get("deviceClass", "")).lower() != "thermostat":
                continue
            device_id = raw.get("deviceID")
            thermostat = raw.get("thermostat")
            if location_id is None or not device_id or not isinstance(thermostat, dict):
                # Do not expose devices routed to the newer Titan schema.
                continue
            if not isinstance(thermostat.get("changeableValues", {}), dict):
                raise InvalidResponse("Resideo returned invalid thermostat values")
            identifier = str(device_id)
            result[identifier] = Thermostat(
                str(location_id), str(location.get("name", "")), identifier, raw
            )
    return result
