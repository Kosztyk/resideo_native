"""Whitelisted diagnostics without tokens, addresses, names, or identifiers."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import VERSION


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry):
    coordinator = entry.runtime_data
    return {
        "integration_version": VERSION,
        "protocol_source": "Resideo Android 6.21.1",
        "last_update_success": coordinator.last_update_success,
        "thermostats": [
            {
                "model": device.model,
                "online": device.online,
                "units": device.unit,
                "api_temperature_units": device.wire_unit,
                "allowed_modes": device.allowed_modes,
                "mode": device.mode,
                "operation_status": device.operation,
                "hold_status": device.values.get("thermostatSetpointStatus"),
                "schedule_enabled": device.schedule_enabled,
                "schedule_time_step_minutes": device.schedule_time_step,
                "temperature_limits_heat": device.temperature_limits("heat"),
                "temperature_limits_cool": device.temperature_limits("cool"),
                "hot_water": (
                    {
                        **device.hot_water.attributes,
                        "online": device.hot_water.online,
                        "control_supported": device.hot_water.can_control,
                    }
                    if device.hot_water
                    else None
                ),
            }
            for device in (coordinator.data or {}).values()
        ],
    }
