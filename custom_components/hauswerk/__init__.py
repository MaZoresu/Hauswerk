"""Hauswerk: Haussteuerung für Home Assistant mit eigenem Seitenmenü-Panel.

Module:
- Heizwerk (intern „heizen“): raumweise Heizungsregelung mit Fensterpause, Heizplänen und Anwesenheit
- Kern (core.py): Anwesenheit, Urlaub, Wetter, Darstellung – gilt für alle Module
- Protokoll: was wann warum entschieden wurde (für alle Module)
- Rollwerk (intern „rollwerk“): Rollläden mit Profilen nach dem Vorbild der Cover Control Automation
- Kraftwerk (intern „kraftwerk“): Energiefluss – Solar, Netz, Batterie, Verbrauch
- Licht, Garten: geplant
"""
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
    MODULE_HEATING,
    MODULE_HOUSE,
    MODULE_LOG,
    MODULE_POWER,
    MODULE_SHUTTER,
    NAME,
    PANEL_COMPONENT,
    PANEL_ICON,
    PANEL_URL,
    PLATFORMS,
    STATIC_URL,
)
from .controller import Heizen
from .core import Haus
from .kraftwerk import Kraftwerk
from .log import Protokoll
from .rename import async_track_renames
from .rollwerk import Rollwerk

_LOGGER = logging.getLogger(__name__)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
PANEL_FILE = "hauswerk-panel.js"
DASHBOARD_FILE = "hauswerk-dashboard.js"


async def _async_register_panel(hass: HomeAssistant) -> None:
    key = f"{DOMAIN}_static_registered"
    if not hass.data.get(key):
        await hass.http.async_register_static_paths(
            # Zwischenspeichern erlaubt: die Adresse enthält die Version (?v=…), ein Update lädt also neu.
            # Liegt hauswerk-panel.js.gz daneben, liefert Home Assistant die komprimierte Datei (≈ 1/5 der Größe).
            [StaticPathConfig(STATIC_URL, FRONTEND_DIR, cache_headers=True)]
        )
        hass.data[key] = True

    mtime = await hass.async_add_executor_job(
        os.path.getmtime, os.path.join(FRONTEND_DIR, PANEL_FILE)
    )
    # Dashboard-Strategie „custom:hauswerk“ auf jeder Seite verfügbar machen (kleine Datei, lädt das Panel erst bei Bedarf)
    if not hass.data.get(f"{DOMAIN}_dashboard_js"):
        frontend.add_extra_js_url(hass, f"{STATIC_URL}/{DASHBOARD_FILE}?v={int(mtime)}")
        hass.data[f"{DOMAIN}_dashboard_js"] = True
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
    log = Protokoll(hass)
    await log.async_load()
    # Hauswerk-Kern zuerst anlegen, Heizwerk nutzt ihn; beim ersten Start übernimmt der Kern
    # Anwesenheit, Urlaub, Wetter und Darstellung aus den bisherigen Einstellungen von Heizwerk.
    haus = Haus(hass, log)
    heating = Heizen(hass, entry, log, haus)
    await heating.async_load()
    await haus.async_load(legacy=heating.loaded_settings)
    heating.drop_house_settings()
    shutters = Rollwerk(hass, log, haus)
    await shutters.async_load()
    power = Kraftwerk(hass, log, haus)
    await power.async_load()
    hass.data[DOMAIN] = {MODULE_LOG: log, MODULE_HOUSE: haus, MODULE_HEATING: heating, MODULE_SHUTTER: shutters, MODULE_POWER: power}

    api.async_register(hass)
    entry.async_on_unload(async_track_renames(hass, entry))
    await _async_register_panel(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await haus.async_start()
    await heating.async_start()
    await shutters.async_start()
    await power.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        modules: dict = hass.data.pop(DOMAIN)
        # Module zuerst, Kern und Protokoll zuletzt
        for key in [k for k in modules if k not in (MODULE_HOUSE, MODULE_LOG)] + [MODULE_HOUSE, MODULE_LOG]:
            if key in modules:
                await modules[key].async_stop()
        frontend.async_remove_panel(hass, PANEL_URL)
    return unloaded
