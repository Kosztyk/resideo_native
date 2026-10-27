"""Schedule action schemas, entity addressing and HA response handling."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from test_hot_water_homeassistant import custom_integrations, client, entry, water_state
from custom_components.resideo_native.protocol.errors import CommandError


@pytest.mark.parametrize("hot", [False, True])
async def test_schedule_actions_return_responses(hass, entry, client, hot):
    entity = (
        water_state(hass).entity_id
        if hot
        else hass.states.async_all("climate")[0].entity_id
    )
    kind = "hot_water" if hot else "heating"
    payload = {"revision": "test-revision", "days": {"Monday": []}}
    client.get_schedule = AsyncMock(return_value=payload)
    client.set_schedule = AsyncMock(return_value=payload)
    response = await hass.services.async_call(
        "resideo_native",
        f"get_{kind}_schedule",
        {"entity_id": entity},
        blocking=True,
        return_response=True,
    )
    assert response[entity] == payload
    assert client.get_schedule.call_args.kwargs == {"hot_water": hot}
    await hass.services.async_call(
        "resideo_native",
        f"set_{kind}_schedule",
        {
            "entity_id": entity,
            "days": {"Monday": []},
            "expected_revision": "test-revision",
        },
        blocking=True,
        return_response=True,
    )
    assert client.set_schedule.call_args.args[1:] == ({"Monday": []}, "test-revision")
    assert client.set_schedule.call_args.kwargs == {"hot_water": hot}


async def test_schedule_errors_surface_in_ha(hass, entry, client):
    client.get_schedule = AsyncMock(
        side_effect=CommandError("Unexpected schedule shape")
    )
    with pytest.raises(HomeAssistantError, match="Unexpected schedule shape"):
        await hass.services.async_call(
            "resideo_native",
            "get_hot_water_schedule",
            {"entity_id": water_state(hass).entity_id},
            blocking=True,
            return_response=True,
        )


async def test_conversion_confirmation_reaches_client(hass, entry, client):
    client.set_schedule = AsyncMock(return_value={"revision": "new", "days": {}})
    entity = hass.states.async_all("climate")[0].entity_id
    await hass.services.async_call(
        "resideo_native",
        "set_heating_schedule",
        {
            "entity_id": entity,
            "days": {},
            "expected_revision": "old",
            "confirm_conversion": True,
        },
        blocking=True,
        return_response=True,
    )
    assert client.set_schedule.call_args.kwargs["confirm_conversion"] is True


async def test_schedule_control_actions_pass_parameters_and_responses(hass, entry, client):
    entity = hass.states.async_all("climate")[0].entity_id
    result = {"revision": "new", "days": {}, "schedule_following": False}
    client.set_schedule_enabled = AsyncMock(return_value=result)
    client.set_schedule_mode = AsyncMock(return_value=result)
    response = await hass.services.async_call("resideo_native", "set_heating_schedule_enabled",
        {"entity_id": entity, "enabled": False, "expected_revision": "old"}, blocking=True, return_response=True)
    assert response[entity] == result
    assert client.set_schedule_enabled.call_args.args[1:] == (False, "old")
    await hass.services.async_call("resideo_native", "set_heating_schedule_mode",
        {"entity_id": entity, "mode": "Geofence", "expected_revision": "old", "confirm_change": True,
         "geofence": {"home_temperature": 20, "away_temperature": 16}}, blocking=True, return_response=True)
    assert client.set_schedule_mode.call_args.kwargs == {"confirm_change": True, "days": None, "geofence": {"home_temperature": 20, "away_temperature": 16}}


async def test_device_configuration_links_scope_to_the_account(hass, entry, client):
    from homeassistant.helpers import device_registry as dr
    registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(registry, entry.entry_id)
    assert devices
    assert all(d.configuration_url == f"homeassistant://resideo-schedules?config_entry={entry.entry_id}" for d in devices)


async def test_unconfirmed_schedule_is_response_data_instead_of_http_error(hass, entry, client):
    result = {"status": "readback_unconfirmed", "write_accepted": True, "days": {"Sunday": []}, "verification_status": "unconfirmed"}
    client.set_schedule = AsyncMock(return_value=result)
    entity = water_state(hass).entity_id
    response = await hass.services.async_call("resideo_native", "set_hot_water_schedule", {"entity_id": entity, "days": {"Sunday": []}, "expected_revision": "fresh"}, blocking=True, return_response=True)
    assert response[entity] == result
