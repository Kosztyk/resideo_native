"""Share one account poll across all thermostats and serialize commands."""

from __future__ import annotations

import logging
from collections.abc import Coroutine
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, NAME
from .protocol import AuthenticationError, NativeClient, ResideoError, Thermostat

_LOGGER = logging.getLogger(__name__)


class ResideoCoordinator(DataUpdateCoordinator[dict[str, Thermostat]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: NativeClient) -> None:
        self.client = client
        self.configured_options = dict(entry.options)
        interval = int(entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=NAME,
            update_interval=timedelta(seconds=max(30, min(600, interval))),
        )

    async def _async_update_data(self) -> dict[str, Thermostat]:
        try:
            return await self.client.update()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ResideoError as err:
            raise UpdateFailed(str(err)) from err

    async def async_command(self, command: Coroutine[Any, Any, None]) -> None:
        try:
            await command
        except AuthenticationError as err:
            if self.config_entry:
                self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError("Sign in to Resideo again") from err
        except ResideoError as err:
            raise HomeAssistantError(str(err)) from err
        # Read back from the server instead of inventing an optimistic state.
        await self.async_request_refresh()
