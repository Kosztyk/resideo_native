"""The editor uses HA's real options-flow API, rather than writing config storage."""

from unittest.mock import AsyncMock, patch

from homeassistant.setup import async_setup_component
from homeassistant.components import frontend

from test_hot_water_homeassistant import custom_integrations, client, entry


async def test_editor_options_form_defaults_and_write_use_native_api(hass, entry, hass_client):
    assert await async_setup_component(hass, "config", {})
    client = await hass_client()
    response = await client.post("/api/config/config_entries/options/flow", json={"handler": entry.entry_id})
    assert response.status == 200
    flow = await response.json()
    assert flow["type"] == "form"
    schema = {field["name"]: field for field in flow["data_schema"]}
    assert schema["show_schedule_sidebar"]["default"] is False
    assert schema["poll_interval"]["default"] == 60
    assert schema["default_hold"]["default"] == "TemporaryHold"
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock):
        saved = await client.post(f'/api/config/config_entries/options/flow/{flow["flow_id"]}', json={
            "poll_interval": 120, "default_hold": "PermanentHold", "show_schedule_sidebar": True,
        })
        assert saved.status == 200
        assert (await saved.json())["type"] == "create_entry"
        assert entry.options["show_schedule_sidebar"] is True
        await hass.async_block_till_done()


async def test_sidebar_toggle_persists_without_reloading_thermostats(hass, entry, hass_client):
    from custom_components.resideo_native.frontend import (
        PANEL_PATH, async_setup_editor, async_unload_editor,
    )

    assert await async_setup_component(hass, "config", {})
    hass.config.components.add("frontend")
    hass.data.setdefault(frontend.DATA_EXTRA_MODULE_URL, frontend.UrlManager(lambda *args: None, []))
    hass.http.async_register_static_paths = AsyncMock()
    await async_setup_editor(hass, entry.entry_id)
    http_client = await hass_client()
    coordinator = entry.runtime_data
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock) as reload:
        for enabled in (True, False):
            response = await http_client.post("/api/config/config_entries/options/flow", json={"handler": entry.entry_id})
            flow = await response.json()
            values = {field["name"]: field["default"] for field in flow["data_schema"]}
            assert values["poll_interval"] == 60
            assert values["default_hold"] == "TemporaryHold"
            values["show_schedule_sidebar"] = enabled
            saved = await http_client.post(f'/api/config/config_entries/options/flow/{flow["flow_id"]}', json=values)
            assert (await saved.json())["type"] == "create_entry"
            await hass.async_block_till_done()
            assert entry.options["show_schedule_sidebar"] is enabled
            assert hass.data[frontend.DATA_PANELS][PANEL_PATH].show_in_sidebar is enabled
            assert entry.runtime_data is coordinator
            reload.assert_not_awaited()
        # A later token update must not treat the sidebar preference as pending.
        hass.config_entries.async_update_entry(entry, data={**entry.data, "test": "token update"})
        await hass.async_block_till_done()
        reload.assert_not_awaited()
        assert coordinator.configured_options == dict(entry.options)
    await async_unload_editor(hass, entry.entry_id)
