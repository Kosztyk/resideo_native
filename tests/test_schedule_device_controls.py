"""Visible device controls use real HA switch/button services and scoped data."""

from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from test_hot_water_homeassistant import custom_integrations, client, entry


def control(hass, domain, suffix):
    return er.async_get(hass).async_get_entity_id(domain, "resideo_native", f"T6R-parent_{suffix}")


async def test_new_controls_are_visible_on_the_same_thermostat_device(hass, entry, client):
    registry = er.async_get(hass)
    heating = registry.async_get(control(hass, "switch", "heating_schedule"))
    for domain, suffix in (("switch", "schedule_sidebar"), ("switch", "geofencing")):
        entity = registry.async_get(control(hass, domain, suffix))
        assert entity.device_id == heating.device_id
        assert entity.entity_category is None
        assert entity.disabled_by is None
    assert hass.states.get(control(hass, "switch", "schedule_sidebar")).state == "off"
    button = hass.states.get(control(hass, "switch", "geofencing"))
    query = parse_qs(urlsplit(button.attributes["editor_url"]).query)
    assert query["config_entry"] == [entry.entry_id]
    assert button.state == "off"
    assert button.attributes["resideo_schedule_mode"] is True
    assert registry.async_get(query["entity"][0]).device_id == heating.device_id


async def test_sidebar_device_switch_preserves_options_and_syncs_other_thermostats(hass, entry, client):
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock) as reload:
        hass.config_entries.async_update_entry(entry, options={"poll_interval": 120, "default_hold": "PermanentHold"})
        await hass.async_block_till_done()
        # Model the coordinator snapshot after loading those custom options.
        entry.runtime_data.configured_options = dict(entry.options)
        reload.reset_mock()
        coordinator = entry.runtime_data
        entity = control(hass, "switch", "schedule_sidebar")
        for service, enabled in (("turn_on", True), ("turn_off", False)):
            await hass.services.async_call("switch", service, {"entity_id": entity}, blocking=True)
            await hass.async_block_till_done()
            assert dict(entry.options) == {"poll_interval": 120, "default_hold": "PermanentHold", "show_schedule_sidebar": enabled}
            sidebars = [s for s in hass.states.async_all("switch") if er.async_get(hass).async_get(s.entity_id).unique_id.endswith("_schedule_sidebar")]
            assert len(sidebars) == len(client.devices)
            assert {s.state for s in sidebars} == ({"on"} if enabled else {"off"})
            assert entry.runtime_data is coordinator
            reload.assert_not_awaited()
        # Editor/native options updates reach the device switches too.
        hass.config_entries.async_update_entry(entry, options={**entry.options, "show_schedule_sidebar": True})
        await hass.async_block_till_done()
        assert hass.states.get(entity).state == "on"
        reload.assert_not_awaited()
    client.set_hold.assert_not_awaited()
    client.set_temperature.assert_not_awaited()


async def test_geofencing_switch_follows_reads_and_does_not_change_mode_before_setup(hass, entry, client):
    from homeassistant.helpers.entity_component import async_update_entity
    entity = control(hass, 'switch', 'geofencing')
    client.set_schedule_mode = AsyncMock()
    assert hass.states.get(entity).state == 'off'
    with patch('custom_components.resideo_native.switch.persistent_notification.async_create') as notify:
        await hass.services.async_call('switch','turn_on',{'entity_id':entity},blocking=True)
        assert 'mode=Geofence' in notify.call_args.args[1]
        assert hass.states.get(entity).state == 'off'
        client.get_schedule = AsyncMock(return_value={'schedule_type':'Geofence'})
        await async_update_entity(hass, entity)
        assert hass.states.get(entity).state == 'on'
        await hass.services.async_call('switch','turn_off',{'entity_id':entity},blocking=True)
        assert 'mode=Timed' in notify.call_args.args[1]
        assert hass.states.get(entity).state == 'on'
    client.set_schedule_mode.assert_not_awaited()
    client.set_hold.assert_not_awaited()


async def test_saved_mode_updates_the_switch_after_service_readback(hass, entry, client):
    entity = control(hass,'switch','geofencing')
    registry=er.async_get(hass)
    climate=registry.async_get_entity_id('climate','resideo_native','T6R-parent')
    client.set_schedule_mode=AsyncMock(return_value={'schedule_type':'Geofence','verification_status':'verified','revision':'new'})
    await hass.services.async_call('resideo_native','set_heating_schedule_mode',{'entity_id':climate,'mode':'Geofence','expected_revision':'fresh','confirm_change':True,'geofence':{'home_temperature':20,'away_temperature':16}},blocking=True,return_response=True)
    assert hass.states.get(entity).state == 'on'


async def test_upgrade_removes_only_the_obsolete_geofencing_button(hass, entry, client):
    registry=er.async_get(hass)
    old=registry.async_get_or_create('button','resideo_native','T6R-parent_switch_to_geofencing',config_entry=entry)
    unrelated=registry.async_get_or_create('button','resideo_native','unrelated_button',config_entry=entry)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(old.entity_id) is None
    assert registry.async_get(unrelated.entity_id) is not None
    assert hass.states.get(control(hass,'switch','geofencing')) is not None
