"""Shared Home Assistant device identity for FlyCatcher wireless sensors."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ResideoCoordinator
from .protocol.rooms import RoomAccessory


class ResideoRoomEntity(CoordinatorEntity[ResideoCoordinator]):
    """A read-only room-sensor child of its owning FlyCatcher thermostat."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ResideoCoordinator, thermostat_id: str,
        accessory: RoomAccessory, suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self.thermostat_id = thermostat_id
        self.accessory_key = accessory.key
        self._attr_unique_id = f"{thermostat_id}_room_sensor_{accessory.key}_{suffix}"
        # Room platforms can add entities before the climate platform does.
        parent = dr.async_get(coordinator.hass).async_get_or_create(
            config_entry_id=coordinator.config_entry.entry_id,
            identifiers={(DOMAIN, thermostat_id)},
        )
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, f"{thermostat_id}:room_sensor:{accessory.key}")},
            via_device_id=parent.id,
            name=accessory.name,
            manufacturer="Resideo / Honeywell Home",
            model=accessory.model,
        )

    @property
    def thermostat(self):
        return (self.coordinator.data or {}).get(self.thermostat_id)

    @property
    def accessory(self) -> RoomAccessory | None:
        device = self.thermostat
        return device.room_accessories.get(self.accessory_key) if device else None

    @property
    def available(self) -> bool:
        device = self.thermostat
        accessory = self.accessory
        return bool(super().available and device and device.online and accessory and accessory.online)

    @property
    def extra_state_attributes(self) -> dict:
        accessory = self.accessory
        if not accessory:
            return {}
        return {
            "room": accessory.room_name,
            "excluded_from_temperature_priority": accessory.exclude_temp,
            "excluded_from_motion_priority": accessory.exclude_motion,
        }
