"""Native heating schedule On/Off switches, independent of thermostat holds."""

from datetime import timedelta

from homeassistant.components.switch import SwitchEntity
from homeassistant.components import persistent_notification
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SHOW_SCHEDULE_SIDEBAR, DOMAIN
from .frontend import async_setup_editor
from .protocol import AuthenticationError, ResideoError
from .schedule_entity import schedule_editor_url

SCAN_INTERVAL = timedelta(seconds=60)


def supports_schedule(device):
    return (str(device.raw.get("deviceType") or device.model).casefold() == "jasper"
            and "Heat" in device.allowed_modes and "Cool" not in device.allowed_modes)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    known = set()

    @callback
    def add_devices():
        added = []
        modes = []
        for device_id, device in (coordinator.data or {}).items():
            if device_id not in known and supports_schedule(device):
                known.add(device_id)
                added.append(ResideoScheduleSwitch(coordinator, device_id))
                added.append(ResideoSidebarSwitch(coordinator, device_id))
                modes.append(ResideoGeofencingSwitch(coordinator, device_id))
        if added:
            async_add_entities(added)
        if modes:
            async_add_entities(modes, update_before_add=True)

    add_devices()
    entry.async_on_unload(coordinator.async_add_listener(add_devices))


class ResideoScheduleSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "heating_schedule"
    _attr_name = "Heating schedule"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, device_id):
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_unique_id = f"{device_id}_heating_schedule"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})
        self._verification = None

    @property
    def device(self):
        return (self.coordinator.data or {}).get(self.device_id)

    @property
    def available(self):
        return bool(super().available and self.device and self.device.online)

    @property
    def is_on(self):
        return self.device.schedule_enabled if self.device else None

    @property
    def extra_state_attributes(self):
        return {"last_command_verification": self._verification}

    async def _set_enabled(self, enabled):
        client = self.coordinator.client
        try:
            baseline = await client.get_schedule(self.device_id)
            if not baseline.get("revision") or baseline.get("write_supported") is False:
                raise HomeAssistantError("Load a supported heating routine before changing its schedule switch")
            result = await client.set_schedule_enabled(self.device_id, enabled, baseline["revision"])
            self._verification = result.get("verification_status")
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()
            if result.get("status") == "readback_unconfirmed":
                raise HomeAssistantError(result["message"])
        except AuthenticationError as err:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError("Sign in to Resideo again") from err
        except ResideoError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_turn_on(self, **kwargs):
        await self._set_enabled(True)

    async def async_turn_off(self, **kwargs):
        await self._set_enabled(False)


class ResideoSidebarSwitch(SwitchEntity):
    """A persisted account preference exposed beside each thermostat control."""

    _attr_has_entity_name = True
    _attr_translation_key = "schedule_sidebar"
    _attr_name = "Add scheduler to sidebar"
    _attr_icon = "mdi:page-layout-sidebar-left"
    _attr_should_poll = False

    def __init__(self, coordinator, device_id):
        self._entry = coordinator.config_entry
        self._attr_unique_id = f"{device_id}_schedule_sidebar"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def is_on(self):
        return self._entry.options.get(CONF_SHOW_SCHEDULE_SIDEBAR, False)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._entry.add_update_listener(self._options_updated))

    async def _options_updated(self, hass, entry):
        self.async_write_ha_state()

    async def _set_enabled(self, enabled):
        try:
            await async_setup_editor(self.hass, self._entry.entry_id, show_in_sidebar=enabled)
        except (ValueError, RuntimeError) as err:
            raise HomeAssistantError(f"Could not change the sidebar shortcut: {err}") from err
        self.hass.config_entries.async_update_entry(
            self._entry, options={**self._entry.options, CONF_SHOW_SCHEDULE_SIDEBAR: enabled},
        )
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        await self._set_enabled(True)

    async def async_turn_off(self, **kwargs):
        await self._set_enabled(False)


class ResideoGeofencingSwitch(CoordinatorEntity, SwitchEntity):
    """Observed mode; native UI toggles configure a reviewed mode-change popup."""

    _attr_has_entity_name = True
    _attr_translation_key = "geofencing"
    _attr_name = "Switch to Geofencing"
    _attr_icon = "mdi:map-marker-radius"
    _unrecorded_attributes = frozenset({"editor_url", "resideo_schedule_mode"})

    def __init__(self, coordinator, device_id):
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_unique_id = f"{device_id}_geofencing"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def should_poll(self):
        return True

    @property
    def is_on(self):
        mode = self.coordinator.schedule_modes.get(self.device_id)
        return mode == "Geofence" if mode in ("Timed", "Geofence", "None") else None

    @property
    def available(self):
        device = (self.coordinator.data or {}).get(self.device_id)
        return bool(super().available and device and device.online and self.is_on is not None)

    @property
    def extra_state_attributes(self):
        return {
            "resideo_schedule_mode": True,
            "schedule_type": self.coordinator.schedule_modes.get(self.device_id),
            "editor_url": schedule_editor_url(self.hass, self.coordinator, self.device_id),
        }

    async def async_update(self):
        try:
            result = await self.coordinator.client.get_schedule(self.device_id)
            self.coordinator.async_note_schedule(self.device_id, result)
        except ResideoError as err:
            self.coordinator.async_note_schedule(self.device_id, {})
            raise HomeAssistantError(str(err)) from err

    async def _request_setup(self, mode):
        # An automation has no browser in which to collect temperatures/periods.
        # Native HA switch interaction is handled by the local popup module.
        url = schedule_editor_url(self.hass, self.coordinator, self.device_id, mode=mode)
        persistent_notification.async_create(
            self.hass, f"[Configure {mode} scheduling]({url}), then review and save. The cloud mode has not changed.",
            title="Resideo schedule setup", notification_id=f"{DOMAIN}_mode_setup_{self.unique_id}",
        )

    async def async_turn_on(self, **kwargs):
        await self._request_setup("Geofence")

    async def async_turn_off(self, **kwargs):
        await self._request_setup("Timed")
