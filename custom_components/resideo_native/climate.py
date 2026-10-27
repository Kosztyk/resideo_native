"""Thermostat climate entities, with capability-based modes and safe setpoints."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEFAULT_HOLD, DEFAULT_HOLD, DOMAIN, SCHEDULE_EDITOR_PATH
from .coordinator import ResideoCoordinator
from .schedule_entity import ScheduleEntityMixin, register_schedule_actions
from .protocol import Thermostat

MODE_MAP = {
    "Off": HVACMode.OFF,
    "Heat": HVACMode.HEAT,
    "Cool": HVACMode.COOL,
    "Auto": HVACMode.HEAT_COOL,
    "AutoHeat": HVACMode.HEAT_COOL,
    "AutoCool": HVACMode.HEAT_COOL,
    "EmergencyHeat": HVACMode.HEAT,
}
HOLD_MAP = {
    PRESET_NONE: "NoHold",
    "temporary_hold": "TemporaryHold",
    "permanent_hold": "PermanentHold",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    register_schedule_actions(False)
    coordinator: ResideoCoordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_devices() -> None:
        added = []
        for device_id in coordinator.data or {}:
            if device_id not in known:
                known.add(device_id)
                added.append(ResideoThermostat(coordinator, device_id))
        if added:
            async_add_entities(added)

    add_devices()
    entry.async_on_unload(coordinator.async_add_listener(add_devices))


class ResideoThermostat(ScheduleEntityMixin, CoordinatorEntity[ResideoCoordinator], ClimateEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "thermostat"
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator: ResideoCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self.device_id = device_id
        device = self.device
        self._attr_unique_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.name,
            manufacturer="Resideo / Honeywell Home",
            model=device.model,
            sw_version=device.raw.get("firmwareVersion") or device.raw.get("thermostatVersion"),
            configuration_url=f"homeassistant:/{SCHEDULE_EDITOR_PATH}?config_entry={coordinator.config_entry.entry_id}",
        )

    @property
    def device(self) -> Thermostat | None:
        return (self.coordinator.data or {}).get(self.device_id)

    @property
    def available(self) -> bool:
        return bool(super().available and self.device and self.device.online and self.device.unit)

    @property
    def supported_features(self) -> ClimateEntityFeature:
        features = ClimateEntityFeature.PRESET_MODE
        if self.hvac_mode == HVACMode.HEAT_COOL:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        else:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if HVACMode.OFF in self.hvac_modes:
            features |= ClimateEntityFeature.TURN_OFF
        if HVACMode.HEAT in self.hvac_modes or HVACMode.COOL in self.hvac_modes:
            features |= ClimateEntityFeature.TURN_ON
        return features

    @property
    def temperature_unit(self) -> str:
        return (
            UnitOfTemperature.FAHRENHEIT
            if self.device and self.device.unit == "Fahrenheit"
            else UnitOfTemperature.CELSIUS
        )

    @property
    def target_temperature_step(self) -> float:
        return 1 if self.temperature_unit == UnitOfTemperature.FAHRENHEIT else 0.5

    @property
    def current_temperature(self) -> float | None:
        return self.device.current_temperature if self.device and self.device.unit else None

    @property
    def current_humidity(self) -> int | None:
        humidity = self.device.humidity if self.device else None
        return round(humidity) if humidity is not None else None

    @property
    def hvac_mode(self) -> HVACMode | None:
        return MODE_MAP.get(self.device.mode) if self.device else None

    @property
    def hvac_modes(self) -> list[HVACMode]:
        if not self.device:
            return []
        return list(
            dict.fromkeys(
                MODE_MAP[mode]
                for mode in self.device.allowed_modes
                if mode in ("Off", "Heat", "Cool", "Auto")
            )
        )

    @property
    def hvac_action(self) -> HVACAction | None:
        if not self.device:
            return None
        # Report the thermostat's own operating status. Do not infer heating
        # from the target temperature: T6 uses TPI / boiler cycle control.
        operation = (self.device.operation or "").lower()
        action = {
            "heat": HVACAction.HEATING,
            "heating": HVACAction.HEATING,
            "cool": HVACAction.COOLING,
            "cooling": HVACAction.COOLING,
            "fan": HVACAction.FAN,
            "idle": HVACAction.IDLE,
        }.get(operation)
        if action:
            return action
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if operation in ("off", "none"):
            return HVACAction.IDLE
        return None

    def _temperature_kind(self) -> str | None:
        if not self.device:
            return None
        if self.hvac_mode == HVACMode.COOL:
            return "cool"
        if self.hvac_mode == HVACMode.HEAT:
            return "heat"
        if self.hvac_mode == HVACMode.OFF:
            previous = self.device.values.get("heatCoolMode")
            if previous == "Cool":
                return "cool"
            if (
                previous == "Heat"
                or "Heat" in self.device.allowed_modes
                and "Cool" not in self.device.allowed_modes
            ):
                return "heat"
        return None

    @property
    def target_temperature(self) -> float | None:
        kind = self._temperature_kind()
        return self.device.setpoint(kind) if kind and self.device else None

    @property
    def target_temperature_low(self) -> float | None:
        return (
            self.device.setpoint("heat")
            if self.device and self.hvac_mode == HVACMode.HEAT_COOL
            else None
        )

    @property
    def target_temperature_high(self) -> float | None:
        return (
            self.device.setpoint("cool")
            if self.device and self.hvac_mode == HVACMode.HEAT_COOL
            else None
        )

    @property
    def min_temp(self) -> float:
        kind = self._temperature_kind() or "heat"
        low = self.device.temperature_limits(kind)[0] if self.device else None
        return low if low is not None else super().min_temp

    @property
    def max_temp(self) -> float:
        kind = (
            "cool" if self.hvac_mode == HVACMode.HEAT_COOL else self._temperature_kind() or "heat"
        )
        high = self.device.temperature_limits(kind)[1] if self.device else None
        return high if high is not None else super().max_temp

    @property
    def preset_mode(self) -> str | None:
        if not self.device:
            return None
        status = self.device.values.get("thermostatSetpointStatus")
        if status == "HoldUntil":
            return "temporary_hold"
        return next((preset for preset, value in HOLD_MAP.items() if value == status), None)

    @property
    def preset_modes(self) -> list[str]:
        return list(HOLD_MAP)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.device:
            return {}
        return {
            "resideo_mode": self.device.mode,
            "operation_status": self.device.operation,
            "hold_status": self.device.values.get("thermostatSetpointStatus"),
            "hold_until": self.device.values.get("holdUntil"),
            "schedule_status": self.device.raw.get("scheduleStatus"),
            "next_period_time": self.device.values.get("nextPeriodTime"),
        }

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if not self.device:
            raise HomeAssistantError("The thermostat is unavailable")
        native = {
            HVACMode.OFF: "Off",
            HVACMode.HEAT: "Heat",
            HVACMode.COOL: "Cool",
            HVACMode.HEAT_COOL: "Auto",
        }.get(hvac_mode)
        if native not in self.device.allowed_modes:
            raise HomeAssistantError("This operating mode is not supported by the thermostat")
        await self.coordinator.async_command(
            self.coordinator.client.set_mode(self.device_id, native)
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if not self.device:
            raise HomeAssistantError("The thermostat is unavailable")
        requested_mode = kwargs.get("hvac_mode")
        if requested_mode is not None and requested_mode != self.hvac_mode:
            raise HomeAssistantError(
                "Set the thermostat's HVAC mode before changing its temperature"
            )
        hold = (
            "PermanentHold"
            if self.preset_mode == "permanent_hold"
            else self.coordinator.config_entry.options.get(CONF_DEFAULT_HOLD, DEFAULT_HOLD)
        )
        if self.hvac_mode == HVACMode.HEAT_COOL:
            heat = kwargs.get("target_temp_low", self.target_temperature_low)
            cool = kwargs.get("target_temp_high", self.target_temperature_high)
            if ATTR_TEMPERATURE in kwargs:
                raise HomeAssistantError("Set the low and high temperatures in automatic mode")
            await self.coordinator.async_command(
                self.coordinator.client.set_temperature(
                    self.device_id, heat=heat, cool=cool, hold=hold
                )
            )
            return
        temperature = kwargs.get(ATTR_TEMPERATURE)
        kind = self._temperature_kind()
        if temperature is None or kind is None:
            raise HomeAssistantError("Set a temperature in heating or cooling mode")
        await self.coordinator.async_command(
            self.coordinator.client.set_temperature(
                self.device_id, **{kind: temperature}, hold=hold
            )
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode not in HOLD_MAP:
            raise HomeAssistantError("Unsupported thermostat preset")
        await self.coordinator.async_command(
            self.coordinator.client.set_hold(self.device_id, HOLD_MAP[preset_mode])
        )

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        if self.hvac_mode in self.hvac_modes and self.hvac_mode != HVACMode.OFF:
            return
        preferred = HVACMode.COOL if self._temperature_kind() == "cool" else HVACMode.HEAT
        for mode in (preferred, HVACMode.HEAT, HVACMode.COOL):
            if mode in self.hvac_modes:
                await self.async_set_hvac_mode(mode)
                return
        raise HomeAssistantError("No supported heating or cooling mode is available")
