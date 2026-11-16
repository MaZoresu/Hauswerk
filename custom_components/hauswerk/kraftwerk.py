"""Modul Kraftwerk: Energiefluss – Solar, Netz, Batterie, Hausverbrauch.

Kraftwerk speichert nur, welche Leistungs-Sensoren (W/kW) wofür stehen. Den Fluss rechnet das Panel
live aus den Zuständen in Home Assistant; Tageswerte (kWh) und Preise kommen aus dem Energie-Dashboard
von Home Assistant, damit nichts doppelt erfasst wird.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import POWER_STORAGE_KEY
from .core import Haus
from .log import Protokoll, log_settings

_LOGGER = logging.getLogger(__name__)

KW_DEFAULTS: dict[str, Any] = {
    "kw_solar": [],              # Leistung der PV-Anlage(n), W oder kW
    "kw_grid": None,             # Netz: eine Leistung mit Vorzeichen (+ Bezug, − Einspeisung) …
    "kw_grid_export": None,      # … oder Bezug in kw_grid und Einspeisung getrennt hier
    "kw_grid_invert": False,     # Vorzeichen umdrehen (+ Einspeisung)
    "kw_battery": None,          # Batterie: Leistung mit Vorzeichen (+ Entladen, − Laden)
    "kw_battery_invert": False,
    "kw_battery_soc": None,      # Ladestand in %
    "kw_home": None,             # Hausverbrauch, falls gemessen (sonst errechnet)
    "kw_consumers": [],          # einzelne Verbraucher (Wärmepumpe, Wallbox …)
    "kw_names": {},              # eigene Namen der Verbraucher: {sensor: "Wärmepumpe"}
}
KW_KEYS = frozenset(KW_DEFAULTS)


class Kraftwerk:
    """Hält die Einstellungen des Moduls Kraftwerk."""

    def __init__(self, hass: HomeAssistant, log: Protokoll, haus: Haus) -> None:
        self.hass = hass
        self.log = log
        self.haus = haus
        self._store: Store = Store(hass, 1, POWER_STORAGE_KEY)
        self.settings: dict[str, Any] = dict(KW_DEFAULTS)

    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        self.settings.update({k: v for k, v in (stored.get("settings") or {}).items() if k in KW_KEYS})

    async def async_start(self) -> None:
        return None

    async def async_stop(self) -> None:
        return None

    def _save(self) -> None:
        self._store.async_delay_save(self._data, 2)

    def _data(self) -> dict[str, Any]:
        return {"settings": self.settings}

    async def async_save_settings(self, settings: dict[str, Any], by: str | None = None) -> None:
        settings = {k: v for k, v in settings.items() if k in KW_KEYS}
        changed = [k for k, v in settings.items() if self.settings.get(k) != v]
        if not changed:
            return
        log_settings(self.log, settings, changed, by, module="kraftwerk")
        self.settings.update(settings)
        self._save()

    def entities(self) -> list[str]:
        """Alle gewählten Sensoren (für Diagnose)."""
        out: list[str] = []
        for key in KW_KEYS:
            value = self.settings.get(key)
            if isinstance(value, str):
                out.append(value)
            elif isinstance(value, list):
                out += [v for v in value if isinstance(v, str)]
        return out
