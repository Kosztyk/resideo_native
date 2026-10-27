"""The schedule entry and genuine On/Off switch appear on real HA devices."""

from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

from homeassistant.helpers import entity_registry as er

from test_hot_water_homeassistant import custom_integrations, client, entry


async def test_editor_entity_links_to_its_thermostat_and_account(hass, entry, client):
    editors = [s for s in hass.states.async_all("sensor") if s.attributes.get("resideo_schedule_editor")]
    assert len(editors) == len(client.devices)
    registry = er.async_get(hass)
    for state in editors:
        assert state.state == "Open"
        query = parse_qs(urlsplit(state.attributes["editor_url"]).query)
        assert query["config_entry"] == [entry.entry_id]
        climate = registry.async_get(query["entity"][0])
        assert climate.device_id == registry.async_get(state.entity_id).device_id


async def test_switch_reports_native_status_and_toggles_the_selected_device(hass, entry, client):
    registry = er.async_get(hass)
    device = client.devices["T6R-parent"]
    device.raw["scheduleStatus"] = "Resume"
    entry.runtime_data.async_set_updated_data(client.devices)
    await hass.async_block_till_done()
    entity = registry.async_get_entity_id("switch", "resideo_native", "T6R-parent_heating_schedule")
    assert hass.states.get(entity).state == "on"
    client.get_schedule = AsyncMock(return_value={"revision": "fresh", "write_supported": True})
    async def toggle(device_id, enabled, revision):
        assert device_id == "T6R-parent" and revision == "fresh"
        device.raw["scheduleStatus"] = "Resume" if enabled else "Pause"
        return {"verification_status": "verified"}
    client.set_schedule_enabled = AsyncMock(side_effect=toggle)
    await hass.services.async_call("switch", "turn_off", {"entity_id": entity}, blocking=True)
    assert hass.states.get(entity).state == "off"
    client.set_schedule_enabled.assert_awaited_once_with("T6R-parent", False, "fresh")
    client.set_hold.assert_not_awaited()
    await hass.services.async_call("switch", "turn_on", {"entity_id": entity}, blocking=True)
    assert hass.states.get(entity).state == "on"
    client.set_hold.assert_not_awaited()


async def test_switch_status_is_unknown_when_native_status_is_missing(hass, entry, client):
    for state in hass.states.async_all("switch"):
        assert state.state == ("off" if er.async_get(hass).async_get(state.entity_id).unique_id.endswith(("_schedule_sidebar", "_geofencing")) else "unknown")


async def test_unconfirmed_toggle_keeps_observed_switch_state(hass, entry, client):
    import pytest
    from homeassistant.exceptions import HomeAssistantError
    device = client.devices["T6R-parent"]
    device.raw["scheduleStatus"] = "Resume"
    entry.runtime_data.async_set_updated_data(client.devices)
    await hass.async_block_till_done()
    entity = er.async_get(hass).async_get_entity_id("switch", "resideo_native", "T6R-parent_heating_schedule")
    client.get_schedule = AsyncMock(return_value={"revision": "fresh"})
    client.set_schedule_enabled = AsyncMock(return_value={"status": "readback_unconfirmed", "verification_status": "unconfirmed", "message": "Accepted but unconfirmed"})
    with pytest.raises(HomeAssistantError, match="unconfirmed"):
        await hass.services.async_call("switch", "turn_off", {"entity_id": entity}, blocking=True)
    assert hass.states.get(entity).state == "on"
    assert hass.states.get(entity).attributes["last_command_verification"] == "unconfirmed"
    client.set_hold.assert_not_awaited()
