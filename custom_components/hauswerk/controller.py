"""Hauswerk-Modul Heizwerk: Regelung, Speicher und Statistik.

Anwesenheit, Urlaub und Außentemperatur kommen aus dem Hauswerk-Kern (core.Haus).
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any
import uuid

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CALENDAR_REFRESH,
    HEAT_DEFAULTS,
    HOUSE_KEYS,
    LEGACY_STORAGE_KEY,
    SIGNAL_ROOMS,
    SIGNAL_UPDATE,
    STATS_DAYS,
    STORAGE_KEY,
    STORAGE_VERSION,
    WINDOW_OPEN_STATES,
)
from .logic import (
    MAX_TEMP,
    MIN_TEMP,
    MODES,
    TYPE_RADIATOR,
    aggressive,
    calendar_state,
    calibration_offset,
    compensated,
    compute_target,
    events_to_blocks,
    keyword_match,
    keywords,
    learn_rate,
    liming_active,
    minutes_until,
    next_comfort,
    smart_lead,
    occupied,
    room_setting,
    snap,
    summer_state,
    valve_opening,
    week_minute,
    window_paused,
)
from .core import Haus, async_calendar_events, parse_when
from .log import Protokoll, log_settings

_LOGGER = logging.getLogger(__name__)

BAD_STATES = {STATE_UNAVAILABLE, STATE_UNKNOWN, None}
OWN_CHANGE_GRACE = 20  # Sekunden, in denen Änderungen am Thermostat als eigene gelten
VALVE_INTERVAL = 300  # Sekunden zwischen zwei Ventilstellungen
CALIBRATION_WORDS = ("calibration", "offset", "kalibrier")
VALVE_WORDS = ("valve", "position", "opening", "ventil")
COMFORT_MODES = ("komfort", "vorheizen", "manuell", "party", "boost", "belegt")
NO_TUNING_MODES = ("fenster", "sommer", "entkalken", "warm")


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class Heizen:
    """Modul Heizen: hält Räume, Einstellungen und Laufzeitzustand und regelt die Thermostate."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, log: Protokoll, haus: Haus) -> None:
        self.hass = hass
        self.entry = entry
        # Hauswerk-Kern: Anwesenheit, Urlaub, Wetter
        self.haus = haus
        self.loaded_settings: dict[str, Any] = {}
        # Protokoll von Hauswerk: Entscheidungen, Fenster, Geräte, Befehle und Änderungen
        self.log = log
        self._flags: dict[str, Any] = {}
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.settings: dict[str, Any] = dict(HEAT_DEFAULTS)
        self.rooms: dict[str, dict[str, Any]] = {}
        self.stats: dict[str, dict[str, dict[str, float]]] = {}
        # Thermostate, die Hauswerk wegen offener Fenster ausgeschaltet hat (-> vorheriger Modus).
        # Wird gespeichert, damit sie nach einem Neustart wieder eingeschaltet werden.
        self.turned_off: dict[str, str] = {}
        # Gelernte Aufheizgeschwindigkeit je Raum in °C pro Stunde (für das lernende Vorheizen).
        self.heat_rates: dict[str, float] = {}
        # Gemeinsame Heizpläne, die Räume über plan_id nutzen.
        self.plans: dict[str, dict[str, Any]] = {}
        # Gemeinsame Pläne, die einem Kalender folgen: Termine der nächsten Tage je Plan
        self._plan_events: dict[str, list[dict[str, Any]]] = {}
        self._plan_errors: dict[str, str] = {}
        self._plan_cal_at = 0.0
        self.runtime: dict[str, dict[str, Any]] = {}
        self._unsubs: list[Callable[[], None]] = []
        self._state_unsub: Callable[[], None] | None = None
        self._pending_eval: Callable[[], None] | None = None
        self._subscribers: set[Callable[[dict], None]] = set()
        self._summer = False
        self._liming = False

    # ------------------------------------------------------------ Speicher
    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored is None:
            # Erster Start als Hauswerk: Daten der früheren Integration „Heizwerk“ übernehmen
            legacy = await Store(self.hass, STORAGE_VERSION, LEGACY_STORAGE_KEY).async_load()
            if legacy:
                _LOGGER.info("Übernehme Räume und Einstellungen aus %s", LEGACY_STORAGE_KEY)
                stored = legacy
                await self._store.async_save(legacy)
        stored = stored or {}
        # Alle gespeicherten Einstellungen merken: der Hauswerk-Kern übernimmt daraus beim ersten Start seine
        self.loaded_settings = dict(stored.get("settings") or {})
        self.settings.update({k: v for k, v in self.loaded_settings.items() if k in HEAT_DEFAULTS})
        self.rooms = stored.get("rooms") or {}
        self.stats = stored.get("stats") or {}
        self.turned_off = stored.get("turned_off") or {}
        self.heat_rates = stored.get("heat_rates") or {}
        self.plans = stored.get("plans") or {}

    def _data(self) -> dict[str, Any]:
        return {
            "settings": self.settings,
            "rooms": self.rooms,
            "plans": self.plans,
            "stats": self.stats,
            "turned_off": self.turned_off,
            "heat_rates": self.heat_rates,
        }

    def _save(self, delay: float = 2) -> None:
        self._store.async_delay_save(self._data, delay)

    # ------------------------------------------------------------ Lebenszyklus
    async def async_start(self) -> None:
        self._unsubs.append(
            async_track_time_interval(self.hass, self._async_tick, timedelta(minutes=1))
        )
        self._track_entities()
        # Änderungen von Anwesenheit, Urlaub und zentralen Einstellungen
        self._unsubs.append(self.haus.subscribe(self._schedule_eval))
        await self._async_refresh_plan_calendars(force=True)
        await self.async_evaluate()

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None
        if self._pending_eval:
            self._pending_eval()
            self._pending_eval = None
        await self._store.async_save(self._data())

    def _track_entities(self) -> None:
        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None
        ids: set[str] = set()
        for entity_id in (self.haus.settings.get("outside_sensor"), self.settings.get("season_entity")):
            if entity_id:
                ids.add(entity_id)
        for room in self.rooms.values():
            ids.update(room.get("climates") or [])
            ids.update(room.get("windows") or [])
            for key in ("temp_sensor", "humidity_sensor", "presence_sensor", "comfort_entity", "eco_entity", "schedule_entity", "presence_schedule"):
                if room.get(key):
                    ids.add(room[key])
        if ids:
            self._state_unsub = async_track_state_change_event(
                self.hass, sorted(ids), self._on_state_change
            )

    # ------------------------------------------------------------ Protokoll-Hilfen
    def _name(self, entity_id: str) -> str:
        state = self.hass.states.get(entity_id)
        return state.name if state is not None else entity_id

    @staticmethod
    def _t(value: float | None) -> str:
        return "–" if value is None else f"{value:.1f}".replace(".", ",")

    @staticmethod
    def _hm(ts: float) -> str:
        return dt_util.as_local(dt_util.utc_from_timestamp(ts)).strftime("%H:%M")

    @staticmethod
    def _by(by: str | None) -> str:
        return f" · von {by}" if by else ""

    def _flip(self, key: str, value: Any, on: str | None, off: str | None, cat: str, why: str | None = None) -> None:
        """Wechsel eines Hauszustands protokollieren (nicht beim ersten Durchlauf nach dem Start)."""
        old = self._flags.get(key)
        self._flags[key] = value
        if old is None or old == value:
            return
        message = on if value else off
        if message:
            self.log.add(cat, message, why)

    def _reason(self, room: dict, result: dict, upcoming: tuple[int, float] | None) -> str:
        """Kurze Begründung für eine Betriebsart im Protokoll."""
        mode = result["mode"]
        if mode in ("komfort", "eco"):
            plan = self.plans.get(room.get("plan_id") or "")
            if room.get("schedule_entity"):
                src = self._name(room["schedule_entity"])
            elif plan is not None:
                src = f"Plan „{plan.get('name')}“"
            else:
                src = "eigenem Heizplan"
            return f"{'Komfortzeit' if mode == 'komfort' else 'keine Komfortzeit'} laut {src}"
        if mode == "vorheizen":
            mins = upcoming[0] if upcoming else result.get("next_change")
            return f"Komfort beginnt in {mins} Min." if mins else "Komfort beginnt bald"
        if mode in ("abwesend", "frost"):
            return self.haus.presence_why()
        if mode in ("manuell", "boost") and result.get("override_until"):
            until = dt_util.parse_datetime(result["override_until"])
            return f"bis {dt_util.as_local(until).strftime('%H:%M')}" if until else ""
        if mode == "warm":
            return f"Raum hat {self._t(result.get('room_temp'))} °C"
        if mode in ("leer", "belegt"):
            return "Präsenzmelder"
        if mode == "eco_fix":
            return "Eco erzwingen ist an"
        if mode == "sommer":
            return "Sommerpause, Thermostate " + ("aus" if result.get("hvac_off") else "auf Frostschutz")
        return ""

    # ------------------------------------------------------------ Änderungen
    def new_room_id(self) -> str:
        return uuid.uuid4().hex[:8]

    async def async_save_room(self, room: dict[str, Any], by: str | None = None) -> dict[str, Any]:
        room_id = room.get("id") or self.new_room_id()
        room["id"] = room_id
        is_new = room_id not in self.rooms
        self.rooms[room_id] = room
        self._save()
        self._track_entities()
        if is_new:
            async_dispatcher_send(self.hass, SIGNAL_ROOMS)
        self.log.add("settings", "Raum angelegt" if is_new else "Raum geändert", f"Panel{self._by(by)}", room_id, room.get("name"))
        await self.async_evaluate()
        return room

    async def async_delete_room(self, room_id: str, by: str | None = None) -> None:
        name = (self.rooms.get(room_id) or {}).get("name")
        if name:
            self.log.add("settings", f"Raum „{name}“ gelöscht", f"Panel{self._by(by)}")
        self.rooms.pop(room_id, None)
        self.runtime.pop(room_id, None)
        self.stats.pop(room_id, None)
        self.heat_rates.pop(room_id, None)
        self._save()
        self._track_entities()
        async_dispatcher_send(self.hass, SIGNAL_ROOMS)
        await self.async_evaluate()

    async def async_save_settings(self, settings: dict[str, Any], by: str | None = None) -> None:
        settings = {k: v for k, v in settings.items() if k in HEAT_DEFAULTS}
        changed = [k for k, v in settings.items() if self.settings.get(k) != v]
        if not changed:
            return
        log_settings(self.log, settings, changed, by)
        self.settings.update(settings)
        self._save()
        self._track_entities()
        await self.async_evaluate()

    def drop_house_settings(self) -> None:
        """Nach der Übernahme durch den Kern: zentrale Einstellungen nicht mehr bei Heizwerk speichern."""
        if any(k in self.loaded_settings for k in HOUSE_KEYS):
            self._save()
        self.loaded_settings = {}

    # ------------------------------------------------------------ Gemeinsame Heizpläne
    async def async_save_plan(self, plan: dict[str, Any], by: str | None = None) -> dict[str, Any]:
        plan_id = plan.get("id") or self.new_room_id()
        is_new = plan_id not in self.plans
        plan["id"] = plan_id
        self.plans[plan_id] = plan
        self.log.add("settings", f"Heizplan „{plan.get('name')}“ {'angelegt' if is_new else 'geändert'}", f"Panel{self._by(by)}")
        self._save()
        await self._async_refresh_plan_calendars(force=True)
        await self.async_evaluate()
        return plan

    async def async_delete_plan(self, plan_id: str, by: str | None = None) -> None:
        """Plan löschen; Räume, die ihn nutzen, behalten seine Zeiten als eigenen Plan."""
        plan = self.plans.pop(plan_id, None)
        if plan:
            self.log.add("settings", f"Heizplan „{plan.get('name')}“ gelöscht", f"Panel{self._by(by)}")
        self._plan_events.pop(plan_id, None)
        self._plan_errors.pop(plan_id, None)
        for room in self.rooms.values():
            if room.get("plan_id") == plan_id:
                room["plan_id"] = None
                if plan:
                    room["schedule"] = [dict(b) for b in plan.get("schedule") or []]
        self._save()
        await self.async_evaluate()

    # ------------------------------------------------------------ Kalender
    def _parse_when(self, value: Any):
        return parse_when(value)

    async def _async_events(self, entity_id: str, start, end) -> list[dict[str, Any]]:
        return await async_calendar_events(self.hass, entity_id, start, end)

    async def _async_refresh_plan_calendars(self, force: bool = False) -> None:
        """Termine der Kalender-Pläne für die nächsten 8 Tage lesen (Termin = Komfortzeit).

        Gelesen wird alle 5 Minuten; ob gerade Komfort ist, rechnet die Regelung jede Minute
        aus diesen Terminen aus. Ganztägige Termine zählen nicht.
        """
        now_ts = dt_util.utcnow().timestamp()
        if not force and now_ts - self._plan_cal_at < CALENDAR_REFRESH:
            return
        self._plan_cal_at = now_ts
        now = dt_util.now()
        for plan_id, plan in self.plans.items():
            cal = plan.get("calendar")
            if not cal:
                self._plan_events.pop(plan_id, None)
                self._plan_errors.pop(plan_id, None)
                continue
            try:
                events = await self._async_events(cal, now - timedelta(days=1), now + timedelta(days=8))
            except Exception as err:  # noqa: BLE001 - letzten Stand behalten
                self._plan_errors[plan_id] = str(err) or type(err).__name__
                _LOGGER.warning("Kalender %s für Plan %s nicht lesbar: %s", cal, plan.get("name"), err)
                continue
            words = keywords(plan.get("keyword"))
            out = []
            for ev in events:
                if not keyword_match(ev.get("summary"), words):
                    continue
                start, all_day = self._parse_when(ev.get("start"))
                end, _ = self._parse_when(ev.get("end"))
                if start is None or end is None or all_day or end <= start:
                    continue
                out.append({"summary": ev.get("summary"), "start": start.timestamp(), "end": end.timestamp()})
            self._plan_events[plan_id] = sorted(out, key=lambda e: e["start"])
            self._plan_errors.pop(plan_id, None)

    def _calendar_plan(self, room: dict) -> dict | None:
        """Gemeinsamer Plan des Raums, falls er einem Kalender folgt."""
        if room.get("schedule_entity"):
            return None
        plan = self.plans.get(room.get("plan_id") or "")
        return plan if plan and plan.get("calendar") else None

    async def async_import_calendar(self, entity_id: str, keyword: str | None, days: int = 7) -> list[dict]:
        """Termine der nächsten Tage als Heizplan-Zeitfenster (Termin = Komfortzeit)."""
        start = dt_util.start_of_local_day()
        events = await self._async_events(entity_id, start, start + timedelta(days=days))
        words = keywords(keyword)
        slots: list[tuple[int, str, str]] = []
        for ev in events:
            if not keyword_match(ev.get("summary"), words):
                continue
            begin, all_day = self._parse_when(ev.get("start"))
            end, _ = self._parse_when(ev.get("end"))
            if begin is None or end is None or all_day or (end - begin) >= timedelta(hours=24):
                continue  # ganztägige und mehrtägige Termine passen nicht in einen Wochenplan
            slots.append((begin.weekday(), begin.strftime("%H:%M"), end.strftime("%H:%M")))
        return events_to_blocks(slots)

    async def async_set_room_enabled(self, room_id: str, enabled: bool) -> None:
        if room_id in self.rooms:
            self.rooms[room_id]["enabled"] = enabled
            self.log.add("settings", f"Automatik {'an' if enabled else 'aus'}", "Home Assistant (Schalter oder Automation)", room_id, self.rooms[room_id].get("name"))
            self._save()
            await self.async_evaluate()

    async def async_set_override(
        self, room_id: str, temp: float | None, hours: float | None, boost: bool = False, by: str | None = None
    ) -> None:
        rt = self._rt(room_id)
        name = (self.rooms.get(room_id) or {}).get("name")
        if boost:
            minutes = float(self.settings.get("boost_minutes") or 30)
            rt["override"] = {
                "temp": MAX_TEMP,
                "until": dt_util.utcnow().timestamp() + minutes * 60,
                "boost": True,
            }
            self.log.add("manual", f"Boost für {minutes:.0f} Min.", f"bis {self._hm(rt['override']['until'])} · im Panel{self._by(by)}", room_id, name)
        elif temp is None:
            rt["override"] = None
            self.log.add("manual", "Zurück zum Plan", f"im Panel{self._by(by)}", room_id, name)
        else:
            until = None
            if hours:
                until = dt_util.utcnow().timestamp() + hours * 3600
            else:
                result = rt.get("result") or {}
                minutes = result.get("next_change")
                until = dt_util.utcnow().timestamp() + (minutes or 240) * 60
            rt["override"] = {"temp": round(float(temp), 1), "until": until}
            self.log.add("manual", f"Von Hand: {self._t(rt['override']['temp'])} °C", f"im Panel · gilt bis {self._hm(until)}{self._by(by)}", room_id, name)
        await self.async_evaluate()

    # ------------------------------------------------------------ Abonnements fürs Panel
    @callback
    def subscribe(self, cb: Callable[[dict], None]) -> Callable[[], None]:
        self._subscribers.add(cb)

        @callback
        def unsub() -> None:
            self._subscribers.discard(cb)

        return unsub

    def status(self) -> dict[str, Any]:
        out = {}
        for room_id in self.rooms:
            rt = self._rt(room_id)
            out[room_id] = dict(rt.get("result") or {})
        return {
            **self.haus.status(),
            "rooms": out,
            "plan_events": {
                pid: [
                    {"summary": e["summary"], "start": dt_util.utc_from_timestamp(e["start"]).isoformat(), "end": dt_util.utc_from_timestamp(e["end"]).isoformat()}
                    for e in evs if e["end"] > dt_util.utcnow().timestamp()
                ][:6]
                for pid, evs in self._plan_events.items()
            },
            "plan_errors": self._plan_errors,
            "party": bool(self.settings.get("party")),
            "summer": self._summer,
            "liming": self._liming,
            "eco_force": bool(self.settings.get("eco_force")),
            "long_away": getattr(self, "_long_away", False),
        }

    def _state_float(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in BAD_STATES:
            return None
        return _float(state.state)

    # ------------------------------------------------------------ Laufzeit
    def _rt(self, room_id: str) -> dict[str, Any]:
        return self.runtime.setdefault(
            room_id,
            {
                "paused": False,
                "override": None,
                "last_sent": {},
                "offset": {},
                "result": {},
                "windows_open": False,
                "occupied": None,
                "warm": False,
                "calib_at": {},
                "valve_at": {},
            },
        )

    def _room_for(self, entity_id: str, key: str) -> list[str]:
        out = []
        for room_id, room in self.rooms.items():
            value = room.get(key)
            if (isinstance(value, list) and entity_id in value) or value == entity_id:
                out.append(room_id)
        return out

    @callback
    def _on_state_change(self, event: Event) -> None:
        entity_id = event.data["entity_id"]
        new = event.data.get("new_state")
        old = event.data.get("old_state")
        now = dt_util.utcnow().timestamp()

        if entity_id.startswith("climate.") and new is not None and old is not None:
            self._detect_manual_change(entity_id, old, new, now)

        # Geräte nicht mehr bzw. wieder erreichbar
        if new is not None and old is not None and (new.state in BAD_STATES) != (old.state in BAD_STATES):
            lost = new.state in BAD_STATES
            seen: set[str] = set()
            for key in ("climates", "windows", "temp_sensor", "humidity_sensor", "presence_sensor"):
                for room_id in self._room_for(entity_id, key):
                    if room_id in seen:
                        continue
                    seen.add(room_id)
                    self.log.add(
                        "health",
                        f"{new.name} {'nicht erreichbar' if lost else 'wieder erreichbar'}",
                        f"{entity_id} · Zustand {new.state}",
                        room_id,
                        self.rooms[room_id].get("name"),
                    )

        for room_id in self._room_for(entity_id, "windows"):
            room = self.rooms[room_id]
            rt = self._rt(room_id)
            is_open = self._windows_open_since(room)[0] is not None
            if new is not None and old is not None and new.state not in BAD_STATES and old.state not in BAD_STATES:
                was = old.state.lower() in WINDOW_OPEN_STATES
                now_open = new.state.lower() in WINDOW_OPEN_STATES
                if was != now_open:
                    self.log.add("window", f"{new.name} {'geöffnet' if now_open else 'geschlossen'}", None, room_id, room.get("name"))
            if is_open and not rt["windows_open"]:
                self._stat(room_id)["open"] += 1
                delay = room_setting(room, "window_delay") or 0
                async_call_later(self.hass, delay + 1, self._async_delayed_eval)
            elif not is_open and rt["windows_open"]:
                delay = room_setting(room, "resume_delay") or 0
                if delay:
                    async_call_later(self.hass, delay + 1, self._async_delayed_eval)
            rt["windows_open"] = is_open

        self._schedule_eval()

    def _detect_manual_change(self, entity_id: str, old, new, now: float) -> None:
        old_t = _float(old.attributes.get("temperature"))
        new_t = _float(new.attributes.get("temperature"))
        if new_t is None or old_t is None or abs(new_t - old_t) < 0.05:
            return
        for room_id in self._room_for(entity_id, "climates"):
            room = self.rooms[room_id]
            rt = self._rt(room_id)
            sent = rt["last_sent"].get(entity_id)
            if sent and (abs(sent[0] - new_t) < 0.05 or now - sent[1] < OWN_CHANGE_GRACE):
                continue
            if rt["paused"] or not room.get("enabled", True) or not room.get("allow_manual", True):
                continue
            if new.state == "off":
                continue
            # Herkunft: mit Benutzer = Home-Assistant-Oberfläche/App, ohne = am Gerät gedreht
            from_ui = getattr(new.context, "user_id", None) is not None
            if from_ui and room.get("manual_ui") is False:
                continue
            if not from_ui and room.get("manual_device") is False:
                continue
            offset = rt["offset"].get(entity_id, 0.0)
            minutes = (rt.get("result") or {}).get("next_change") or 240
            rt["override"] = {"temp": round(new_t - offset, 1), "until": now + minutes * 60}
            _LOGGER.debug("Manuelle Änderung in %s: %.1f °C", room.get("name"), new_t)
            self.log.add(
                "manual",
                f"Von Hand: {self._t(rt['override']['temp'])} °C",
                f"{'in Home Assistant geändert' if from_ui else 'am Thermostat gedreht'} ({new.name}) · gilt bis {self._hm(rt['override']['until'])}",
                room_id,
                room.get("name"),
            )

    @callback
    def _schedule_eval(self) -> None:
        if self._pending_eval is None:
            self._pending_eval = async_call_later(self.hass, 1, self._async_delayed_eval)

    async def _async_delayed_eval(self, _now=None) -> None:
        self._pending_eval = None
        await self.async_evaluate()

    async def _async_tick(self, _now=None) -> None:
        await self._async_refresh_plan_calendars()
        await self.async_evaluate()
        self._record_stats()

    # ------------------------------------------------------------ Messwerte
    def _windows_open_since(self, room: dict) -> tuple[float | None, float | None]:
        opened: list[float] = []
        closed: list[float] = []
        for entity_id in room.get("windows") or []:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in BAD_STATES:
                continue
            ts = state.last_changed.timestamp()
            (opened if state.state.lower() in WINDOW_OPEN_STATES else closed).append(ts)
        if opened:
            return min(opened), None
        return None, (max(closed) if closed else None)

    def _room_values(self, room: dict) -> tuple[float | None, float | None]:
        temp = None
        if room.get("temp_sensor"):
            state = self.hass.states.get(room["temp_sensor"])
            temp = _float(state.state) if state else None
        if temp is None:
            values = []
            for entity_id in room.get("climates") or []:
                state = self.hass.states.get(entity_id)
                if state is not None:
                    value = _float(state.attributes.get("current_temperature"))
                    if value is not None:
                        values.append(value)
            temp = round(sum(values) / len(values), 1) if values else None
        humidity = None
        if room.get("humidity_sensor"):
            state = self.hass.states.get(room["humidity_sensor"])
            humidity = _float(state.state) if state else None
        return temp, humidity

    def _is_heating(self, room: dict, room_temp: float | None, target: float | None) -> bool:
        actions = []
        for entity_id in room.get("climates") or []:
            state = self.hass.states.get(entity_id)
            if state is not None and state.attributes.get("hvac_action") is not None:
                actions.append(state.attributes["hvac_action"])
        if actions:
            return "heating" in actions
        if room_temp is None or target is None:
            return False
        return room_temp < target - 0.2

    def _effective_room(self, room: dict) -> dict:
        """Raum mit gemeinsamem Heizplan und Komfort-/Eco-Temperatur aus Helfer-Entitäten, falls gewählt."""
        out = room
        plan = self.plans.get(room.get("plan_id") or "")
        if plan is not None and not room.get("schedule_entity"):
            out = dict(room)
            out["schedule"] = plan.get("schedule") or []
        for key in ("comfort", "eco"):
            value = self._state_float(room.get(f"{key}_entity"))
            if value is not None and MIN_TEMP <= value <= MAX_TEMP:
                if out is room:
                    out = dict(room)
                out[key] = value
        return out

    def _occupancy(self, room: dict, rt: dict, now: float) -> bool | None:
        sensor = room.get("presence_sensor")
        if not sensor:
            return None
        # Präsenzmelder nur innerhalb seines Zeitplans berücksichtigen (falls gewählt)
        window = room.get("presence_schedule")
        if window:
            win_state = self.hass.states.get(window)
            if win_state is not None and win_state.state == "off":
                return None
        state = self.hass.states.get(sensor)
        if state is None or state.state in BAD_STATES:
            return rt.get("occupied")
        return occupied(
            state.state == "on",
            now - state.last_changed.timestamp(),
            rt.get("occupied"),
            float(room_setting(room, "presence_on") or 0) * 60,
            float(room_setting(room, "presence_off") or 0) * 60,
        )

    def _schedule_entity(self, room: dict, now: float) -> tuple[bool | None, int | None]:
        """Zustand eines Zeitplans oder Kalenders: (an?, Minuten bis zum nächsten Einschalten).

        schedule.*: next_event ist der nächste Wechsel. calendar.*: an, solange ein Termin
        läuft; ist keiner aktiv, steht der nächste Termin in start_time.
        """
        cal_plan = self._calendar_plan(room)
        if cal_plan is not None:
            events = self._plan_events.get(cal_plan["id"]) or []
            return calendar_state([(e["start"], e["end"]) for e in events], now)
        entity_id = room.get("schedule_entity")
        if not entity_id:
            return None, None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in BAD_STATES:
            return False, None
        is_on = state.state == "on"
        if entity_id.startswith("calendar."):
            if is_on or state.attributes.get("all_day"):
                return is_on, None
            start, _ = self._parse_when(state.attributes.get("start_time"))
            return is_on, minutes_until(start, now)
        nxt = minutes_until(state.attributes.get("next_event"), now)
        return is_on, nxt

    def _preheat(
        self, room_id: str, room: dict, room_temp: float | None, week_min: int, schedule_next_on: int | None = None
    ) -> tuple[int, float | None, tuple[int, float] | None]:
        """Vorlaufzeit: aus, fest eingestellt oder aus der gelernten Aufheizgeschwindigkeit."""
        mode = self._preheat_mode(room)
        if mode == "off":
            return 0, None, None
        if mode != "smart":
            return self._fixed_lead(room), None, None
        max_lead = int(room_setting(room, "preheat_max") or 90)
        rate = self.heat_rates.get(room_id) or float(room_setting(room, "heat_rate") or 1.0)
        if room.get("schedule_entity") or self._calendar_plan(room) is not None:
            comfort = float(room.get("comfort", 21))
            upcoming = (schedule_next_on, comfort) if schedule_next_on is not None and schedule_next_on <= max_lead else None
        else:
            upcoming = next_comfort(room.get("schedule") or [], week_min, float(room.get("comfort", 21)), max_lead)
        target = upcoming[1] if upcoming else float(room.get("comfort", 21))
        return smart_lead(room_temp, target, rate, max_lead), rate, upcoming

    def _preheat_mode(self, room: dict) -> str:
        """Vorheizen des Raums, sonst die Einstellung für alle Räume."""
        return room.get("preheat_mode") or self.settings.get("preheat_mode") or "fixed"

    def _fixed_lead(self, room: dict) -> int:
        """Feste Vorlaufzeit: Wert des Raums, sonst der allgemeine Wert seiner Heizungsart."""
        if room.get("lead_min") is not None:
            return int(room["lead_min"])
        key = "lead_radiator" if room.get("type", TYPE_RADIATOR) == TYPE_RADIATOR else "lead_floor"
        value = self.settings.get(key)
        return int(value if value is not None else room_setting(room, "lead_min") or 0)

    def _learn(self, room_id: str, rt: dict, result: dict, room_temp: float | None, now: float) -> None:
        """Misst Aufheizvorgänge: von Beginn (≥ 1 K unter Soll) bis zum Erreichen des Solls."""
        run = rt.get("learn")
        heating_up = result["mode"] in ("vorheizen", "komfort", "belegt", "party") and room_temp is not None
        if not heating_up or result["target"] is None:
            rt["learn"] = None
            return
        if run is None:
            if result["target"] - room_temp >= 1.0:
                rt["learn"] = {"ts": now, "temp": room_temp, "target": result["target"]}
            return
        if abs(result["target"] - run["target"]) > 0.6 or now - run["ts"] > 8 * 3600:
            rt["learn"] = None  # Ziel geändert oder zu lange: Messung verwerfen
            return
        if room_temp >= run["target"] - 0.2:
            rate = learn_rate(self.heat_rates.get(room_id), run["temp"], room_temp, (now - run["ts"]) / 3600)
            if rate is not None:
                self.heat_rates[room_id] = rate
                self._save()
                _LOGGER.debug("Aufheizgeschwindigkeit %s: %.2f K/h", room_id, rate)
            rt["learn"] = None

    def _device_numbers(
        self, climate_id: str, words: tuple[str, ...], explicit: list[str] | None = None, single: bool = False
    ) -> list[str]:
        """number-Entitäten zum Thermostat.

        Selbst gewählte Entitäten (explicit) gehen vor: genommen werden die am selben Gerät,
        bei nur einem Thermostat im Raum alle gewählten. Sonst automatisch am Gerät über die Wörter.
        """
        registry = er.async_get(self.hass)
        entry = registry.async_get(climate_id)
        device_id = entry.device_id if entry is not None else None
        if explicit:
            same = [
                n for n in explicit
                if device_id is not None and (ne := registry.async_get(n)) is not None and ne.device_id == device_id
            ]
            return same or (list(explicit) if single else [])
        if device_id is None:
            return []
        return [
            e.entity_id
            for e in er.async_entries_for_device(registry, device_id)
            if e.domain == "number" and e.disabled_by is None and any(w in e.entity_id for w in words)
        ]

    # ------------------------------------------------------------ Regelung
    async def async_evaluate(self) -> None:
        now_local = dt_util.now()
        now = dt_util.utcnow().timestamp()
        week_min = week_minute(now_local.weekday(), now_local.hour, now_local.minute)
        self.haus.update()
        away = self.haus.away
        vacation = self.haus.vacation
        outside = self.haus.outside_temp()
        party = bool(self.settings.get("party"))

        summer_mode = self.settings.get("summer_mode") or "off"
        if summer_mode == "on":
            self._summer = True
        elif summer_mode == "auto":
            self._summer = summer_state(
                outside,
                float(self.settings.get("summer_temp") or 16),
                self._summer,
                fallback=self.settings.get("summer_fallback") or "keep",
            )
        elif summer_mode == "entity":
            # Heizperiode aus einer Entität: an = heizen, aus = Sommerpause
            season = self.hass.states.get(self.settings.get("season_entity") or "")
            if season is not None and season.state in ("on", "off"):
                self._summer = season.state == "off"
            elif (self.settings.get("summer_fallback") or "keep") != "keep":
                self._summer = self.settings.get("summer_fallback") == "summer"
        else:
            self._summer = False
        force_eco = bool(self.settings.get("eco_force"))
        long_days = float(self.settings.get("long_away_days") or 0)
        long_away = away and long_days > 0 and self.haus.away_for >= long_days * 86400
        self._long_away = long_away
        # Entkalken im Sommer – oder immer, wenn so eingestellt bzw. keine Sommerpause genutzt wird.
        self._liming = liming_active(self.settings, week_min) and (
            self._summer or bool(self.settings.get("liming_winter")) or summer_mode == "off"
        )

        # Wechsel der Hauszustände ins Protokoll
        self._flip("long_away", long_away, "Lange niemand da – Frostschutz", None, "presence",
                   f"seit {self.haus.away_for / 86400:.1f} Tagen".replace(".", ","))
        self._flip("summer", self._summer, "Sommerpause beginnt", "Heizperiode beginnt", "season",
                   f"außen {self._t(outside)} °C · Heizgrenze {self._t(float(self.settings.get('summer_temp') or 16))} °C"
                   if summer_mode == "auto" else {"on": "von Hand", "entity": "laut Entität"}.get(summer_mode, ""))
        self._flip("liming", self._liming, "Entkalken: alle Ventile auf", "Entkalken beendet", "season",
                   f"{int(self.settings.get('liming_minutes') or 5)} Min. Entkalkungsschutz")

        for room_id, stored_room in list(self.rooms.items()):
            room = self._effective_room(stored_room)
            rt = self._rt(room_id)
            open_since, closed_since = self._windows_open_since(room)
            rt["windows_open"] = open_since is not None
            paused = window_paused(
                open_since,
                closed_since,
                rt["paused"],
                now,
                float(room_setting(room, "window_delay") or 0),
                float(room_setting(room, "resume_delay") or 0),
            )
            if paused != rt["paused"]:
                if paused:
                    rt["pause_at"] = now
                    names = [
                        self._name(w) for w in room.get("windows") or []
                        if (s := self.hass.states.get(w)) is not None and s.state.lower() in WINDOW_OPEN_STATES
                    ]
                    why = f"{', '.join(names) or 'Fenster'} offen · Thermostate " + ("aus" if room_setting(room, "pause_mode") == "off" else "auf Frostschutz")
                    self.log.add("window", "Fensterpause beginnt", why, room_id, room.get("name"))
                else:
                    mins = int((now - rt.get("pause_at", now)) // 60)
                    self.log.add("window", "Fensterpause endet", f"alle Fenster zu · Pause dauerte {mins} Min.", room_id, room.get("name"))
            rt["paused"] = paused

            override = rt.get("override")
            if override and override.get("until") and now >= override["until"]:
                rt["override"] = override = None

            room_temp, humidity = self._room_values(room)
            rt["occupied"] = self._occupancy(room, rt, now)
            schedule_on, schedule_next_on = self._schedule_entity(room, now)
            lead, rate, upcoming = self._preheat(room_id, room, room_temp, week_min, schedule_next_on)
            result = compute_target(
                room,
                self.settings,
                week_min,
                window_paused=paused,
                away=away,
                vacation=vacation,
                override=override["temp"] if override else None,
                boost=bool(override and override.get("boost")),
                party=party,
                summer=self._summer,
                liming=self._liming,
                occupied=rt["occupied"],
                room_temp=room_temp,
                was_warm=rt["warm"],
                lead=lead,
                force_eco=force_eco,
                long_away=long_away,
                schedule_on=schedule_on,
                schedule_next_on=schedule_next_on,
            )
            rt["warm"] = result["mode"] == "warm"
            self._learn(room_id, rt, result, room_temp, now)
            result.update(
                preheat_mode=self._preheat_mode(room),
                plan_name=(self.plans.get(room.get("plan_id") or "") or {}).get("name"),
                preheat_lead=lead,
                heat_rate=rate,
                learned=room_id in self.heat_rates,
                comfort_in=upcoming[0] if upcoming else None,
                occupied=rt["occupied"],
                comfort=room.get("comfort"),
                eco=room.get("eco"),
                mode_label=MODES[result["mode"]],
                room_temp=room_temp,
                humidity=humidity,
                windows_open=open_since is not None,
                window_pending=open_since is not None and not paused,
                override_until=(
                    dt_util.utc_from_timestamp(override["until"]).isoformat()
                    if override and override.get("until")
                    else None
                ),
                heating=self._is_heating(room, room_temp, result["target"]),
            )
            rt["result"] = result
            # Entscheidung protokollieren, sobald sich Betriebsart oder Ziel ändern
            current = (result["mode"], result["target"], result["hvac_off"])
            before = rt.get("logged")
            if before != current:
                rt["logged"] = current
                if result["target"] is None:
                    what = "Automatik aus"
                elif result["hvac_off"]:
                    what = "Thermostate aus"
                else:
                    what = f"Ziel {self._t(result['target'])} °C"
                reason = self._reason(room, result, upcoming)
                self.log.add(
                    "target",
                    ("Start: " if before is None else "") + what,
                    MODES[result["mode"]] + (f" – {reason}" if reason else ""),
                    room_id,
                    room.get("name"),
                )
            try:
                await self._apply(room, rt, result, room_temp, now)
            except Exception:  # noqa: BLE001 - ein defektes Thermostat soll die anderen nicht stoppen
                _LOGGER.exception("Fehler beim Regeln von %s", room.get("name"))

        status = self.status()
        for cb in list(self._subscribers):
            cb(status)
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    async def _apply(self, room: dict, rt: dict, result: dict, room_temp: float | None, now: float) -> None:
        if result["target"] is None:  # Automatik aus
            for entity_id in room.get("climates") or []:
                if entity_id in self.turned_off:
                    await self._restore_mode(entity_id, room)
            return
        for entity_id in room.get("climates") or []:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in BAD_STATES:
                continue

            if result["hvac_off"] and room.get("min_instead_of_off"):
                # Statt Ausschalten auf die kleinste Temperatur des Thermostats stellen.
                if entity_id in self.turned_off:
                    await self._restore_mode(entity_id, room)
                low = dict(result, target=MIN_TEMP)
                await self._set_temperature(room, rt, low, room_temp, now, entity_id)
                await self._set_valve(room, rt, low, room_temp, now, entity_id)
                continue

            if result["hvac_off"]:
                if state.state != "off":
                    self.turned_off[entity_id] = state.state
                    self._save()
                    await self.hass.services.async_call(
                        "climate", "set_hvac_mode", {"entity_id": entity_id, "hvac_mode": "off"}
                    )
                    self.log.add("command", f"{self._name(entity_id)} → aus", MODES[result["mode"]], room.get("id"), room.get("name"))
                continue

            if entity_id in self.turned_off:
                await self._restore_mode(entity_id, room)
            elif state.state == "off":
                continue  # vom Nutzer ausgeschaltet: respektieren

            await self._calibrate(room, rt, room_temp, now, entity_id)
            await self._set_temperature(room, rt, result, room_temp, now, entity_id)
            await self._set_valve(room, rt, result, room_temp, now, entity_id)

    async def _calibrate(self, room: dict, rt: dict, room_temp: float | None, now: float, entity_id: str) -> None:
        """Offset des Thermostats so setzen, dass es die Temperatur des Raumsensors misst."""
        if not room.get("calibration") or not room.get("temp_sensor"):
            return
        interval = float(self.settings.get("calibration_interval") or 10) * 60
        if now - rt["calib_at"].get(entity_id, 0) < interval:
            return
        state = self.hass.states.get(entity_id)
        if state is None:
            return
        single = len(room.get("climates") or []) == 1
        for number_id in self._device_numbers(entity_id, CALIBRATION_WORDS, room.get("calibration_entities"), single):
            number = self.hass.states.get(number_id)
            if number is None or number.state in BAD_STATES:
                continue
            new = calibration_offset(
                room_temp,
                _float(state.attributes.get("current_temperature")),
                _float(number.state) or 0.0,
                _float(number.attributes.get("step")) or 0.1,
                _float(number.attributes.get("min")) or -5.0,
                _float(number.attributes.get("max")) or 5.0,
            )
            rt["calib_at"][entity_id] = now
            if new is not None:
                await self.hass.services.async_call(
                    "number", "set_value", {"entity_id": number_id, "value": new}
                )
                self.log.add("command", f"{self._name(number_id)} → Offset {self._t(new)} °C",
                             f"Raumsensor {self._t(room_temp)} °C", room.get("id"), room.get("name"))
            return

    async def _set_valve(
        self, room: dict, rt: dict, result: dict, room_temp: float | None, now: float, entity_id: str
    ) -> None:
        """Ventilöffnung direkt vorgeben (für Thermostate mit Ventil-Entität)."""
        if not room.get("valve_control"):
            return
        max_open = float(room_setting(room, "valve_max") or 100)
        if result["mode"] == "entkalken":
            value: float | None = 100.0
        else:
            value = valve_opening(
                result["target"], room_temp, float(room_setting(room, "valve_diff") or 1.5), max_open
            )
        if value is None:
            return
        single = len(room.get("climates") or []) == 1
        for number_id in self._device_numbers(entity_id, VALVE_WORDS, room.get("valve_entities"), single):
            number = self.hass.states.get(number_id)
            if number is None or number.state in BAD_STATES:
                continue
            current = _float(number.state)
            changed_a_lot = current is None or abs(current - value) >= 30
            if current is not None and abs(current - value) < 1:
                continue
            if not changed_a_lot and now - rt["valve_at"].get(number_id, 0) < VALVE_INTERVAL:
                continue
            rt["valve_at"][number_id] = now
            await self.hass.services.async_call(
                "number", "set_value", {"entity_id": number_id, "value": value}
            )
            self.log.add("command", f"{self._name(number_id)} → Ventil {value:.0f} %",
                         MODES[result["mode"]], room.get("id"), room.get("name"))

    async def _restore_mode(self, entity_id: str, room: dict | None = None) -> None:
        previous = self.turned_off.pop(entity_id, None) or "heat"
        self._save()
        await self.hass.services.async_call(
            "climate", "set_hvac_mode", {"entity_id": entity_id, "hvac_mode": previous}
        )
        room = room or {}
        self.log.add("command", f"{self._name(entity_id)} → wieder {previous}", "vorheriger Modus nach der Pause", room.get("id"), room.get("name"))

    async def _set_temperature(
        self, room: dict, rt: dict, result: dict, room_temp: float | None, now: float, entity_id: str
    ) -> None:
        state = self.hass.states.get(entity_id)
        if state is None:
            return
        attrs = state.attributes
        target = result["target"]
        tunable = result["mode"] not in NO_TUNING_MODES and target > MIN_TEMP
        if tunable and result["mode"] != "boost":
            target = aggressive(
                target,
                room_temp,
                float(room_setting(room, "aggressive_range") or 0),
                float(room_setting(room, "aggressive_offset") or 0),
            )
        if tunable:
            # Fester Ausgleich für Thermostate, die dauerhaft zu warm/zu kalt regeln
            target += float(room.get("target_offset") or 0)
        use_comp = (
            bool(room_setting(room, "compensation"))
            and not room.get("calibration")
            and room.get("type", TYPE_RADIATOR) == TYPE_RADIATOR
            and bool(room.get("temp_sensor"))
            and tunable
        )
        if use_comp:
            target = compensated(target, _float(attrs.get("current_temperature")), room_temp)
        step = _float(attrs.get("target_temp_step")) or 0.5
        value = snap(target, step, _float(attrs.get("min_temp")), _float(attrs.get("max_temp")))
        rt["offset"][entity_id] = round(value - result["target"], 2)

        current = _float(attrs.get("temperature"))
        # Mit Kompensation erst ab einem ganzen Schritt nachführen, sonst pendelt der Sollwert.
        hysteresis = max(step, 0.5) if use_comp else 0.05
        if current is not None and abs(current - value) < hysteresis:
            return
        rt["last_sent"][entity_id] = (value, now)
        await self.hass.services.async_call(
            "climate", "set_temperature", {"entity_id": entity_id, "temperature": value}
        )
        extra = f" · gesendet {self._t(value)} °C (Ausgleich)" if abs(value - result["target"]) >= 0.05 else ""
        self.log.add("command", f"{self._name(entity_id)} → {self._t(value)} °C",
                     f"Ziel {self._t(result['target'])} °C · {MODES[result['mode']]}{extra}", room.get("id"), room.get("name"))

    # ------------------------------------------------------------ Statistik
    def _stat(self, room_id: str) -> dict[str, float]:
        day = dt_util.now().date().isoformat()
        return self.stats.setdefault(room_id, {}).setdefault(
            day, {"heat": 0, "pause": 0, "open": 0, "tsum": 0.0, "tn": 0, "comfort": 0}
        )

    def _record_stats(self) -> None:
        cutoff = (dt_util.now().date() - timedelta(days=STATS_DAYS)).isoformat()
        for room_id in self.rooms:
            result = self._rt(room_id).get("result") or {}
            bucket = self._stat(room_id)
            if result.get("heating"):
                bucket["heat"] += 1
            if result.get("mode") == "fenster":
                bucket["pause"] += 1
            if result.get("mode") in COMFORT_MODES:
                bucket["comfort"] += 1
            if result.get("room_temp") is not None:
                bucket["tsum"] += result["room_temp"]
                bucket["tn"] += 1
            for day in [d for d in self.stats[room_id] if d < cutoff]:
                del self.stats[room_id][day]
        self._save(30)

    def report(self, days: int) -> dict[str, list[dict[str, Any]]]:
        start = dt_util.now().date() - timedelta(days=days - 1)
        out: dict[str, list[dict[str, Any]]] = {}
        for room_id in self.rooms:
            rows = []
            room_stats = self.stats.get(room_id, {})
            for i in range(days):
                day = (start + timedelta(days=i)).isoformat()
                b = room_stats.get(day) or {}
                rows.append(
                    {
                        "date": day,
                        "heat_min": b.get("heat", 0),
                        "pause_min": b.get("pause", 0),
                        "comfort_min": b.get("comfort", 0),
                        "openings": b.get("open", 0),
                        "avg_temp": round(b["tsum"] / b["tn"], 1) if b.get("tn") else None,
                    }
                )
            out[room_id] = rows
        return out
