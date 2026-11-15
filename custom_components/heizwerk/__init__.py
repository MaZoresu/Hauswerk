"""Heizwerk: Raumweise Heizungsregelung mit Fensterpause, Heizplänen und Anwesenheit."""
from __future__ import annotations

import logging
import os

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import api
from .const import (
    DOMAIN,
    NAME,
    PANEL_COMPONENT,
    PANEL_ICON,
    PANEL_URL,
    PLATFORMS,
    STATIC_URL,
)
from .controller import Heizwerk

_LOGGER = logging.getLogger(__name__)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
PANEL_FILE = "heizwerk-panel.js"


async def _async_register_panel(hass: HomeAssistant) -> None:
    key = f"{DOMAIN}_static_registered"
    if not hass.data.get(key):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, FRONTEND_DIR, cache_headers=False)]
        )
        hass.data[key] = True

    mtime = await hass.async_add_executor_job(
        os.path.getmtime, os.path.join(FRONTEND_DIR, PANEL_FILE)
    )
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL,
        webcomponent_name=PANEL_COMPONENT,
        sidebar_title=NAME,
        sidebar_icon=PANEL_ICON,
        module_url=f"{STATIC_URL}/{PANEL_FILE}?v={int(mtime)}",
        require_admin=False,
        config={},
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    controller = Heizwerk(hass, entry)
    await controller.async_load()
    hass.data[DOMAIN] = controller

    api.async_register(hass)
    await _async_register_panel(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await controller.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        controller: Heizwerk = hass.data.pop(DOMAIN)
        await controller.async_stop()
        frontend.async_remove_panel(hass, PANEL_URL)
    return unloaded
