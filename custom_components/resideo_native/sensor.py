"""Reported on/off state of nested domestic hot-water zones."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ResideoCoordinator
from .room_entity import ResideoRoomEntity
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
    room_entities: set[str] = set()

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
            for accessory in device.room_accessories.values():
                for key in ("temperature", "humidity", "battery_status", "rssi", "status"):
                    if getattr(accessory, key) is None:
                        continue
                    uid = f"{device_id}:{accessory.key}:{key}"
                    if uid not in room_entities:
                        room_entities.add(uid)
                        added.append(ResideoRoomSensor(coordinator, device_id, accessory, key))
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


class ResideoRoomSensor(ResideoRoomEntity, SensorEntity):
    """One measurement (or diagnostic value) per wireless room accessory."""

    _FIELDS = {
        "temperature": ("Temperature", SensorDeviceClass.TEMPERATURE, "mdi:thermometer"),
        "humidity": ("Humidity", SensorDeviceClass.HUMIDITY, "mdi:water-percent"),
        "battery_status": ("Battery status", None, "mdi:battery-heart-variant"),
        "rssi": ("Signal strength", SensorDeviceClass.SIGNAL_STRENGTH, "mdi:wifi"),
        "status": ("Sensor status", None, "mdi:information-outline"),
    }

    def __init__(self, coordinator, thermostat_id, accessory, key):
        super().__init__(coordinator, thermostat_id, accessory, key)
        self.key = key
        name, device_class, icon = self._FIELDS[key]
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_icon = icon
        if key in ("temperature", "humidity", "rssi"):
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if key in ("battery_status", "status", "rssi"):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self):
        # Report status and battery condition even when the wireless sensor is offline.
        if self.key in ("status", "battery_status"):
            device = self.thermostat
            return bool(self.coordinator.last_update_success and device and device.online and self.accessory)
        return super().available

    @property
    def native_value(self):
        accessory = self.accessory
        return getattr(accessory, self.key, None) if accessory else None

    @property
    def native_unit_of_measurement(self):
        if self.key == "temperature":
            thermostat = self.thermostat
            return UnitOfTemperature.FAHRENHEIT if thermostat and thermostat.unit == "Fahrenheit" else UnitOfTemperature.CELSIUS
        if self.key == "humidity":
            return PERCENTAGE
        if self.key == "rssi":
            return "dBm"
        return None
