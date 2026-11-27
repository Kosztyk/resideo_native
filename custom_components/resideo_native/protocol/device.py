"""Interpret the legacy CHAPI thermostat model recovered from APK 6.21.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any

from .errors import CommandError, InvalidResponse
from .hot_water import HotWaterZone
from .rooms import RoomAccessory, RoomPriority

# APK framework/utils/r.java and p373qi/d.java g()/u(): these legacy
# models exchange absolute temperatures in Fahrenheit. thermostat.units is
# the preferred display setting, also retained in outgoing command bodies.
_FAHRENHEIT_WIRE_MODELS = frozenset(
    {"flycatcher", "jasper", "storm", "focus pro", "houdini", "blackbeard"}
)


# Android 6.21.2 fan endpoint; FollowSchedule is intentionally not writable
# until its schedule/hold semantics are verified on hardware.
FAN_MODE_MAP = {"Auto": "auto", "On": "on", "Circulate": "diffuse"}
HA_TO_NATIVE_FAN_MODE = {ha: native for native, ha in FAN_MODE_MAP.items()}
_NON_JASPER_FAN_FAMILIES = _FAHRENHEIT_WIRE_MODELS - {"jasper"}
_GENERIC_DEVICE_TYPES = frozenset({"", "thermostat", "stat", "unknown", "lcc", "tcc"})


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _reported_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


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
    room_accessories: dict[str, RoomAccessory] = field(default_factory=dict)
    room_priority: RoomPriority | None = None

    @property
    def supports_rooms(self) -> bool:
        """The Android application exposes rooms for FlyCatcher-family models."""
        return any(
            str(self.raw.get(field) or "").strip().casefold().startswith("flycatcher")
            for field in ("deviceType", "deviceModel")
        )

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
        models = (self.raw.get("deviceType"), self.raw.get("deviceModel"))
        if self.unit and any(
            (model_name := str(model or "").strip().casefold()) in _FAHRENHEIT_WIRE_MODELS
            or model_name.startswith("flycatcher")
            for model in models
        ):
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
    def hot_water(self) -> HotWaterZone | None:
        """Expose a nested DHW zone without adding it to the thermostat list."""
        zone = self.raw.get("dhwZone")
        if not isinstance(zone, dict) or not isinstance(zone.get("dhw"), dict):
            return None
        identifier = zone.get("deviceId") or zone.get("deviceID")
        if not isinstance(identifier, str) or not identifier.strip():
            return None
        if str(zone.get("deviceClass", "DHW")).casefold() != "dhw":
            return None
        return HotWaterZone(self, zone)

    @property
    def current_temperature(self) -> float | None:
        return self._temperature_from_wire(self.thermostat.get("indoorTemperature"))

    def setpoint(self, kind: str) -> float | None:
        value = self.values.get(f"{kind}Setpoint")
        # FlyCatcher can briefly report 0 °F while applying a priority change.
        if self.supports_rooms and number(value) == 0:
            return None
        return self._temperature_from_wire(value)

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

    @property
    def fan_settings(self) -> dict[str, Any]:
        """Legacy StatDeviceResponse.settings.fan (APK 6.21.2)."""
        return _mapping(_mapping(self.raw.get("settings")).get("fan"))

    @property
    def allowed_fan_modes(self) -> list[str]:
        modes = self.fan_settings.get("allowedModes")
        if not isinstance(modes, list):
            return []
        return list(dict.fromkeys(
            mode for mode in modes if isinstance(mode, str) and mode in FAN_MODE_MAP
        ))

    @property
    def fan_mode(self) -> str | None:
        mode = _mapping(self.fan_settings.get("changeableValues")).get("mode")
        return mode if isinstance(mode, str) and mode in (*FAN_MODE_MAP, "FollowSchedule") else None

    @property
    def can_control_fan(self) -> bool:
        """Require an explicit Jasper identifier and no conflicting known family."""
        def normalize(value: Any) -> str:
            return value.strip().casefold() if isinstance(value, str) else ""

        raw_type = self.raw.get("deviceType")
        raw_model = self.raw.get("deviceModel")
        if any(value is not None and not isinstance(value, str) for value in (raw_type, raw_model)):
            return False
        device_type = normalize(raw_type)
        device_model = normalize(raw_model)
        if any(
            model in _NON_JASPER_FAN_FAMILIES or model.startswith("flycatcher")
            for model in (device_type, device_model)
        ):
            return False
        # A generic type must not hide an explicit Jasper model. An unfamiliar
        # non-generic type is not proof that Jasper's hold semantics apply.
        is_jasper = device_type == "jasper" or (
            device_type in _GENERIC_DEVICE_TYPES and device_model == "jasper"
        )
        return is_jasper and bool(self.allowed_fan_modes)

    @property
    def fan_running(self) -> bool | None:
        """Actual reported activity, not the configured mode or a demand flag."""
        return _reported_bool(self.fan_settings.get("fanRunning"))

    @property
    def fan_request(self) -> bool | None:
        return _reported_bool(_mapping(self.thermostat.get("operationStatus")).get("fanRequest"))

    @property
    def circulation_fan_request(self) -> bool | None:
        return _reported_bool(_mapping(self.thermostat.get("operationStatus")).get("circulationFanRequest"))

    @property
    def schedule_enabled(self) -> bool | None:
        """Native schedule status is separate from the thermostat's hold."""
        status = self.raw.get("scheduleStatus")
        return {"Resume": True, "Pause": False}.get(status)

    @property
    def schedule_time_step(self) -> int | None:
        """Use a reported increment; never silently round an owner's time."""
        value = self.raw.get("allowedTimeIncrements")
        if type(value) is int and 1 <= value <= 60 and 60 % value == 0:
            return value
        return None

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
