"""Shared entity behavior for a thermostat's nested domestic hot-water zone."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SCHEDULE_EDITOR_PATH
from .coordinator import ResideoCoordinator
from .protocol.hot_water import HotWaterZone


class ResideoHotWaterEntity(CoordinatorEntity[ResideoCoordinator]):
    """Attach DHW entities to the existing thermostat device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ResideoCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self.device_id = device_id
        device = coordinator.data[device_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.name,
            manufacturer="Resideo / Honeywell Home",
            model=device.model,
            sw_version=device.raw.get("firmwareVersion")
            or device.raw.get("thermostatVersion"),
            configuration_url=f"homeassistant:/{SCHEDULE_EDITOR_PATH}?config_entry={coordinator.config_entry.entry_id}",
        )

    @property
    def zone(self) -> HotWaterZone | None:
        device = (self.coordinator.data or {}).get(self.device_id)
        return device.hot_water if device else None

    @property
    def available(self) -> bool:
        zone = self.zone
        return bool(super().available and zone and zone.online)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.zone.attributes if self.zone else {}
