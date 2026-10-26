"""Resideo Native integration for legacy Resideo / Honeywell Home thermostats."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_TOKEN
from .coordinator import ResideoCoordinator
from .protocol import AuthenticationError, NativeClient, ResideoAuth, Token

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.WATER_HEATER]


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
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    # Refresh-token persistence changes entry.data. Reload only for options.
    coordinator = entry.runtime_data
    if coordinator.configured_options != dict(entry.options):
        await hass.config_entries.async_reload(entry.entry_id)
