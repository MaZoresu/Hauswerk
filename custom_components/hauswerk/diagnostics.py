"""Diagnose-Download für Hauswerk (Geräte & Dienste › Hauswerk › ⋮ › Diagnose herunterladen).

Enthält Einstellungen, Räume, Heizpläne, den aktuellen Zustand aller Module, die Zustände
aller beteiligten Entitäten und die letzten Einträge des Protokolls. Benachrichtigungsziele
und Personen werden unkenntlich gemacht.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN, MODULE_HEATING, MODULE_HOUSE, MODULE_LOG, MODULE_POWER, MODULE_SHUTTER

TO_REDACT = {"notify_targets", "latitude", "longitude", "gps_accuracy", "user_id", "entity_picture"}
LOG_ENTRIES = 1500


def _entities(value: Any, found: set[str]) -> None:
    """Alle Entitäts-IDs in Einstellungen und Räumen einsammeln."""
    if isinstance(value, str):
        if "." in value and value.split(".", 1)[0].isidentifier() and " " not in value and value.count(".") == 1:
            found.add(value)
    elif isinstance(value, dict):
        for item in value.values():
            _entities(item, found)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _entities(item, found)


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    data = hass.data.get(DOMAIN) or {}
    haus, heating, shutters, power, log = (data.get(k) for k in (MODULE_HOUSE, MODULE_HEATING, MODULE_SHUTTER, MODULE_POWER, MODULE_LOG))
    out: dict[str, Any] = {"version": entry.version, "manifest_version": None}
    try:
        from homeassistant.loader import async_get_integration

        out["manifest_version"] = str((await async_get_integration(hass, DOMAIN)).version)
    except Exception:  # noqa: BLE001
        pass

    found: set[str] = set()
    if haus is not None:
        out["haus"] = {"settings": haus.settings, "status": haus.status()}
        _entities(haus.settings, found)
    if heating is not None:
        out["heizwerk"] = {
            "settings": heating.settings,
            "rooms": heating.rooms,
            "plans": heating.plans,
            "heat_rates": heating.heat_rates,
            "turned_off": heating.turned_off,
            "status": heating.status(),
            "valve_sources": getattr(heating, "_valve_src", {}),
        }
        _entities(heating.rooms, found)
        _entities(heating.settings, found)
        for ids in getattr(heating, "_valve_src", {}).values():
            found.update(ids)
    if shutters is not None:
        out["rollwerk"] = {"settings": shutters.settings, "covers": shutters.covers, "profiles": shutters.profiles, "status": shutters.status()}
        _entities(shutters.covers, found)
        _entities(shutters.settings, found)
    if power is not None:
        out["kraftwerk"] = {"settings": power.settings}
        found.update(power.entities())

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    states = {}
    for entity_id in sorted(found):
        state = hass.states.get(entity_id)
        entry_ = ent_reg.async_get(entity_id)
        device = dev_reg.async_get(entry_.device_id) if entry_ is not None and entry_.device_id else None
        states[entity_id] = {
            "state": state.state if state is not None else None,
            "attributes": dict(state.attributes) if state is not None else None,
            "last_changed": state.last_changed.isoformat() if state is not None else None,
            "platform": getattr(entry_, "platform", None),
            "device": {"manufacturer": device.manufacturer, "model": device.model, "name": device.name} if device else None,
        }
    out["entities"] = states
    if log is not None:
        out["log"] = log.entries[-LOG_ENTRIES:]
    return async_redact_data(out, TO_REDACT)
