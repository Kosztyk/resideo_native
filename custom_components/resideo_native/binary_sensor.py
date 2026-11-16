"""Read-only motion, occupancy, battery and connectivity from wireless rooms."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ResideoCoordinator
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
    def add_rooms():
        entities = []
        for thermostat_id, device in (coordinator.data or {}).items():
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

    add_rooms()
    entry.async_on_unload(coordinator.async_add_listener(add_rooms))


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
