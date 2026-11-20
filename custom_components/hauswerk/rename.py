"""Umbenannte Entitäten übernehmen: Wird in Home Assistant eine Entitäts-ID geändert, ersetzt Hauswerk
sie in allen gespeicherten Einstellungen (Räume, Heizpläne, Rollläden, Profile, Kraftwerk, Widgets …)
und lädt sich neu, damit alle Zuhörer wieder stimmen."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, MODULE_HEATING, MODULE_HOUSE, MODULE_LIGHT, MODULE_LOG, MODULE_POWER, MODULE_SHUTTER

_LOGGER = logging.getLogger(__name__)

# Gespeicherte Daten je Modul, in denen Entitäts-IDs stehen können
RENAME_ATTRS: dict[str, tuple[str, ...]] = {
    MODULE_HOUSE: ("settings",),
    MODULE_HEATING: ("settings", "rooms", "plans", "turned_off", "heat_rates"),
    MODULE_SHUTTER: ("settings", "covers", "profiles", "_persist"),
    MODULE_POWER: ("settings",),
    MODULE_LIGHT: ("settings", "lights", "profiles"),
}
MODULE_NAMES = {MODULE_HOUSE: "Hauswerk", MODULE_HEATING: "Heizwerk", MODULE_SHUTTER: "Rollwerk", MODULE_POWER: "Kraftwerk", MODULE_LIGHT: "Lichtwerk"}


def swap(obj: Any, old: str, new: str) -> tuple[Any, bool]:
    """Ersetzt die Entitäts-ID überall (Werte und Schlüssel); liefert (neues Objekt, geändert?)."""
    if isinstance(obj, str):
        return (new, True) if obj == old else (obj, False)
    if isinstance(obj, list):
        out, changed = [], False
        for item in obj:
            val, ch = swap(item, old, new)
            out.append(val)
            changed |= ch
        return out, changed
    if isinstance(obj, dict):
        out, changed = {}, False
        for key, item in obj.items():
            val, ch = swap(item, old, new)
            if key == old:
                key, ch = new, True
            out[key] = val
            changed |= ch
        return out, changed
    return obj, False


def _payload(module: Any) -> dict[str, Any]:
    data = getattr(module, "_data", None)
    return data() if callable(data) else {"settings": module.settings}


async def async_rename_entity(hass: HomeAssistant, entry: ConfigEntry | None, old: str, new: str) -> list[str]:
    """Entität in allen Modulen umbenennen und sofort speichern; liefert die betroffenen Module."""
    modules = hass.data.get(DOMAIN) or {}
    touched: list[str] = []
    for key, attrs in RENAME_ATTRS.items():
        module = modules.get(key)
        if module is None:
            continue
        hit = False
        for attr in attrs:
            value = getattr(module, attr, None)
            if value is None:
                continue
            new_value, changed = swap(value, old, new)
            if changed:
                setattr(module, attr, new_value)
                hit = True
        if hit:
            await module._store.async_save(_payload(module))  # noqa: SLF001 - sofort, vor dem Neuladen
            touched.append(key)
    if touched:
        names = ", ".join(MODULE_NAMES[k] for k in touched)
        _LOGGER.info("Hauswerk: Entität %s umbenannt in %s (%s)", old, new, names)
        log = modules.get(MODULE_LOG)
        if log is not None:
            log.add("settings", "Entität umbenannt – übernommen", f"{old} → {new} · in {names}")
        if entry is not None:
            hass.config_entries.async_schedule_reload(entry.entry_id)
    return touched


@callback
def async_track_renames(hass: HomeAssistant, entry: ConfigEntry):
    """Auf Umbenennungen im Entitäts-Register hören; gibt die Abmeldung zurück."""

    @callback
    def _changed(event: Event) -> None:
        data = event.data
        if data.get("action") != "update" or not data.get("old_entity_id"):
            return
        hass.async_create_task(async_rename_entity(hass, entry, data["old_entity_id"], data["entity_id"]))

    return hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _changed)
