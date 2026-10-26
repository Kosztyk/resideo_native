"""Reported on/off state of nested domestic hot-water zones."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ResideoCoordinator
from .dhw_entity import ResideoHotWaterEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ResideoCoordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_zones() -> None:
        added = []
        for device_id, device in (coordinator.data or {}).items():
            if device.hot_water and device_id not in known:
                known.add(device_id)
                added.append(ResideoHotWaterState(coordinator, device_id))
        if added:
            async_add_entities(added)

    add_zones()
    entry.async_on_unload(coordinator.async_add_listener(add_zones))


class ResideoHotWaterState(ResideoHotWaterEntity, SensorEntity):
    """Reported DHW state, separate from auto/manual/boost selection."""

    _attr_translation_key = "hot_water_state"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["on", "off"]
    _attr_icon = "mdi:water-boiler"

    def __init__(self, coordinator: ResideoCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_dhw_state"

    @property
    def native_value(self) -> str | None:
        return self.zone.state.lower() if self.zone and self.zone.state else None
