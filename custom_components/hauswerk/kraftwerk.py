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

from .appliance import Appliances
from .appliance_logic import TYPES as APPLIANCE_TYPES
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
    "kw_battery_energy": None,   # gespeicherte Energie (Wh/kWh), sonst Kapazität × Ladestand
    "kw_battery_kwh": None,      # Kapazität in kWh (nur ohne Energie-Sensor nötig)
    "kw_battery_min": 10,        # Reserve in %, die nicht entladen wird
    "kw_home": None,             # Hausverbrauch, falls gemessen (sonst errechnet)
    "kw_consumers": [],          # einzelne Verbraucher (Wärmepumpe, Wallbox …)
    "kw_names": {},              # eigene Namen der Verbraucher: {sensor: "Wärmepumpe"}
    "kw_invest": None,           # Anschaffungskosten der Solaranlage (€) fürs Sparschwein im Bericht
    # Geräte mit Fertigerkennung: [{id, name, type, power, door?, status?, status_done?, notify[], notify_ha, important}]
    "kw_appliances": [],
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
        self.appliances = Appliances(hass, log, haus, lambda: list(self.settings.get("kw_appliances") or []))
        haus.extra_status["appliances"] = self.appliances.status

    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        self.settings.update({k: v for k, v in (stored.get("settings") or {}).items() if k in KW_KEYS})
        await self.appliances.async_load()

    async def async_start(self) -> None:
        self.appliances.async_setup()

    async def async_stop(self) -> None:
        self.appliances.async_stop()
        await self.appliances._store.async_save(self.appliances._data())

    def _save(self) -> None:
        self._store.async_delay_save(self._data, 2)

    def _data(self) -> dict[str, Any]:
        return {"settings": self.settings}

    async def async_save_settings(self, settings: dict[str, Any], by: str | None = None) -> None:
        settings = {k: v for k, v in settings.items() if k in KW_KEYS}
        changed = [k for k, v in settings.items() if self.settings.get(k) != v]
        if not changed:
            return
        log_settings(self.log, settings, changed, by, module="kraftwerk", old=self.settings)
        self.settings.update(settings)
        self._save()
        if "kw_appliances" in changed:
            self.appliances.async_setup()

    def entities(self) -> list[str]:
        """Alle gewählten Sensoren (für Diagnose)."""
        out: list[str] = []
        for key in KW_KEYS:
            value = self.settings.get(key)
            if isinstance(value, str):
                out.append(value)
            elif isinstance(value, list):
                out += [v for v in value if isinstance(v, str)]
        for dev in self.settings.get("kw_appliances") or []:
            out += [dev[k] for k in ("power", "door", "status") if dev.get(k)]
        return out
