"""Sidebar lifecycle: shared across accounts, safe headless and reusable on reload."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components import frontend

from custom_components.resideo_native.frontend import (
    PANEL_PATH,
    ENTITY_MODULE_URL,
    PANEL_ELEMENT,
    STATIC_URL,
    VERSIONED_STATIC_URL,
    async_setup_editor,
    async_unload_editor,
)


async def test_headless_setup_is_noop(hass):
    await async_setup_editor(hass, "entry-a")
    assert not frontend.async_panel_exists(hass, PANEL_PATH)


async def test_shared_panel_and_static_path_lifecycle(hass):
    hass.config.components.add("frontend")
    hass.data.setdefault(frontend.DATA_EXTRA_MODULE_URL, frontend.UrlManager(lambda *args: None, []))
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    await async_setup_editor(hass, "entry-a")
    await async_setup_editor(hass, "entry-b")
    assert frontend.async_panel_exists(hass, PANEL_PATH)
    panel = hass.data[frontend.DATA_PANELS][PANEL_PATH]
    assert panel.require_admin is True
    assert panel.sidebar_title == "Resideo schedules"
    assert panel.show_in_sidebar is False
    assert panel.config_panel_domain is None
    assert ENTITY_MODULE_URL in hass.data[frontend.DATA_EXTRA_MODULE_URL].urls
    assert panel.config["_panel_custom"]["name"] == PANEL_ELEMENT
    assert panel.config["_panel_custom"]["module_url"] == VERSIONED_STATIC_URL
    hass.http.async_register_static_paths.assert_awaited_once()
    configs = hass.http.async_register_static_paths.call_args.args[0]
    assert {config.url_path for config in configs} == {STATIC_URL, VERSIONED_STATIC_URL, ENTITY_MODULE_URL}
    for config in configs:
        assert config.cache_headers is False
        assert config.path.endswith(("/www/schedule-editor.js", "/www/schedule-entity.js"))
    await async_unload_editor(hass, "entry-a")
    assert frontend.async_panel_exists(hass, PANEL_PATH)
    await async_unload_editor(hass, "entry-b")
    assert not frontend.async_panel_exists(hass, PANEL_PATH)
    assert ENTITY_MODULE_URL not in hass.data[frontend.DATA_EXTRA_MODULE_URL].urls
    await async_setup_editor(hass, "entry-a")
    assert frontend.async_panel_exists(hass, PANEL_PATH)
    hass.http.async_register_static_paths.assert_awaited_once()
    await async_unload_editor(hass, "entry-a")


async def test_sidebar_is_optional_across_accounts(hass):
    hass.config.components.add("frontend")
    hass.data.setdefault(frontend.DATA_EXTRA_MODULE_URL, frontend.UrlManager(lambda *args: None, []))
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    await async_setup_editor(hass, "entry-a")
    await async_setup_editor(hass, "entry-b", show_in_sidebar=True)
    assert hass.data[frontend.DATA_PANELS][PANEL_PATH].show_in_sidebar is True
    await async_unload_editor(hass, "entry-b")
    assert hass.data[frontend.DATA_PANELS][PANEL_PATH].show_in_sidebar is False
    assert hass.data[frontend.DATA_PANELS][PANEL_PATH].config_panel_domain is None
    await async_unload_editor(hass, "entry-a")
    assert not frontend.async_panel_exists(hass, PANEL_PATH)


async def test_does_not_replace_another_panel(hass):
    hass.config.components.add("frontend")
    hass.data.setdefault(frontend.DATA_EXTRA_MODULE_URL, frontend.UrlManager(lambda *args: None, []))
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    frontend.async_register_built_in_panel(
        hass, "history", frontend_url_path=PANEL_PATH
    )
    with pytest.raises(ValueError, match="already in use"):
        await async_setup_editor(hass, "entry-a")
    await async_unload_editor(hass, "entry-a")
    assert hass.data[frontend.DATA_PANELS][PANEL_PATH].component_name == "history"
    frontend.async_remove_panel(hass, PANEL_PATH)


async def test_editor_module_served_by_home_assistant_http(hass, hass_client):
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, 'http', {})
    hass.config.components.add('frontend')
    hass.data.setdefault(frontend.DATA_EXTRA_MODULE_URL, frontend.UrlManager(lambda *args: None, []))
    await async_setup_editor(hass, 'entry-a')
    client = await hass_client()
    for path in (STATIC_URL, VERSIONED_STATIC_URL):
        response = await client.get(path)
        assert response.status == 200
        text = await response.text()
        assert 'resideo-schedule-panel' in text
        assert 'resideo-schedule-card' in text
        assert 'confirm_conversion' in text
    response = await client.get(ENTITY_MODULE_URL)
    assert response.status == 200
    assert 'hass-more-info' in await response.text()
    await async_unload_editor(hass, 'entry-a')
