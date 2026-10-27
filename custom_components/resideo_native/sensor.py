"""Reported on/off state of nested domestic hot-water zones."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ResideoCoordinator
from .dhw_entity import ResideoHotWaterEntity
from .const import DOMAIN
from .schedule_entity import schedule_editor_url
from .switch import supports_schedule


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ResideoCoordinator = entry.runtime_data
    known: set[str] = set()
    editors: set[str] = set()

    @callback
    def add_zones() -> None:
        added = []
        for device_id, device in (coordinator.data or {}).items():
            if device_id not in editors and supports_schedule(device):
                editors.add(device_id)
                added.append(ResideoScheduleEditor(coordinator, device_id))
            if device.hot_water and device_id not in known:
                known.add(device_id)
                added.append(ResideoHotWaterState(coordinator, device_id))
        if added:
            async_add_entities(added)

    add_zones()
    entry.async_on_unload(coordinator.async_add_listener(add_zones))


class ResideoScheduleEditor(CoordinatorEntity, SensorEntity):
    """Visible entity entry that opens this thermostat's editor when tapped."""

    _attr_has_entity_name = True
    _attr_name = "Schedule editor"
    _attr_translation_key = "schedule_editor"
    _attr_icon = "mdi:calendar-edit"
    _attr_native_value = "Open"
    _unrecorded_attributes = frozenset({"editor_url", "resideo_schedule_editor"})

    def __init__(self, coordinator, device_id):
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_unique_id = f"{device_id}_schedule_editor"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def extra_state_attributes(self):
        return {"resideo_schedule_editor": True, "editor_url": schedule_editor_url(self.hass, self.coordinator, self.device_id)}


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
