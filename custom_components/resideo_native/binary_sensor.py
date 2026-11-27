"""Read-only wireless room and thermostat fan activity sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ResideoCoordinator
from .protocol import Thermostat
from .room_entity import ResideoRoomEntity


def _battery_low(value: str | None) -> bool | None:
    if not isinstance(value, str):
        return None
    v = value.strip().casefold().replace(" ", "").replace("_", "")
    if v in ("low", "lowbattery", "critical", "replace", "replacebattery"):
        return True
    if v in ("ok", "good", "normal", "full", "high"):
        return False
    return None


def _connected(value: str | None) -> bool | None:
    """Never guess a connection state from an unfamiliar cloud status."""
    if not isinstance(value, str):
        return None
    value = value.strip().casefold().replace(" ", "").replace("_", "")
    if value in ("ok", "good", "online", "connected", "active"):
        return True
    if value in ("offline", "disconnected", "unavailable", "lost", "notconnected"):
        return False
    return None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ResideoCoordinator = entry.runtime_data
    seen: set[str] = set()

    @callback
    def discover_binary_sensors() -> None:
        entities: list[BinarySensorEntity] = []
        for thermostat_id, device in (coordinator.data or {}).items():
            uid = f"{thermostat_id}:fan_running"
            if device.fan_running is not None and uid not in seen:
                seen.add(uid)
                entities.append(ResideoFanRunning(coordinator, thermostat_id))
            for accessory in device.room_accessories.values():
                for kind in ("motion", "occupancy", "battery_low", "connected"):
                    value = _battery_low(accessory.battery_status) if kind == "battery_low" else (
                        _connected(accessory.status) if kind == "connected" else getattr(accessory, kind)
                    )
                    if value is None:
                        continue
                    uid = f"{thermostat_id}:{accessory.key}:{kind}"
                    if uid not in seen:
                        seen.add(uid)
                        entities.append(ResideoRoomBinary(coordinator, thermostat_id, accessory, kind))
        if entities:
            async_add_entities(entities)

    discover_binary_sensors()
    entry.async_on_unload(coordinator.async_add_listener(discover_binary_sensors))


class ResideoRoomBinary(ResideoRoomEntity, BinarySensorEntity):
    _FIELDS = {
        "motion": ("Motion", BinarySensorDeviceClass.MOTION),
        "occupancy": ("Occupancy", BinarySensorDeviceClass.OCCUPANCY),
        "battery_low": ("Battery low", BinarySensorDeviceClass.BATTERY),
        "connected": ("Connected", BinarySensorDeviceClass.CONNECTIVITY),
    }

    def __init__(self, coordinator, thermostat_id, accessory, kind):
        super().__init__(coordinator, thermostat_id, accessory, kind)
        self.kind = kind
        self._attr_name, self._attr_device_class = self._FIELDS[kind]
        if kind in ("battery_low", "connected"):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self):
        if self.kind == "connected":
            device = self.thermostat
            return bool(self.coordinator.last_update_success and device and device.online and self.accessory)
        return super().available

    @property
    def is_on(self):
        accessory = self.accessory
        if accessory is None:
            return None
        if self.kind == "connected":
            return _connected(accessory.status)
        if self.kind == "battery_low":
            return _battery_low(accessory.battery_status)
        return getattr(accessory, self.kind)


class ResideoFanRunning(CoordinatorEntity[ResideoCoordinator], BinarySensorEntity):
    """Cloud-reported fan activity, independent of fan mode and HVAC mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "fan_running"
    _attr_icon = "mdi:fan"

    def __init__(self, coordinator: ResideoCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_unique_id = f"{device_id}:fan_running"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def device(self) -> Thermostat | None:
        return (self.coordinator.data or {}).get(self.device_id)

    @property
    def available(self) -> bool:
        return bool(super().available and self.device and self.device.online)

    @property
    def is_on(self) -> bool | None:
        return self.device.fan_running if self.device else None
