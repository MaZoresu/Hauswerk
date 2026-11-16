"""Protokoll von Hauswerk: was wann warum entschieden wurde (für alle Module)."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import LOG_DAYS, LOG_MAX, LOG_STORAGE_KEY, SETTING_LABELS

# Kategorien (das Panel zeigt sie als Filter)
CATEGORIES = ("presence", "season", "target", "window", "manual", "health", "command", "settings", "shutter")


def log_settings(log: "Protokoll", settings: dict[str, Any], changed: list[str], by: str | None, module: str | None = None) -> None:
    """Geänderte Einstellungen ins Protokoll: „Urlaub an“ bzw. „Einstellungen geändert“ mit Quelle."""
    labels = list(dict.fromkeys(SETTING_LABELS.get(k, k) for k in changed))
    only = changed[0]
    if len(changed) == 1 and isinstance(settings[only], bool):
        title = f"{labels[0]} {'an' if settings[only] else 'aus'}"
    else:
        title = "Einstellungen geändert"
    source = f"Panel · von {by}" if by else "Home Assistant (Schalter oder Automation)"
    log.add("settings", title, f"{', '.join(labels)} · {source}", module=module)


class Protokoll:
    """Hält die Einträge der letzten LOG_DAYS Tage und meldet neue an das Panel."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store = Store(hass, 1, LOG_STORAGE_KEY)
        self.entries: list[dict[str, Any]] = []
        self._subscribers: set[Callable[[dict], None]] = set()

    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        self.entries = list(stored.get("entries") or [])
        self._prune()

    async def async_stop(self) -> None:
        await self._store.async_save({"entries": self.entries})

    def _prune(self) -> None:
        cutoff = (dt_util.utcnow() - timedelta(days=LOG_DAYS)).timestamp()
        if self.entries and self.entries[0]["ts"] < cutoff:
            self.entries = [e for e in self.entries if e["ts"] >= cutoff]
        if len(self.entries) > LOG_MAX:
            self.entries = self.entries[-LOG_MAX:]

    @callback
    def add(
        self,
        cat: str,
        title: str,
        why: str | None = None,
        room: str | None = None,
        room_name: str | None = None,
        module: str | None = None,
    ) -> None:
        entry = {"ts": round(dt_util.utcnow().timestamp(), 1), "cat": cat, "title": title}
        if module:
            entry["mod"] = module
        if why:
            entry["why"] = why
        if room:
            entry["room"] = room
            if room_name:
                entry["rn"] = room_name
        self.entries.append(entry)
        if len(self.entries) % 100 == 0:
            self._prune()
        self._store.async_delay_save(lambda: {"entries": self.entries}, 30)
        for cb in list(self._subscribers):
            cb(entry)

    @callback
    def subscribe(self, cb: Callable[[dict], None]) -> Callable[[], None]:
        self._subscribers.add(cb)

        @callback
        def unsub() -> None:
            self._subscribers.discard(cb)

        return unsub
