"""Response-returning schedule actions shared by climate and water heater."""

from __future__ import annotations

from urllib.parse import urlencode

import probatio as vol

from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, SCHEDULE_EDITOR_PATH
from .protocol import AuthenticationError, ResideoError


def schedule_editor_url(hass, coordinator, device_id, *, mode=None):
    query = {"config_entry": coordinator.config_entry.entry_id}
    entity = er.async_get(hass).async_get_entity_id("climate", DOMAIN, device_id)
    if entity:
        query["entity"] = entity
    if mode in ("Geofence", "Timed"):
        query["mode"] = mode
    return f"{SCHEDULE_EDITOR_PATH}?{urlencode(query)}"


def register_schedule_actions(hot_water: bool) -> None:
    kind = "hot_water" if hot_water else "heating"
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        f"get_{kind}_schedule",
        {},
        "async_get_resideo_schedule",
        supports_response=SupportsResponse.ONLY,
    )
    platform.async_register_entity_service(
        f"set_{kind}_schedule",
        {
            vol.Required("days"): dict,
            vol.Required("expected_revision"): str,
            vol.Optional("confirm_conversion", default=False): bool,
        },
        "async_set_resideo_schedule",
        supports_response=SupportsResponse.ONLY,
    )
    if not hot_water:
        platform.async_register_entity_service(
            "set_heating_schedule_mode",
            {vol.Required("mode"): vol.In(("Timed", "Geofence")),
             vol.Required("expected_revision"): str,
             vol.Optional("confirm_change", default=False): bool,
             vol.Optional("days"): dict, vol.Optional("geofence"): dict},
            "async_set_resideo_schedule_mode", supports_response=SupportsResponse.ONLY,
        )
        platform.async_register_entity_service(
            "set_heating_schedule_enabled",
            {vol.Required("enabled"): bool, vol.Required("expected_revision"): str},
            "async_set_resideo_schedule_enabled", supports_response=SupportsResponse.ONLY,
        )


class ScheduleEntityMixin:
    _schedule_hot_water = False

    async def _schedule_call(
        self, days=None, expected_revision=None, confirm_conversion=False
    ):
        client = self.coordinator.client
        try:
            if days is None:
                result = await client.get_schedule(
                    self.device_id, hot_water=self._schedule_hot_water
                )
                if not self._schedule_hot_water:
                    self.coordinator.async_note_schedule(self.device_id, result)
                return result
            result = await client.set_schedule(
                self.device_id,
                days,
                expected_revision,
                hot_water=self._schedule_hot_water,
                **({"confirm_conversion": True} if confirm_conversion else {}),
            )
            if not self._schedule_hot_water:
                self.coordinator.async_note_schedule(self.device_id, result)
            await self.coordinator.async_request_refresh()
            return result
        except AuthenticationError as err:
            if self.coordinator.config_entry:
                self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError("Sign in to Resideo again") from err
        except ResideoError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_get_resideo_schedule(self):
        return await self._schedule_call()

    async def async_set_resideo_schedule(
        self, days, expected_revision, confirm_conversion=False
    ):
        return await self._schedule_call(days, expected_revision, confirm_conversion)

    async def _schedule_control(self, command):
        try:
            result = await command
            self.coordinator.async_note_schedule(self.device_id, result)
            await self.coordinator.async_request_refresh()
            if result.get("schedule_controls_supported"):
                device = (self.coordinator.data or {}).get(self.device_id)
                status = device.values.get("thermostatSetpointStatus") if device else None
                following = (device.schedule_enabled and status == "NoHold") if self.coordinator.last_update_success and device and device.schedule_enabled is not None and status in ("NoHold", "PermanentHold", "TemporaryHold", "HoldUntil") else None
                result = {**result, "schedule_following": following}
            return result
        except AuthenticationError as err:
            if self.coordinator.config_entry:
                self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError("Sign in to Resideo again") from err
        except ResideoError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_set_resideo_schedule_mode(self, mode, expected_revision, confirm_change=False, days=None, geofence=None):
        return await self._schedule_control(self.coordinator.client.set_schedule_mode(
            self.device_id, mode, expected_revision, confirm_change=confirm_change,
            days=days, geofence=geofence,
        ))

    async def async_set_resideo_schedule_enabled(self, enabled, expected_revision):
        return await self._schedule_control(self.coordinator.client.set_schedule_enabled(
            self.device_id, enabled, expected_revision,
        ))
