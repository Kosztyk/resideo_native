"""Resideo Native integration for legacy Resideo / Honeywell Home thermostats."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_DEFAULT_HOLD,
    CONF_POLL_INTERVAL,
    CONF_SHOW_SCHEDULE_SIDEBAR,
    CONF_TOKEN,
    DEFAULT_HOLD,
    DEFAULT_POLL_INTERVAL,
)
from .coordinator import ResideoCoordinator
from .frontend import async_setup_editor, async_unload_editor
from .protocol import AuthenticationError, NativeClient, ResideoAuth, Token

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.SWITCH, Platform.WATER_HEATER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load the saved authorization without retaining an account password."""
    session = async_get_clientsession(hass)

    def save_token(token: Token) -> None:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_TOKEN: token.as_dict()}
        )

    try:
        token = Token.from_storage(entry.data.get(CONF_TOKEN, {}))
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    auth = ResideoAuth(session, token, save_token)
    client = NativeClient(session, auth)
    coordinator = ResideoCoordinator(hass, entry, client)
    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain == "button" and entity.platform == "resideo_native" and entity.unique_id in {f"{device_id}_switch_to_geofencing" for device_id in coordinator.data}:
            registry.async_remove(entity.entity_id)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    try:
        await async_setup_editor(
            hass, entry.entry_id,
            show_in_sidebar=entry.options.get(CONF_SHOW_SCHEDULE_SIDEBAR, False),
        )
    except (ValueError, RuntimeError) as err:
        # A frontend path conflict must not remove working thermostat controls.
        logging.getLogger(__name__).warning("Schedule editor is unavailable: %s", err)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await async_unload_editor(hass, entry.entry_id)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    # Refresh-token persistence changes entry.data. Reload only for options.
    coordinator = entry.runtime_data
    options = dict(entry.options)
    if coordinator.configured_options == options:
        return
    defaults = {CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL, CONF_DEFAULT_HOLD: DEFAULT_HOLD}
    previous = {**defaults, **coordinator.configured_options}
    current = {**defaults, **options}
    previous.pop(CONF_SHOW_SCHEDULE_SIDEBAR, None)
    current.pop(CONF_SHOW_SCHEDULE_SIDEBAR, None)
    if previous == current:
        await async_setup_editor(
            hass, entry.entry_id,
            show_in_sidebar=options.get(CONF_SHOW_SCHEDULE_SIDEBAR, False),
        )
        coordinator.configured_options = options
        return
    await hass.config_entries.async_reload(entry.entry_id)
