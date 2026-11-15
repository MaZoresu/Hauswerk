"""Hauswerk-Kern: Einstellungen und Zustände, die für alle Module gelten.

Anwesenheit (Personen, Zone, Wartezeiten, Heimweg, Gäste), Urlaub (Schalter, Zeitraum, Kalender),
Wetter, Darstellung, Widgets der Startseite und Berechtigungen. Module (z. B. Heizwerk) lesen
`away`, `approaching`, `away_for` und `vacation` und melden sich mit `subscribe()` für Änderungen an.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from homeassistant.const import STATE_HOME, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import CALENDAR_REFRESH, HOUSE_DEFAULTS, HOUSE_KEYS, HOUSE_STORAGE_KEY
from .log import Protokoll, log_settings
from .logic import distance_km, is_vacation, keyword_match, keywords

_LOGGER = logging.getLogger(__name__)

BAD_STATES = {STATE_UNAVAILABLE, STATE_UNKNOWN, None}
VACATION_KEYS = ("vacation_source", "vacation_calendar", "vacation_keywords")


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_when(value: Any):
    """Termin-Zeitpunkt aus einem Kalender: (lokale Zeit, ganztägig?)."""
    if value is None:
        return None, False
    text = str(value)
    if len(text) == 10:  # ganztägig: "2026-12-20"
        day = dt_util.parse_date(text)
        return (dt_util.start_of_local_day(day) if day else None), True
    when = dt_util.parse_datetime(text)
    if when is not None and when.tzinfo is None:
        when = when.replace(tzinfo=dt_util.get_default_time_zone())
    return (dt_util.as_local(when) if when else None), False


async def async_calendar_events(hass: HomeAssistant, entity_id: str, start, end) -> list[dict[str, Any]]:
    """Termine eines Kalenders über den Dienst calendar.get_events."""
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {"entity_id": entity_id, "start_date_time": start.isoformat(), "end_date_time": end.isoformat()},
        blocking=True,
        return_response=True,
    )
    return list(((response or {}).get(entity_id) or {}).get("events") or [])


class Haus:
    """Zentrale Einstellungen und Hauszustände von Hauswerk."""

    def __init__(self, hass: HomeAssistant, log: Protokoll) -> None:
        self.hass = hass
        self.log = log
        self._store: Store = Store(hass, 1, HOUSE_STORAGE_KEY)
        self.settings: dict[str, Any] = dict(HOUSE_DEFAULTS)
        # Zustände für die Module
        self.away = False
        self.approaching = False
        self.away_for = 0.0  # Sekunden, seit die letzte Person gegangen ist
        self.vacation = False
        # Urlaub aus dem Kalender
        self._cal_vacation = False
        self._cal_events: list[dict[str, Any]] = []
        self._cal_error: str | None = None
        self._cal_at = 0.0
        self._flags: dict[str, Any] = {}
        self._listeners: set[Callable[[], None]] = set()
        self._unsubs: list[Callable[[], None]] = []
        self._state_unsub: Callable[[], None] | None = None

    # ------------------------------------------------------------ Speicher
    async def async_load(self, legacy: dict[str, Any] | None = None) -> None:
        """Laden; beim ersten Start die zentralen Einstellungen aus dem Speicher von Heizwerk übernehmen."""
        stored = await self._store.async_load()
        if stored is None:
            taken = {k: v for k, v in (legacy or {}).items() if k in HOUSE_KEYS or k == "proximity_km"}
            stored = {"settings": taken}
            if taken:
                _LOGGER.info("Übernehme zentrale Einstellungen (%s) aus Heizwerk", ", ".join(sorted(taken)))
        self.settings.update(stored.get("settings") or {})
        # Heimweg-Grenze früher in Kilometern, jetzt in Metern
        old_km = self.settings.pop("proximity_km", None)
        if old_km and not self.settings.get("proximity_m"):
            self.settings["proximity_m"] = float(old_km) * 1000
        self.settings = {k: v for k, v in self.settings.items() if k in HOUSE_KEYS}
        await self._store.async_save({"settings": self.settings})

    def _save(self) -> None:
        self._store.async_delay_save(lambda: {"settings": self.settings}, 2)

    # ------------------------------------------------------------ Lebenszyklus
    async def async_start(self) -> None:
        self._unsubs.append(async_track_time_interval(self.hass, self._async_tick, timedelta(minutes=1)))
        self._track()
        await self._async_refresh_calendar(force=True)
        self.update()

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None
        await self._store.async_save({"settings": self.settings})

    def _track(self) -> None:
        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None
        ids = set(self.settings.get("persons") or []) | set(self.settings.get("proximity_sensors") or [])
        for key in ("home_zone", "outside_sensor"):
            if self.settings.get(key):
                ids.add(self.settings[key])
        if ids:
            self._state_unsub = async_track_state_change_event(self.hass, sorted(ids), self._on_change)

    @callback
    def _on_change(self, event: Event) -> None:
        if event.data["entity_id"] in (self.settings.get("persons") or []):
            # Nach den Wartezeiten noch einmal prüfen
            for key in ("away_delay", "arrive_delay"):
                delay = int(self.settings.get(key) or 0) * 60
                if delay:
                    async_call_later(self.hass, delay + 1, self._async_later)
        self._notify()

    async def _async_later(self, _now=None) -> None:
        self._notify()

    async def _async_tick(self, _now=None) -> None:
        before = (self.away, self.approaching, self.vacation)
        await self._async_refresh_calendar()
        self.update()
        if (self.away, self.approaching, self.vacation) != before:
            self._notify(update=False)

    # ------------------------------------------------------------ Module benachrichtigen
    @callback
    def subscribe(self, cb: Callable[[], None]) -> Callable[[], None]:
        """Ein Modul meldet sich für Änderungen an (Anwesenheit, Urlaub, Einstellungen)."""
        self._listeners.add(cb)

        @callback
        def unsub() -> None:
            self._listeners.discard(cb)

        return unsub

    @callback
    def _notify(self, update: bool = True) -> None:
        if update:
            self.update()
        for cb in list(self._listeners):
            cb()

    # ------------------------------------------------------------ Einstellungen
    async def async_save_settings(self, settings: dict[str, Any], by: str | None = None) -> None:
        settings = {k: v for k, v in settings.items() if k in HOUSE_KEYS}
        changed = [k for k, v in settings.items() if self.settings.get(k) != v]
        if not changed:
            return
        log_settings(self.log, settings, changed, by)
        self.settings.update(settings)
        self._save()
        self._track()
        if any(k in settings for k in VACATION_KEYS):
            await self._async_refresh_calendar(force=True)
        self._notify()

    # ------------------------------------------------------------ Anwesenheit
    def home_state(self) -> str:
        """Zustand einer Person, die in der gewählten Wohnungs-Zone ist („home“ oder der Zonenname)."""
        zone = self.settings.get("home_zone") or "zone.home"
        if zone == "zone.home":
            return STATE_HOME
        state = self.hass.states.get(zone)
        return state.name if state is not None else STATE_HOME

    def _name(self, entity_id: str) -> str:
        state = self.hass.states.get(entity_id)
        return state.name if state is not None else entity_id

    def presence_why(self) -> str:
        """Kurze Begründung für das Protokoll."""
        if self.settings.get("presence_force") == "away":
            return "von Hand auf Abwesend gesetzt"
        if self.settings.get("guest"):
            return "Gäste-Modus"
        home = [
            self._name(p)
            for p in self.settings.get("persons") or []
            if (s := self.hass.states.get(p)) is not None and s.state == self.home_state()
        ]
        return f"Zu Hause: {', '.join(home)}" if home else "Alle Personen unterwegs"

    def _is_away(self) -> bool:
        """Abwesenheit mit Wartezeit beim Gehen und beim Heimkommen, Gästen und Heimweg."""
        self.approaching = False
        self.away_for = 0.0
        if self.settings.get("presence_force") == "away":
            return True
        if self.settings.get("guest"):
            return False
        persons = self.settings.get("persons") or []
        known = [s for s in (self.hass.states.get(p) for p in persons) if s is not None and s.state not in BAD_STATES]
        if not known:
            return False
        now = dt_util.utcnow().timestamp()
        home_state = self.home_state()
        home = [s for s in known if s.state == home_state]
        if home:
            # Erst nach der Wartezeit beim Heimkommen wieder „zu Hause“
            # (es zählt die Person, die schon am längsten da ist).
            arrive = int(self.settings.get("arrive_delay") or 0) * 60
            longest = max(now - s.last_changed.timestamp() for s in home)
            return self.away and longest < arrive
        delay = int(self.settings.get("away_delay") or 0) * 60
        last_left = max(s.last_changed.timestamp() for s in known)
        away = now - last_left >= delay
        self.away_for = now - last_left
        if away and self._near_home():
            self.approaching = True
            return False
        return away

    def _near_home(self) -> bool:
        limit_km = float(self.settings.get("proximity_m") or 0) / 1000
        if limit_km <= 0:
            return False
        for entity_id in self.settings.get("proximity_sensors") or []:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in BAD_STATES:
                continue
            km = distance_km(_float(state.state), state.attributes.get("unit_of_measurement"))
            if km is not None and km <= limit_km:
                return True
        return False

    def _flip(self, key: str, value: Any, on: str | None, off: str | None, why: str | None = None) -> None:
        """Wechsel protokollieren (nicht beim ersten Durchlauf nach dem Start)."""
        old = self._flags.get(key)
        self._flags[key] = value
        if old is None or old == value:
            return
        message = on if value else off
        if message:
            self.log.add("presence", message, why)

    @callback
    def update(self) -> None:
        """Anwesenheit und Urlaub neu bestimmen (wird von den Modulen vor jeder Regelung aufgerufen)."""
        self.away = self._is_away()
        self.vacation = is_vacation(self.settings, dt_util.now().date().isoformat(), self._cal_vacation)
        self._flip("away", self.away, "Niemand mehr zu Hause – abwesend", "Wieder jemand zu Hause", self.presence_why())
        self._flip("approaching", self.approaching, "Jemand ist auf dem Heimweg", None,
                   f"näher als {float(self.settings.get('proximity_m') or 0):.0f} m")
        self._flip("vacation", self.vacation, "Urlaub beginnt", "Urlaub endet",
                   "Schalter Urlaub" if self.settings.get("vacation")
                   else {"calendar": "laut Kalender", "period": "laut Zeitraum"}.get(self.settings.get("vacation_source") or "period", ""))

    # ------------------------------------------------------------ Urlaub aus dem Kalender
    async def _async_refresh_calendar(self, force: bool = False) -> None:
        """Urlaubskalender lesen: läuft ein passender Termin, und welche kommen als Nächstes."""
        now_ts = dt_util.utcnow().timestamp()
        if not force and now_ts - self._cal_at < CALENDAR_REFRESH:
            return
        self._cal_at = now_ts
        cal = self.settings.get("vacation_calendar")
        if (self.settings.get("vacation_source") or "period") != "calendar" or not cal:
            self._cal_vacation, self._cal_events, self._cal_error = False, [], None
            return
        now = dt_util.now()
        try:
            events = await async_calendar_events(self.hass, cal, now - timedelta(days=1), now + timedelta(days=120))
        except Exception as err:  # noqa: BLE001 - Kalender weg/defekt: letzten Stand behalten
            self._cal_error = str(err) or type(err).__name__
            _LOGGER.warning("Urlaubskalender %s nicht lesbar: %s", cal, err)
            return
        words = keywords(self.settings.get("vacation_keywords"))
        active, upcoming = False, []
        for ev in events:
            if not keyword_match(ev.get("summary"), words):
                continue
            start, _ = parse_when(ev.get("start"))
            end, _ = parse_when(ev.get("end"))
            if start is None or end is None or end <= now:
                continue
            if start <= now:
                active = True
            upcoming.append({"summary": ev.get("summary"), "start": start.isoformat(), "end": end.isoformat()})
        upcoming.sort(key=lambda e: e["start"])
        self._cal_vacation, self._cal_events, self._cal_error = active, upcoming[:5], None

    # ------------------------------------------------------------ Für das Panel
    def outside_temp(self) -> float | None:
        entity_id = self.settings.get("outside_sensor")
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None or state.state in BAD_STATES:
            return None
        return _float(state.state)

    def status(self) -> dict[str, Any]:
        return {
            "away": self.away,
            "approaching": self.approaching,
            "presence_force": self.settings.get("presence_force"),
            "vacation": self.vacation,
            "vacation_events": self._cal_events,
            "vacation_calendar_error": self._cal_error,
            "guest": bool(self.settings.get("guest")),
            "outside_temp": self.outside_temp(),
        }
