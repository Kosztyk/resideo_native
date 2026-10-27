"""Serve the integration editor with an optional shared sidebar entry."""

from __future__ import annotations

import asyncio
from pathlib import Path

from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION

PANEL_PATH = "resideo-schedules"
STATIC_URL = "/resideo_native/schedule-editor.js"
EDITOR_VERSION = VERSION
VERSIONED_STATIC_URL = f"/resideo_native/schedule-editor-{EDITOR_VERSION}.js"
PANEL_ELEMENT = f"resideo-schedule-panel-{EDITOR_VERSION.replace('.', '-')}"
ENTITY_MODULE_URL = f"/resideo_native/schedule-entity-{EDITOR_VERSION}.js"


async def _register_panel(hass, state):
    from homeassistant.components import frontend

    visible = bool(state.get("sidebar_entries"))
    if state.get("panel_registered"):
        if state.get("sidebar_visible") == visible:
            return
        frontend.async_remove_panel(hass, PANEL_PATH)
    elif frontend.async_panel_exists(hass, PANEL_PATH):
        raise ValueError(f"The sidebar path {PANEL_PATH} is already in use")
    # Use the same custom-panel configuration as panel_custom, with the
    # explicit sidebar flag exposed by frontend's registration API.
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        frontend_url_path=PANEL_PATH,
        sidebar_title="Resideo schedules",
        sidebar_icon="mdi:calendar-clock",
        config={"_panel_custom": {"name": PANEL_ELEMENT, "module_url": VERSIONED_STATIC_URL,
                "embed_iframe": False, "trust_external": False, "handle_safe_area": False}},
        require_admin=True,
        show_in_sidebar=visible,
    )
    state["panel_registered"] = True
    state["sidebar_visible"] = visible


async def async_setup_editor(hass: HomeAssistant, entry_id: str, *, show_in_sidebar: bool = False) -> None:
    """Headless HA can run the protocol without loading the frontend."""
    if "frontend" not in hass.config.components or getattr(hass, "http", None) is None:
        return
    from homeassistant.components.http import StaticPathConfig

    state = hass.data.setdefault(DOMAIN, {}).setdefault("editor", {})
    lock = state.setdefault("lock", asyncio.Lock())
    async with lock:
        if not state.get("static_registered"):
            await hass.http.async_register_static_paths(
                [
                    StaticPathConfig(
                        STATIC_URL,
                        str(Path(__file__).parent / "www" / "schedule-editor.js"),
                        False,
                    ),
                    StaticPathConfig(
                        ENTITY_MODULE_URL,
                        str(Path(__file__).parent / "www" / "schedule-entity.js"),
                        False,
                    ),
                    StaticPathConfig(
                        VERSIONED_STATIC_URL,
                        str(Path(__file__).parent / "www" / "schedule-editor.js"),
                        False,
                    ),
                ]
            )
            state["static_registered"] = True
        if not state.get("entity_module_registered"):
            from homeassistant.components import frontend
            frontend.add_extra_js_url(hass, ENTITY_MODULE_URL)
            state["entity_module_registered"] = True
        state.setdefault("entries", set()).add(entry_id)
        sidebar_entries = state.setdefault("sidebar_entries", set())
        if show_in_sidebar:
            sidebar_entries.add(entry_id)
        else:
            sidebar_entries.discard(entry_id)
        await _register_panel(hass, state)


async def async_unload_editor(hass: HomeAssistant, entry_id: str) -> None:
    state = hass.data.get(DOMAIN, {}).get("editor")
    if not state:
        return
    from homeassistant.components import frontend

    async with state["lock"]:
        state.setdefault("entries", set()).discard(entry_id)
        state.setdefault("sidebar_entries", set()).discard(entry_id)
        if not state["entries"]:
            if state.get("panel_registered"):
                frontend.async_remove_panel(hass, PANEL_PATH)
                state["panel_registered"] = False
            if state.get("entity_module_registered"):
                frontend.remove_extra_js_url(hass, ENTITY_MODULE_URL)
                state["entity_module_registered"] = False
        elif state["entries"] and state.get("panel_registered"):
            await _register_panel(hass, state)
        # The HTTP router cannot unregister a static path. Reuse it on reload.
