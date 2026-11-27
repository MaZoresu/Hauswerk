"""Hauswerk-Modul Heizwerk: Regelung, Speicher und Statistik.

Anwesenheit, Urlaub und Außentemperatur kommen aus dem Hauswerk-Kern (core.Haus).
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any
import uuid

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CALL_SERVICE, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
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
from .logic import degree_days, morning_vent_done, punctual_summary, savings_summary
from .logic import (
    MAX_TEMP,
    MIN_TEMP,
    MODES,
    TYPE_RADIATOR,
    aggressive,
    assist_on,
    calendar_state,
    calibration_offset,
    compensated,
    battery_level,
    cold_radiator,
    vent_balance,
    vent_helps,
    vent_learned_minutes,
    vent_plan,
    vent_tau,
    next_dry_hour,
    compute_target,
    demand_state,
    VALVE_ATTRS,
    VALVE_SKIP,
    VALVE_WORDS as VALVE_SENSOR_WORDS,
    drop_within,
    events_to_blocks,
    find_references,
    holiday_week_minute,
    keyword_match,
    keywords,
    learn_rate,
    block_conflicts,
    block_value,
    day_segments,
    resolve_overlaps,
    extra_heat_rise,
    fireplace_phase,
    room_analysis,
    liming_active,
    minutes_until,
    next_comfort,
    smart_lead,
    occupied,
    radio_should_send,
    retry_wait,
    abs_humidity,
    abs_rise_points,
    rise_within,
    room_setting,
    snap,
    summer_state,
    hourly_mean,
    thermostat_kind,
    valve_opening,
    ventilate_advice,
    parse_hm,
    vent_done,
    vent_limit,
    vent_minutes,
    mold_risk,
    window_loss_kwh,
    weather_lead_factor,
    week_minute,
    window_paused,
)
from .core import Haus, async_calendar_events, parse_when
from .hmlinks import HmLinks, analyze_room, findings as link_findings, peer_kind
from .log import Protokoll, log_settings

_LOGGER = logging.getLogger(__name__)

BAD_STATES = {STATE_UNAVAILABLE, STATE_UNKNOWN, None}
OWN_CHANGE_GRACE = 20  # Sekunden, in denen Änderungen am Thermostat als eigene gelten
VALVE_INTERVAL = 300  # Sekunden zwischen zwei Ventilstellungen
CALIBRATION_WORDS = ("calibration", "offset", "kalibrier")
VALVE_WORDS = ("valve", "position", "opening", "ventil")
CONFLICT_WRITES = 3  # so viele fremde Befehle ...
CONFLICT_WINDOW = 2 * 3600  # ... innerhalb dieser Zeit gelten als zweite Regelung
PAIR_GRACE = 900  # Sekunden, die ein gekoppeltes Heizkörper-Thermostat vom Wandthermostat abweichen darf
RETRY_CONFIRM = 45  # s: so lange darf ein gesendeter Sollwert brauchen, bis er im Zustand steht
CLIMATE_SERVICES = {"set_temperature", "set_hvac_mode", "set_preset_mode", "turn_on", "turn_off", "toggle"}
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
        self._outside_mean: float | None = None
        self._lead_factor = 1.0
        # Batterie-Entitäten je Raum (an den Geräten der Thermostate, Fenster und Sensoren)
        self._batteries: dict[str, list[str]] = {}
        # Eigene Befehle (Context-IDs), um sie von fremden zu unterscheiden
        self._own_ctx: dict[str, float] = {}
        # Fremde Befehle an unsere Thermostate: entity_id -> [(Zeit, Herkunft)] und deren Context-IDs
        self._foreign: dict[str, list[tuple[float, str]]] = {}
        self._foreign_ctx: dict[str, str] = {}
        # Andere Regelungen, die unsere Thermostate in ihren Attributen nennen: entity_id -> [{id, name, platform}]
        self._refs: dict[str, list[dict[str, str]]] = {}
        self._refs_at = 0.0
        # Art des Thermostats (wall/trv/None) und Duty-Cycle-Melder am Gerät
        self._kinds: dict[str, str | None] = {}
        # Direktverknüpfungen der Homematic-CCU (nur lesen): Raum → Analyse, Hinweise
        self.hmlinks = HmLinks(hass)
        self._links: dict[str, dict] = {}
        self._link_findings: list[dict] = []
        self._links_next = 0.0
        self._ventdone_sent: dict[str, tuple[str, int]] = {}  # „Fenster schließen“ je Raum: (Tag, wie oft gesendet)
        self._dev_duty: dict[str, list[str]] = {}
        # Gesendete Befehle (Zeitpunkte) für die Funk-Anzeige
        self._sent_at: list[float] = []
        # Quellen der Ventilöffnung je Raum (Thermostate, %-Sensoren am Gerät, Anzeige-Geräte)
        self._valve_src: dict[str, list[str]] = {}
        # Wärmeanforderung: Zustand (low/normal/raise), gemerkte Werte des Wärmeerzeugers
        self.demand: dict[str, Any] = {}
        self._no_need_since: float | None = None

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
        self.demand = stored.get("demand") or {}
        # Außentemperatur je Stunde (Summe, Anzahl) für die Sommerpause nach Tagesmittel – übersteht Neustarts
        self.outside_hours: dict[str, list] = stored.get("outside_hours") or {}
        # Lüftungen je Raum (14 Tage): Beginn, Dauer, Feuchte und Temperatur vorher/nachher, Wärmeverlust
        self.vent_log: dict[str, list] = stored.get("vent_log") or {}
        self.rh_morning: dict[str, dict[str, float]] = stored.get("rh_morning") or {}  # Raum → Tag → höchste Feuchte 5–9 Uhr
        # gelernter Luftwechsel je Raum: Zeitkonstante τ (Min.) aus den letzten Lüftungen
        self.vent_tau: dict[str, list[float]] = stored.get("vent_tau") or {}
        # „Kamin in Betrieb“ von Hand: Raum → gilt bis (Zeitstempel); übersteht Neustarts
        self.fire_manual: dict[str, float] = stored.get("fire_manual") or {}
        # Lüften übersteht Neustarts: seit wann ein Fenster offen ist (last_changed beginnt nach dem Start neu),
        # laufende Lüftungen (Timer, „genug gelüftet“, Nacht) und wie oft „Fenster schließen“ heute kam
        self.win_open: dict[str, float] = stored.get("win_open") or {}
        for rid, vs in (stored.get("vent_sessions") or {}).items():
            if vs and rid in self.rooms:
                self._rt(rid)["vs"] = vs
        self._ventdone_sent = {k: tuple(v) for k, v in (stored.get("ventdone_sent") or {}).items()}
        self._plans_fixed = self._fix_schedules()

    @staticmethod
    def _plan_today(room: dict, plan_min: int) -> list[dict]:
        """Heutiger Plan-Tagesablauf (wie Zeitleiste und Steuerung rechnen): [{start, end, target, kind, custom}]."""
        return day_segments(room.get("schedule") or [], (plan_min // 1440) % 7,
                            float(room.get("comfort", 21)), float(room.get("eco", 18)))

    def _fix_schedules(self) -> list[str]:
        """Heizpläne ins neue Modell überführen: überschneidungsfreie Zeitfenster.
        Früher galt bei Überschneidung der höhere Wert – genau so wird aufgelöst (Komfort vor Eco, höhere Temperatur
        zuerst, bei Gleichstand das obere Fenster). Fenster mit Beginn = Ende (früher 24 Std.) werden bis Mitternacht
        und ab Mitternacht geteilt. Rückgabe: geänderte Pläne (für das Protokoll)."""
        changed = []

        def fix(blocks: list[dict], comfort: float) -> list[dict] | None:
            if not blocks:
                return None
            out, split = [], False
            for b in blocks:
                if b.get("start") == b.get("end") and b.get("start") not in ("00:00", None):
                    days = b.get("days") or list(range(7))
                    out.append({**b, "end": "24:00"})
                    out.append({**b, "start": "00:00", "end": b["start"], "days": sorted({(d + 1) % 7 for d in days})})
                    split = True
                else:
                    out.append(b)
            if not split and not block_conflicts(out):
                return None
            value = lambda i: (out[i].get("kind") != "eco", block_value(out[i].get("kind") or "comfort", out[i].get("temp"), comfort, 0), -i)  # noqa: E731
            return resolve_overlaps(out, value)

        for room in self.rooms.values():
            new = fix(room.get("schedule") or [], float(room.get("comfort") or 21))
            if new is not None:
                room["schedule"] = new
                changed.append(f"Raum „{room.get('name')}“")
        for plan in self.plans.values():
            comforts = [float(r.get("comfort") or 21) for r in self.rooms.values() if r.get("plan_id") == plan.get("id")]
            new = fix(plan.get("schedule") or [], max(comforts) if comforts else 21.0)
            if new is not None:
                plan["schedule"] = new
                changed.append(f"Plan „{plan.get('name')}“")
        return changed

    def _data(self) -> dict[str, Any]:
        return {
            "settings": self.settings,
            "rooms": self.rooms,
            "plans": self.plans,
            "stats": self.stats,
            "turned_off": self.turned_off,
            "heat_rates": self.heat_rates,
            "demand": self.demand,
            "outside_hours": self.outside_hours,
            "vent_log": self.vent_log,
            "rh_morning": self.rh_morning,
            "vent_tau": self.vent_tau,
            "fire_manual": self.fire_manual,
            "win_open": self.win_open,
            "vent_sessions": {rid: rt["vs"] for rid, rt in self.runtime.items() if rt.get("vs")},
            "ventdone_sent": {k: list(v) for k, v in self._ventdone_sent.items()},
        }

    def _note_outside(self, outside: float | None) -> None:
        """Außentemperatur in den Stundenwert einrechnen (für das Tagesmittel), höchstens 4 Tage aufheben."""
        if outside is None:
            return
        hour = int(dt_util.utcnow().timestamp() // 3600)
        cur = self.outside_hours.get(str(hour))
        if cur is None:
            for key in [k for k in self.outside_hours if int(k) <= hour - 96]:
                del self.outside_hours[key]
            self.outside_hours[str(hour)] = [round(outside, 2), 1]
            self._save(60)
        else:
            cur[0] = round(cur[0] + outside, 2)
            cur[1] += 1

    def _save(self, delay: float = 2) -> None:
        self._store.async_delay_save(self._data, delay)

    # ------------------------------------------------------------ Lebenszyklus
    async def async_start(self) -> None:
        self._unsubs.append(
            async_track_time_interval(self.hass, self._async_tick, timedelta(minutes=1))
        )
        self._track_entities()
        self._unsubs.append(self.hass.bus.async_listen(EVENT_CALL_SERVICE, self._on_service_call))
        # Änderungen von Anwesenheit, Urlaub und zentralen Einstellungen
        self._unsubs.append(self.haus.subscribe(self._schedule_eval))
        if self._plans_fixed:
            self.log.add("settings", "Heizpläne bereinigt",
                         f"{', '.join(self._plans_fixed)}: sich überschneidende Zeitfenster aufgeteilt – wie bisher gilt dort der "
                         "höhere Wert, jetzt eindeutig. Zeiten ohne Zeitfenster sind Eco.")
            self._plans_fixed = []
            self._save()
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
        for entity_id in (self.haus.settings.get("outside_sensor"), self.settings.get("season_entity"),
                          self.haus.settings.get("workday_entity")):
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
        self._find_batteries()
        self._kinds = {}
        self._find_duty_flags()
        self._find_valves()
        self._refs_at = 0.0

    def _find_duty_flags(self) -> None:
        """Duty-Cycle-Melder (binary_sensor) am Gerät jedes Thermostats, z. B. Homematic IP."""
        registry = er.async_get(self.hass)
        self._dev_duty = {}
        for room in self.rooms.values():
            for entity_id in room.get("climates") or []:
                entry = registry.async_get(entity_id)
                if entry is None or not entry.device_id:
                    continue
                self._dev_duty[entity_id] = [
                    e.entity_id for e in er.async_entries_for_device(registry, entry.device_id)
                    if e.domain == "binary_sensor" and "duty_cycle" in e.entity_id and e.disabled_by is None
                ]

    # ------------------------------------------------------------ Ventile
    def _find_valves(self) -> None:
        """Woher die Ventilöffnung eines Raums kommt: Thermostate, %-Sensoren an deren Geräten, Anzeige-Geräte."""
        registry = er.async_get(self.hass)
        self._valve_src = {}
        for room_id, room in self.rooms.items():
            src: list[str] = []
            for entity_id in list(room.get("climates") or []) + list(room.get("show_entities") or []):
                src.append(entity_id)
                if not entity_id.startswith("climate."):
                    continue
                entry = registry.async_get(entity_id)
                if entry is None or not entry.device_id:
                    continue
                siblings = [
                    e for e in er.async_entries_for_device(registry, entry.device_id)
                    if e.entity_id != entity_id and e.disabled_by is None and e.domain in ("sensor", "number")
                    and VALVE_SENSOR_WORDS.search(f"{e.entity_id} {getattr(e, 'original_name', None) or ''} {getattr(e, 'translation_key', None) or ''}")
                    and not VALVE_SKIP.search(e.entity_id)
                ]
                sensors = [e.entity_id for e in siblings if e.domain == "sensor"]
                src.extend(sensors or [e.entity_id for e in siblings if e.domain == "number"])
            self._valve_src[room_id] = list(dict.fromkeys(src))

    def _valve_of(self, entity_id: str) -> tuple[float | None, bool]:
        """Öffnung in % einer Quelle und ob es ein Heizkörper-Ventil ist (False = Schalter/Fußbodenheizung)."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in BAD_STATES:
            return None, True
        domain = entity_id.split(".", 1)[0]
        attrs = state.attributes
        if domain == "climate":
            for key in VALVE_ATTRS:
                value = _float(attrs.get(key))
                if value is not None:
                    return value, True
            return None, True
        if domain in ("switch", "input_boolean"):
            return (100.0 if state.state == "on" else 0.0), False
        if domain in ("valve", "cover"):
            return _float(attrs.get("current_position")), True
        if attrs.get("unit_of_measurement") == "%" or domain == "number":
            return _float(state.state), True
        return None, True

    def _valves(self, room_id: str) -> tuple[float | None, float | None]:
        """(höchste Heizkörper-Ventilöffnung, höchste Öffnung inkl. Fußbodenheizung) eines Raums."""
        radiator: list[float] = []
        every: list[float] = []
        for entity_id in self._valve_src.get(room_id) or []:
            value, is_valve = self._valve_of(entity_id)
            if value is None:
                continue
            every.append(value)
            if is_valve:
                radiator.append(value)
        return (max(radiator) if radiator else None), (max(every) if every else None)

    def _floor_valve(self, room_id: str) -> float | None:
        """Öffnung der Fußbodenheizung (Stellantrieb an = 100 %) – ohne die Zusatz-Heizkörper des Mischbetriebs."""
        room = self.rooms.get(room_id) or {}
        assist = set(room.get("assist_entities") or [])
        reg = er.async_get(self.hass)
        adev = {e.device_id for a in assist if (e := reg.async_get(a)) and e.device_id}
        vals = []
        for entity_id in self._valve_src.get(room_id) or []:
            if entity_id in assist:
                continue
            ent = reg.async_get(entity_id)
            if ent and ent.device_id in adev:
                continue
            value, _is_valve = self._valve_of(entity_id)
            if value is not None:
                vals.append(value)
        return max(vals) if vals else None

    def _duty_blocked(self, entity_id: str) -> bool:
        return any(
            (s := self.hass.states.get(b)) is not None and s.state == "on" for b in self._dev_duty.get(entity_id) or []
        )

    # ------------------------------------------------------------ Eigene und fremde Befehle
    async def _call(self, domain: str, service: str, data: dict[str, Any]) -> None:
        """Dienst aufrufen und als eigenen Befehl merken."""
        now = dt_util.utcnow().timestamp()
        ctx = self.haus.own_context("Heizwerk")
        self._own_ctx[ctx.id] = now
        if len(self._own_ctx) > 300:
            self._own_ctx = {k: v for k, v in self._own_ctx.items() if now - v < 600}
        self._sent_at = [x for x in self._sent_at if now - x < 3600] + [now]
        await self.hass.services.async_call(domain, service, data, context=ctx)

    def _controlled(self) -> set[str]:
        out: set[str] = set()
        for room in self.rooms.values():
            out.update(room.get("climates") or [])
        return out

    def _origin(self, context) -> str:
        """Herkunft eines fremden Befehls: Automation oder Skript (über den auslösenden Context), sonst andere Integration."""
        parent = getattr(context, "parent_id", None)
        if parent:
            for domain in ("automation", "script"):
                for state in self.hass.states.async_all(domain):
                    if getattr(state.context, "id", None) == parent:
                        return f"{'Automation' if domain == 'automation' else 'Skript'} „{state.name}“"
            return "Automation oder Skript"
        return "andere Integration"

    @callback
    def _on_service_call(self, event: Event) -> None:
        data = event.data or {}
        if data.get("domain") != "climate" or data.get("service") not in CLIMATE_SERVICES:
            return
        context = event.context
        if getattr(context, "id", None) in self._own_ctx or getattr(context, "user_id", None):
            return  # eigener Befehl oder von einer Person in Home Assistant
        targets = (data.get("service_data") or {}).get("entity_id") or []
        if isinstance(targets, str):
            targets = [targets]
        mine = self._controlled() & set(targets)
        if not mine:
            return
        now = dt_util.utcnow().timestamp()
        origin = self._origin(context)
        for entity_id in mine:
            writes = [w for w in self._foreign.get(entity_id, []) if now - w[0] < CONFLICT_WINDOW]
            self._foreign[entity_id] = writes + [(now, origin)]
        self._foreign_ctx[context.id] = origin
        if len(self._foreign_ctx) > 200:
            self._foreign_ctx = dict(list(self._foreign_ctx.items())[-100:])

    def _scan_refs(self, now: float) -> None:
        """Andere Regelungen suchen, die unsere Thermostate in ihren Attributen nennen (alle 10 Minuten)."""
        if now - self._refs_at < 600:
            return
        self._refs_at = now
        ids = self._controlled()
        shown = {e for room in self.rooms.values() for e in room.get("show_entities") or []}
        registry = er.async_get(self.hass)
        refs: dict[str, list[dict[str, str]]] = {}
        for state in self.hass.states.async_all("climate"):
            if state.entity_id in ids or state.entity_id in shown:
                continue
            for found in find_references(dict(state.attributes), ids):
                entry = registry.async_get(state.entity_id)
                refs.setdefault(found, []).append(
                    {"id": state.entity_id, "name": state.name, "platform": getattr(entry, "platform", None) or ""}
                )
        self._refs = refs

    def _conflicts(self, room: dict, now: float) -> list[dict[str, Any]]:
        out = []
        for entity_id in room.get("climates") or []:
            by = [f"{r['name']} ({r['platform']})" if r["platform"] else r["name"] for r in self._refs.get(entity_id, [])]
            writes = [w for w in self._foreign.get(entity_id, []) if now - w[0] < CONFLICT_WINDOW]
            self._foreign[entity_id] = writes
            if len(writes) >= CONFLICT_WRITES:
                for origin in dict.fromkeys(w[1] for w in writes):
                    if origin != "andere Integration" or not by:
                        by.append(origin)
            if by:
                out.append({"id": entity_id, "name": self._name(entity_id), "by": by, "writes": len(writes)})
        return out

    # ------------------------------------------------------------ Wandthermostat und Heizkörper gekoppelt
    def _kind(self, entity_id: str) -> str | None:
        if entity_id not in self._kinds:
            state = self.hass.states.get(entity_id)
            model = state.attributes.get("model") if state is not None else None
            if not model:
                entry = er.async_get(self.hass).async_get(entity_id)
                if entry is not None and entry.device_id:
                    device = dr.async_get(self.hass).async_get(entry.device_id)
                    model = getattr(device, "model", None)
            self._kinds[entity_id] = thermostat_kind(model, entity_id, state.name if state is not None else None)
        return self._kinds[entity_id]

    # ------------------------------------------------------------ Homematic: Direktverknüpfungen
    async def async_refresh_links(self, by: str | None = None) -> dict:
        """Verknüpfungen aus der CCU lesen (alle 6 Std. und auf Wunsch) und auswerten."""
        self._links_next = dt_util.utcnow().timestamp() + 6 * 3600
        if not self.hmlinks.available:
            self._links, self._link_findings = {}, []
            return self.links_status()
        ids = sorted({e for r in self.rooms.values() for e in (r.get("climates") or []) + (r.get("windows") or [])})
        await self.hmlinks.async_refresh(ids)
        self._analyze_links()
        if by:
            self.log.add("settings", "Homematic-Verknüpfungen gelesen",
                         f"{sum(len(i['walls']) for i in self._links.values())} Wandthermostate · {len(self._link_findings)} Hinweise · {by}")
        await self.async_evaluate()
        return self.links_status()

    def _analyze_links(self) -> None:
        old = {f["text"] for f in self._link_findings}
        kinds = lambda e: self._kind(e)  # noqa: E731
        self._links = {}
        for room_id, room in self.rooms.items():
            info = analyze_room(room, kinds, self.hmlinks.addr, self.hmlinks.peers, self.hmlinks.devices)
            if info is not None:
                self._links[room_id] = info
        fal = [(p["address"], p["channel"]) for i in self._links.values() for p in i["fal"]]
        self._link_findings = link_findings(self.rooms, self._links, self._name, self.hmlinks.devices, fal)
        for f in self._link_findings:
            if f["text"] not in old:
                room = self.rooms.get(f.get("room") or "") or {}
                self.log.add("health", "Homematic-Verknüpfung", f["text"], f.get("room"), room.get("name"))

    def links_status(self) -> dict:
        devices = self.hmlinks.devices
        return {"available": self.hmlinks.available, "at": self.hmlinks.at, "error": self.hmlinks.error,
                "rooms": self._links, "findings": self._link_findings,
                "devices": {a: {**d, "kind": peer_kind(d.get("model"))} for a, d in devices.items()
                            if any(a == p["address"] for i in self._links.values() for w in i["walls"] for p in w["peers"])}}

    def _window_ccu(self, room: dict, result: dict, virtual: bool) -> list[str]:
        """Fensterpause, die die CCU schon selbst macht: alle offenen Fenster sind direkt mit dem Thermostat
        verknüpft. Dann sendet Hauswerk den verknüpften Thermostaten keine Fenster-Befehle (spart Funk).
        Rückgabe: Thermostate, denen Hauswerk nichts schickt (leer = Hauswerk macht die Pause selbst)."""
        links = self._links.get(room.get("id") or "")
        if result.get("mode") != "fenster" or virtual or not links or room.get("window_ccu") is False:
            return []
        open_ = [w for w in room.get("windows") or []
                 if (st := self.hass.states.get(w)) is not None and st.state.lower() in WINDOW_OPEN_STATES]
        if not open_ or any(w not in links["windows_ccu"] for w in open_):
            return []
        return self._ccu_covered(links, open_)

    @staticmethod
    def _ccu_covered(links: dict, wins: list[str]) -> list[str]:
        """Thermostate, die die CCU für diese Fenster selbst absenkt: nur die, mit denen ein Fenster direkt verknüpft
        ist (ein verknüpftes Wandthermostat nimmt seine verknüpften Heizkörper mit). Alle anderen senkt Hauswerk."""
        targets = links.get("window_targets") or {}
        walls = {w["entity"] for w in links.get("walls") or []}
        out: set[str] = set()
        for win in wins:
            for e in targets.get(win) or []:
                out.add(e)
                if e in walls:
                    out |= set(links.get("linked_trvs") or [])
        return sorted(out)

    def _ccu_window_entities(self, room: dict, rt: dict, now: float) -> list[str]:
        """Thermostate, die die CCU gerade selbst wegen eines Fensters umstellt – auch schon während der Wartezeit vor
        der Fensterpause und kurz nach dem Schließen (die CCU stellt dann zurück). Hauswerk sendet ihnen solange nichts,
        sonst stellen beide gegeneinander."""
        links = self._links.get(room.get("id") or "")
        if not links or room.get("window_ccu") is False:
            return []
        wins = room.get("windows") or []
        open_ = [w for w in wins if (st := self.hass.states.get(w)) is not None and st.state.lower() in WINDOW_OPEN_STATES]
        recent = now - (rt.get("win_change_at") or 0) < 180
        return self._ccu_covered(links, open_ if open_ else (wins if recent else []))

    def _followers(self, room: dict, rt: dict, now: float) -> set[str]:
        """Heizkörper-Thermostate, die dem Wandthermostat folgen und deshalb nicht selbst gestellt werden.

        Bestätigt wird die Kopplung laufend: weicht der Sollwert länger als 15 Minuten ab, stellt
        Hauswerk das Heizkörper-Thermostat wieder selbst.
        """
        if room.get("pair_mode") == "off":
            return set()
        # Zusatzheizung und „selbst stellen“ gewählte Thermostate folgen nie dem Wandthermostat
        assist = set(room.get("assist_entities") or []) | set(room.get("pair_exclude") or [])
        climates = [c for c in room.get("climates") or [] if c not in assist]
        walls = [c for c in climates if self._kind(c) == "wall"]
        trvs = [c for c in climates if self._kind(c) == "trv"]
        links = self._links.get(room.get("id") or "")
        if links is not None:
            # Verknüpfungen aus der CCU bekannt: nur verknüpfte Heizkörper folgen dem Wandthermostat
            trvs = [t for t in trvs if t in links["linked_trvs"]]
        if not walls or not trvs:
            return set()
        broken = rt.setdefault("pair_broken", {})
        diverge = rt.setdefault("pair_diverge", {})
        wall = next((self.hass.states.get(w) for w in walls if (s := self.hass.states.get(w)) is not None and s.state not in BAD_STATES), None)
        wall_t = _float(wall.attributes.get("temperature")) if wall is not None and wall.state != "off" else None
        out = set()
        for trv in trvs:
            if trv in broken:
                continue
            state = self.hass.states.get(trv)
            trv_t = _float(state.attributes.get("temperature")) if state is not None and state.state not in BAD_STATES and state.state != "off" else None
            if wall_t is not None and trv_t is not None and abs(wall_t - trv_t) > 0.3:
                since = diverge.setdefault(trv, now)
                if now - since >= PAIR_GRACE:
                    broken[trv] = now
                    diverge.pop(trv, None)
                    self.log.add("health", f"{self._name(trv)} folgt dem Wandthermostat nicht",
                                 f"Soll {self._t(trv_t)} statt {self._t(wall_t)} °C seit {int((now - since) // 60)} Min. · Hauswerk stellt es wieder selbst",
                                 room.get("id"), room.get("name"))
                    continue
            else:
                diverge.pop(trv, None)
            out.add(trv)
        if out != rt.get("followers_logged"):
            if out:
                self.log.add("health", "Wandthermostat stellt die Heizkörper",
                             f"{', '.join(self._name(w) for w in walls)} → {', '.join(self._name(f) for f in sorted(out))} · Hauswerk stellt nur das Wandthermostat",
                             room.get("id"), room.get("name"))
            rt["followers_logged"] = out
        return out

    # ------------------------------------------------------------ Mischbetrieb
    def _assist_ids(self, room: dict) -> list[str]:
        """Heizkörper-Thermostate, die als Zusatzheizung eigenständig gestellt werden."""
        climates = room.get("climates") or []
        return [c for c in room.get("assist_entities") or [] if c in climates]

    def _assist(self, room: dict, rt: dict, result: dict, room_temp: float | None) -> None:
        if not self._assist_ids(room):
            rt["assist_on"] = None
            return
        temp = room_temp  # ohne Zusatz-Heizkörper gemessen (siehe _room_values)
        before = rt.get("assist_on")
        on = assist_on(result["mode"], temp, result["target"], float(room.get("assist_diff") or 0.5), bool(before))
        rt["assist_on"], rt["assist_temp"] = on, temp
        if before is not None and before != on:
            why = {"vorheizen": "Vorheizen", "boost": "Boost", "entkalken": "Entkalken"}.get(result["mode"])
            if on and not why:
                why = f"Raum {self._t(temp)} °C, Soll {self._t(result['target'])} °C"
            elif not on:
                why = f"Raum {self._t(temp)} °C – Fußbodenheizung reicht" if result["target"] is not None and result["mode"] not in ("fenster", "sommer", "aus", "warm") else MODES[result["mode"]]
            self.log.add("target", "Heizkörper hilft nach" if on else "Heizkörper aus – Fußbodenheizung allein", why,
                         room.get("id"), room.get("name"))

    def _assist_status(self, room: dict, rt: dict) -> dict[str, Any] | None:
        ids = self._assist_ids(room)
        if not ids:
            return None
        return {"entities": ids, "on": bool(rt.get("assist_on")), "diff": float(room.get("assist_diff") or 0.5),
                "room_temp": rt.get("assist_temp")}

    def _find_batteries(self) -> None:
        """Batterie-Sensoren an den Geräten jedes Raums suchen (Thermostate, Fenster, Sensoren)."""
        registry = er.async_get(self.hass)
        self._batteries = {}
        for room_id, room in self.rooms.items():
            devices = set()
            for key in ("climates", "windows", "temp_sensor", "humidity_sensor", "presence_sensor"):
                value = room.get(key)
                for entity_id in value if isinstance(value, list) else [value] if value else []:
                    entry = registry.async_get(entity_id)
                    if entry is not None and entry.device_id:
                        devices.add(entry.device_id)
            found = []
            for device_id in devices:
                for entry in er.async_entries_for_device(registry, device_id):
                    if entry.domain not in ("sensor", "binary_sensor") or entry.disabled_by is not None:
                        continue
                    dc = getattr(entry, "device_class", None) or getattr(entry, "original_device_class", None)
                    if dc == "battery" or (dc is None and "battery" in entry.entity_id and entry.domain == "sensor"):
                        found.append(entry.entity_id)
            self._batteries[room_id] = sorted(set(found))

    def _battery_low(self, room_id: str) -> list[dict[str, Any]]:
        limit = float(self.haus.settings.get("battery_low") or 0)
        out = []
        for entity_id in self._batteries.get(room_id) or []:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in BAD_STATES:
                continue
            level = battery_level(state.state, state.attributes.get("device_class"), state.attributes.get("unit_of_measurement"))
            if level is not None and level <= limit:
                out.append({"id": entity_id, "name": state.name, "level": level})
        return out

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
        self._links_next = 0.0  # Geräte des Raums können sich geändert haben: Verknüpfungen beim nächsten Takt neu lesen
        if self.hmlinks.peers:
            self._analyze_links()
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
        log_settings(self.log, settings, changed, by, old=self.settings)
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
    @callback
    def push(self) -> None:
        """Status sofort an das Panel schicken (z. B. Gerät fertig), ohne neu zu regeln."""
        status = self.status()
        for cb in list(self._subscribers):
            cb(status)

    def subscribe(self, cb: Callable[[dict], None]) -> Callable[[], None]:
        self._subscribers.add(cb)

        @callback
        def unsub() -> None:
            self._subscribers.discard(cb)

        return unsub

    def status(self) -> dict[str, Any]:
        self._retry_publish()
        out = {}
        for room_id in self.rooms:
            rt = self._rt(room_id)
            out[room_id] = dict(rt.get("result") or {})
            out[room_id]["unconfirmed"] = [{"entity": k, "value": v.get("value"), "current": v.get("current"), "fails": v["fails"],
                                            "next": v.get("next")} for k, v in (rt.get("retry") or {}).items() if v.get("fails", 0) >= 2]
        return {
            **self.haus.status(),
            "rooms": out,
            "hm_links": self.links_status(),
            "vent_plan": self._vent_plan(),
            "outside_mean": None if self._outside_mean is None else round(self._outside_mean, 1),
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
            "boiler": self.boiler(),
            "demand": {**{k: v for k, v in self.demand.items() if k != "since_no_need"},
                       "action": self.settings.get("demand_action") or "lower"} if self.settings.get("demand_entity") else None,
            "cold_rooms": [rid for rid in self.rooms if (self._rt(rid).get("result") or {}).get("cold_radiator")],
            "commands_hour": len([x for x in self._sent_at if dt_util.utcnow().timestamp() - x < 3600]),
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
                    rt["win_change_at"] = now
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
            if entity_id in (rt.get("followers") or set()):
                continue  # folgt dem Wandthermostat – dessen Änderung zählt
            sent = rt["last_sent"].get(entity_id)
            if sent and (abs(sent[0] - new_t) < 0.05 or now - sent[1] < OWN_CHANGE_GRACE):
                continue
            if rt["paused"] or not room.get("enabled", True) or not room.get("allow_manual", True):
                continue
            if new.state == "off":
                continue
            # Herkunft: mit Benutzer = Home-Assistant-Oberfläche/App, ohne = am Gerät gedreht
            foreign = self._foreign_ctx.get(getattr(new.context, "id", None))
            from_ui = getattr(new.context, "user_id", None) is not None or foreign is not None
            if from_ui and room.get("manual_ui") is False:
                continue
            if not from_ui and room.get("manual_device") is False:
                continue
            # Fensterfunktion: Bei offenem Fenster (bzw. kurz nach dem Öffnen oder Schließen) stellt die CCU über die
            # Direktverknüpfung Fensterkontakt → Thermostat den Sollwert selbst um – das ist kein „von Hand“.
            if not from_ui and (self._windows_open_since(room)[0] is not None or now - (rt.get("win_change_at") or 0) < 180):
                if rt.get("win_func_logged") != (entity_id, new_t):
                    rt["win_func_logged"] = (entity_id, new_t)
                    linked = entity_id in self._ccu_window_entities(room, rt, now)
                    self.log.add("window", f"{'Fensterfunktion HmIP' if linked else 'Sollwert bei offenem Fenster'}: {self._t(new_t)} °C",
                                 f"{new.name} – " + ("die CCU stellt bei offenem Fenster selbst um (Direktverknüpfung)" if linked
                                                     else "Änderung während Fenster offen bzw. kurz danach") + ", kein „von Hand“",
                                 room_id, room.get("name"))
                continue
            offset = rt["offset"].get(entity_id, 0.0)
            minutes = (rt.get("result") or {}).get("next_change") or 240
            rt["override"] = {"temp": round(new_t - offset, 1), "until": now + minutes * 60}
            _LOGGER.debug("Manuelle Änderung in %s: %.1f °C", room.get("name"), new_t)
            self.log.add(
                "manual",
                f"Von Hand: {self._t(rt['override']['temp'])} °C",
                f"{f'von {foreign}' if foreign else 'in Home Assistant geändert' if from_ui else 'am Thermostat gedreht'} ({new.name}) · gilt bis {self._hm(rt['override']['until'])}",
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
        if dt_util.utcnow().timestamp() >= self._links_next:
            await self.async_refresh_links()
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
            if state.state.lower() in WINDOW_OPEN_STATES:
                # nach einem Neustart beginnt last_changed neu – gemerkte Öffnungszeit gilt weiter
                known = self.win_open.get(entity_id)
                if known is None or known > ts:
                    self.win_open[entity_id] = ts
                    self._save(30)
                else:
                    ts = known
                opened.append(ts)
            else:
                if self.win_open.pop(entity_id, None) is not None:
                    self._save(30)
                closed.append(ts)
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
            assist = set(room.get("assist_entities") or [])
            # Zusatz-Heizkörper messen am Heizkörper zu warm – nur, wenn es sonst nichts gibt
            climates = [c for c in room.get("climates") or [] if c not in assist] or room.get("climates") or []
            # Wandthermostate messen die Raumluft, Heizkörper-Thermostate am Heizkörper: Wand zählt vor
            climates = [c for c in climates if self._kind(c) == "wall"] or climates
            for entity_id in climates:
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
        factor = self._lead_factor
        if mode != "smart":
            return int(round(self._fixed_lead(room) * factor)), None, None
        max_lead = int(room_setting(room, "preheat_max") or 90)
        # Gelernt wird die Geschwindigkeit bei 5 °C draußen; bei Kälte heizt der Raum langsamer auf.
        rate = (self.heat_rates.get(room_id) or float(room_setting(room, "heat_rate") or 1.0)) / factor
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
                rt["learn"] = {"ts": now, "temp": room_temp, "target": result["target"], "factor": self._lead_factor}
            return
        if abs(result["target"] - run["target"]) > 0.6 or now - run["ts"] > 8 * 3600:
            rt["learn"] = None  # Ziel geändert oder zu lange: Messung verwerfen
            return
        if rt.get("fire"):
            run["fire"] = True  # Kamin an oder Wärme ohne Heizung: diese Messung zählt nicht
        if room_temp >= run["target"] - 0.2:
            # auf 5 °C draußen umrechnen (gemessene Geschwindigkeit × Wetterfaktor)
            hours = (now - run["ts"]) / 3600 / (run.get("factor") or 1.0)
            old = self.heat_rates.get(room_id)
            measured = (room_temp - run["temp"]) / hours if hours > 0 else None
            if run.get("fire") or ((self.rooms.get(room_id) or {}).get("fireplace") and old and measured and measured > 2.5 * old):
                # Kamin-Raum und viel schneller als gelernt: wahrscheinlich half eine andere Wärmequelle mit
                self.log.add("target", "Aufheizmessung verworfen",
                             "Kamin bzw. zusätzliche Wärme während des Aufheizens – zählt nicht für die Heizleistung",
                             room_id, (self.rooms.get(room_id) or {}).get("name"))
                rt["learn"] = None
                return
            rate = learn_rate(old, run["temp"], room_temp, hours)
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
        self.haus.update_radio()
        self._scan_refs(now)
        away = self.haus.away
        vacation = self.haus.vacation
        outside = self.haus.outside_temp()
        self._note_outside(outside)
        out_temp, out_rh = self.haus.outside_air()
        self._lead_factor = weather_lead_factor(out_temp) if self.settings.get("preheat_weather") else 1.0
        # Feiertag laut Sensor „Arbeitstag“: Heizpläne wie am Wochenende
        hs = self.haus.settings
        # Arbeitstag aus dem Kalender der Integration „Arbeitstag“ (zentral unter Hauswerk › Kalender), sonst aus dem Sensor
        workday = self.haus.is_workday(now_local.date())
        plan_min = holiday_week_minute(week_min, workday, int(hs.get("workday_as") or 6))
        holiday = plan_min != week_min
        self._flip("holiday", holiday, "Feiertag – Heizpläne wie am Wochenende", None, "season",
                   f"laut {self.haus.workday_source()}: kein Arbeitstag" if holiday else None)
        party = bool(self.settings.get("party"))

        summer_mode = self.settings.get("summer_mode") or "off"
        if summer_mode == "on":
            self._summer = True
        elif summer_mode == "auto":
            # Nach Tages- oder 3-Tage-Mittel statt nach dem Wert genau jetzt (sonst kippt die Saison an milden Nachmittagen)
            basis = self.settings.get("summer_basis") or "day"
            mean = None if basis == "now" else hourly_mean(self.outside_hours, dt_util.utcnow().timestamp(), 72 if basis == "days3" else 24)
            self._outside_mean = mean
            self._summer = summer_state(
                outside if mean is None else mean,
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
            room_temp, humidity = self._room_values(room)
            self._sample(rt, "temps", room_temp, now)
            self._sample(rt, "hums", humidity, now)
            self._sample(rt, "ahs", round(abs_humidity(room_temp, humidity), 2) if room_temp is not None and humidity is not None else None, now)
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
            # Fenster ohne Kontakt: Raumtemperatur fällt in 5 Minuten stark
            virtual = self._virtual_window(room, rt, now)
            paused = paused or virtual
            if paused != rt["paused"]:
                if paused:
                    rt["pause_at"] = now
                    names = [
                        self._name(w) for w in room.get("windows") or []
                        if (s := self.hass.states.get(w)) is not None and s.state.lower() in WINDOW_OPEN_STATES
                    ]
                    mode_text = "Thermostate " + ("aus" if room_setting(room, "pause_mode") == "off" else "auf Frostschutz")
                    if virtual and not names:
                        why = f"Raumtemperatur fiel um {self._t(rt.get('virtual_drop'))} °C in 5 Min. – Fenster vermutlich offen · {mode_text}"
                    else:
                        why = f"{', '.join(names) or 'Fenster'} offen · {mode_text}"
                    self.log.add("window", "Fensterpause beginnt", why, room_id, room.get("name"))
                else:
                    mins = int((now - rt.get("pause_at", now)) // 60)
                    self.log.add("window", "Fensterpause endet", f"alle Fenster zu · Pause dauerte {mins} Min.", room_id, room.get("name"))
            rt["paused"] = paused

            override = rt.get("override")
            if override and override.get("until") and now >= override["until"]:
                rt["override"] = override = None

            # Nach dem Duschen nachheizen: Luftfeuchte steigt in 15 Minuten stark
            override = self._shower(room_id, room, rt, override, paused, now) or override
            rt["followers"] = self._followers(room, rt, now)
            rt["occupied"] = self._occupancy(room, rt, now)
            schedule_on, schedule_next_on = self._schedule_entity(room, now)
            lead, rate, upcoming = self._preheat(room_id, room, room_temp, plan_min, schedule_next_on)
            result = compute_target(
                room,
                self.settings,
                plan_min,
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
            valve, valve_all = self._valves(room_id)
            run, cold = cold_radiator(valve, room_temp, result["target"], result["mode"], open_since is not None,
                                      rt.get("cold_run"), now, closed_ago=(now - closed_since) if closed_since else None,
                                      floor=room.get("type") == "flaeche" or bool(room.get("assist_entities")))
            rt["cold_run"] = run
            self._assist(room, rt, result, room_temp)
            rt["window_ccu"] = self._window_ccu(room, result, virtual)
            if rt["window_ccu"]:
                rest = [c for c in room.get("climates") or [] if c not in rt["window_ccu"] and c not in rt["followers"]]
                result["cause"] = ("Fenster offen – die CCU senkt über die Direktverknüpfung ab" +
                                   (f", Hauswerk senkt {', '.join(self._name(c) for c in rest)}" if rest else " (Hauswerk sendet nichts)"))
            hm_ids = self._ccu_window_entities(room, rt, now) if open_since is not None else []
            result["window_hmip"] = any(self._kind(e) == "wall" for e in hm_ids)  # Wandthermostat senkt die CCU
            hm_ids = sorted(hm_ids, key=lambda e: self._kind(e) != "wall")  # Wandthermostat zuerst
            result["hmip_target"] = next((t for e in hm_ids if (st := self.hass.states.get(e)) is not None
                                          and (t := _float(st.attributes.get("temperature"))) is not None), None)
            result["window_since"] = dt_util.utc_from_timestamp(open_since).isoformat() if open_since is not None else None
            fire = self._fireplace(room_id, room, rt, result, room_temp, valve_all, now)
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
                cause=(result.get("cause") or "") + (f" bis {self._hm(override['until'])}" if override and override.get("until") else ""),
                plan_today=self._plan_today(room, plan_min) if not room.get("schedule_entity") else None,
                preheat_factor=self._lead_factor,
                holiday=holiday,
                window_virtual=virtual,
                shower=bool(override and override.get("shower")),
                **self._air(room_id, room, rt, room_temp, humidity, out_temp, out_rh, open_since, now),
                battery_low=self._battery_low(room_id),
                followers=sorted(rt["followers"]),
                links=self._links.get(room_id),
                window_ccu=bool(rt.get("window_ccu")),
                pair_broken=sorted(rt.get("pair_broken") or {}),
                conflicts=self._conflicts(room, now),
                duty_blocked=[c for c in room.get("climates") or [] if self._duty_blocked(c)],
                assist=self._assist_status(room, rt),
                valve=valve,
                valve_all=valve_all,
                fireplace=fire,
                cold_radiator={"minutes": int((now - run["since"]) // 60), "valve": valve,
                               "rise": round(room_temp - run["t0"], 1)} if cold else None,
            )
            self._cold_notice(room_id, room, result)
            for c in result["conflicts"]:
                if f"conflict:{c['id']}" not in self._flags:
                    self._flags[f"conflict:{c['id']}"] = True
                    self.log.add("health", f"Zweite Regelung an {c['name']}",
                                 f"{', '.join(c['by'])} stellt dieses Thermostat ebenfalls", room_id, room.get("name"))
            for c in room.get("climates") or []:
                if not any(x["id"] == c for x in result["conflicts"]):
                    self._flags.pop(f"conflict:{c}", None)
            rt["result"] = result
            self._room_notices(room_id, room, result, open_since, now)
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

        try:
            await self._demand(now)
        except Exception:  # noqa: BLE001 - Wärmeerzeuger nicht erreichbar: Räume trotzdem weiter regeln
            _LOGGER.exception("Fehler bei der Wärmeanforderung")
        status = self.status()
        for cb in list(self._subscribers):
            cb(status)
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    # ------------------------------------------------------------ Verläufe, Erkennung, Nachrichten
    @staticmethod
    def _sample(rt: dict, key: str, value: float | None, now: float) -> None:
        """Messwerte der letzten 20 Minuten merken (für Fenster- und Duscherkennung)."""
        samples = rt.setdefault(key, [])
        if value is not None and (not samples or samples[-1][1] != value or now - samples[-1][0] >= 60):
            samples.append((now, value))
        while samples and now - samples[0][0] > 1200:
            samples.pop(0)

    def _virtual_window(self, room: dict, rt: dict, now: float) -> bool:
        if not room.get("window_detect"):
            rt["virtual_until"] = 0
            return False
        if now < rt.get("virtual_until", 0):
            return True
        drop = drop_within(rt.get("temps") or [], now, 300)
        if drop >= float(room.get("window_detect_drop") or 1.0):
            rt["virtual_until"] = now + float(room.get("window_detect_min") or 15) * 60
            rt["virtual_drop"] = drop
            rt["temps"] = []  # nach der Pause neu messen
            return True
        return False

    # ------------------------------------------------------------ Kamin
    def _fire_signal(self, room: dict) -> bool | None:
        """Signal „Kamin in Betrieb“: Schalter/Binärsensor an, Temperaturfühler am Ofen/Rohr ≥ 50 °C (unter 35 °C aus),
        Leistung/Gebläse > 5 W. None = kein Signal gewählt oder gerade kein Wert."""
        entity_id = room.get("fireplace_entity")
        st = self.hass.states.get(entity_id) if entity_id else None
        if st is None or st.state in ("unavailable", "unknown", ""):
            return None
        if st.state in ("on", "off", "open", "closed", "detected", "clear", "true", "false"):
            return st.state in ("on", "open", "detected", "true")
        try:
            value = float(st.state)
        except ValueError:
            return st.state.lower() in ("heating", "burning", "an", "brennt", "heizen")
        unit = st.attributes.get("unit_of_measurement") or ""
        if unit in ("°C", "°F"):
            value = (value - 32) / 1.8 if unit == "°F" else value
            return True if value >= 50 else False if value < 35 else None
        if unit in ("W", "kW"):
            return value > (0.005 if unit == "kW" else 5)
        return value > 0

    def _fireplace(self, room_id: str, room: dict, rt: dict, result: dict, room_temp: float | None,
                   valve_all: float | None, now: float) -> dict | None:
        """Kamin im Raum: in Betrieb (Hand/Signal), wahrscheinlich (wärmer ohne Heizanforderung) oder Nachwirkung.
        Ergebnis steht in rt["fire"] und schließt die Zeit aus Lernen und Heizleistungs-Bewertung aus."""
        if not room.get("fireplace"):
            rt["fire"] = None
            rt.pop("fire_hist", None)
            self.fire_manual.pop(room_id, None)
            return None
        demand = bool(result.get("heating")) or self._is_heating(room, room_temp, result.get("target")) or (valve_all or 0) >= 15
        hist = rt.setdefault("fire_hist", [])
        if room_temp is not None and (not hist or now - hist[-1][0] >= 55):
            hist.append((now, room_temp, demand))
        elif hist and demand:
            hist[-1] = (hist[-1][0], hist[-1][1], True)
        while hist and now - hist[0][0] > 4 * 3600:
            hist.pop(0)
        until = self.fire_manual.get(room_id)
        if until and now >= until:
            self.fire_manual.pop(room_id, None)
            self._save()
            self.log.add("manual", "Kamin aus", "„Kamin in Betrieb“ nach 8 Std. von selbst beendet", room_id, room.get("name"))
            until = None
        signal = self._fire_signal(room)
        rise = extra_heat_rise(hist, now, floor=room.get("type") == "flaeche")
        prev = rt.get("fire")
        phase = fireplace_phase(prev, now, manual=bool(until), signal=signal, rise=rise, temp=room_temp, target=result.get("target"))
        rt["fire"] = phase
        old, new = (prev or {}).get("state"), (phase or {}).get("state")
        if new == "maybe" and old not in ("maybe", "on"):
            self.log.add("target", "Wärmer ohne Heizung",
                         f"+{self._t(phase['rise'])} °C in 30 Min. ohne Heizanforderung · "
                         + ("Kamin laut Signal aus – andere Wärmequelle (Sonne, Kochen …)" if phase.get("cause") == "other"
                            else "vielleicht der Kamin oder Sonne – zählt nicht für die Heizleistung"),
                         room_id, room.get("name"))
        if new == "on" and old != "on" and phase["source"] == "signal":
            self.log.add("target", "Kamin an", f"laut {self._name(room['fireplace_entity'])}", room_id, room.get("name"))
        if old == "on" and new != "on" and (prev or {}).get("source") == "signal":
            self.log.add("target", "Kamin aus", f"laut {self._name(room['fireplace_entity'])}", room_id, room.get("name"))
        if not phase:
            return {"state": None, "signal": signal, "manual": False}
        out = {**phase, "signal": signal, "manual": bool(until),
               "minutes": int((now - phase["since"]) // 60)}
        if until:
            out["until"] = dt_util.utc_from_timestamp(until).isoformat()
        return out

    async def async_set_fireplace(self, room_id: str, on: bool, by: str | None = None) -> None:
        """„Kamin in Betrieb“ von Hand – längstens 8 Stunden."""
        room = self.rooms.get(room_id) or {}
        if on:
            self.fire_manual[room_id] = dt_util.utcnow().timestamp() + 8 * 3600
            self.log.add("manual", "Kamin an", f"von Hand · zählt bis zum Ausschalten (längstens 8 Std.) nicht für die Heizleistung{self._by(by)}", room_id, room.get("name"))
        else:
            self.fire_manual.pop(room_id, None)
            self.log.add("manual", "Kamin aus", f"von Hand{self._by(by)}", room_id, room.get("name"))
        self._save()
        await self.async_evaluate()

    def _hum_rise(self, rt: dict, now: float) -> float:
        """Feuchte-Anstieg in 15 Min. (%-Punkte): aus der absoluten Feuchte, sonst aus der relativen."""
        temps = [v for _ts, v in rt.get("temps") or []]
        x = abs_rise_points(rt.get("ahs") or [], now, 900, temps[-1] if temps else None)
        return x if x is not None else rise_within(rt.get("hums") or [], now, 900)

    def _shower(self, room_id: str, room: dict, rt: dict, override: dict | None, paused: bool, now: float) -> dict | None:
        minutes = int(room.get("shower_boost") or 0)
        if not minutes or paused or not room.get("humidity_sensor") or (override and not override.get("shower")):
            return None
        rise = self._hum_rise(rt, now)
        if rise < float(room.get("shower_rise") or 10) or now - rt.get("shower_at", 0) < 3600:
            return None
        rt["shower_at"] = now
        rt["override"] = {"temp": float(room.get("comfort", 21)), "until": now + minutes * 60, "shower": True}
        self.log.add("manual", f"Nach dem Duschen: {self._t(rt['override']['temp'])} °C für {minutes} Min.",
                     f"Luftfeuchte um {rise:.0f} Prozentpunkte gestiegen", room_id, room.get("name"))
        return rt["override"]

    def _vent_plan(self) -> dict[str, Any] | None:
        """Beste Lüftzeiten der nächsten 24 h für das ganze Haus (Mittel der Räume mit Feuchtesensor)."""
        hours = getattr(self.haus, "hourly", None) or []
        if not hours or self._summer:
            return None
        temps, rhs = [], []
        for rid in self.rooms:
            res = self._rt(rid).get("result") or {}
            if res.get("room_temp") is not None:
                temps.append(res["room_temp"])
            if res.get("humidity") is not None:
                rhs.append(res["humidity"])
        t_in = sum(temps) / len(temps) if temps else 21.0
        rh_in = sum(rhs) / len(rhs) if rhs else 55.0
        now = dt_util.utcnow().timestamp()
        times = vent_plan(hours, now, t_in, rh_in)
        return {"times": [{**x, "at": dt_util.utc_from_timestamp(x["ts"]).isoformat()} for x in times], "rh_in": round(rh_in)}

    def _night_allowed(self, room: dict) -> bool:
        """Darf das Fenster nachts offen bleiben (bei offenem Fenster schlafen)? Automatisch im Schlafzimmer."""
        if room.get("vent_night") is not None:
            return bool(room["vent_night"])
        return room.get("use") == "schlafen" or "schlaf" in str(room.get("name") or "").lower()

    def _night_window(self) -> tuple[int, int]:
        return parse_hm(self.settings.get("vent_night_from") or "21:00"), parse_hm(self.settings.get("vent_night_to") or "07:30")

    def _in_night(self, local) -> bool:
        a, b = self._night_window()
        m = local.hour * 60 + local.minute
        return (a <= m < b) if a < b else (m >= a or m < b)

    def _night_end(self, local) -> datetime:
        """Ende der laufenden Nacht (für „offen bis …“)."""
        _a, b = self._night_window()
        end = local.replace(hour=b // 60, minute=b % 60, second=0, microsecond=0)
        return end if end > local else end + timedelta(days=1)

    def _air(self, room_id: str, room: dict, rt: dict, room_temp: float | None, humidity: float | None,
             out_temp: float | None, out_rh: float | None, open_since: float | None, now: float) -> dict[str, Any]:
        """Lüften: Empfehlung mit Dauer und Anlass, Lüft-Timer mit Ende, Schimmel-Ampel, Dauerkippen, Sommer-Kühlen, Bilanz."""
        name = room.get("name") or room_id
        base = float(self.settings.get("vent_rh") or 0)
        limit = vent_limit(room, base) if base else 0.0
        # Lüftdauer: gelernt aus den letzten Lüftungen des Raums, sonst Richtwert nach Außentemperatur
        minutes, learned = vent_learned_minutes(self.vent_tau.get(room_id) or [], room_temp, humidity, out_temp, out_rh,
                                                limit or 65, vent_minutes(out_temp))
        helps = vent_helps(room_temp, humidity, out_temp, out_rh)
        wait = None
        mold = mold_risk(room_temp, humidity, out_temp) if humidity is not None else None
        co2 = None
        if room.get("co2_sensor"):
            st = self.hass.states.get(room["co2_sensor"])
            try:
                co2 = round(float(st.state)) if st is not None else None
            except (TypeError, ValueError):
                co2 = None
        local = dt_util.now()
        cool_on = bool(self.settings.get("vent_cool", True)) and self._summer and room_temp is not None and out_temp is not None
        advice = ventilate_advice(room_temp, humidity, out_temp, out_rh, limit) if limit else None
        reasons: list[str] = []
        kind = None
        if open_since is None:
            # Anlass: feucht, Schimmelgefahr, Feuchte steigt schnell (Duschen, Kochen), CO₂, morgens, Sommer kühlen
            if advice:
                reasons.append(f"Luftfeuchte {advice['rh']} %")
                kind = "humid"
            if mold and mold["level"] == "bad" and not advice and out_temp is not None and out_rh is not None and room_temp is not None \
                    and humidity is not None and ventilate_advice(room_temp, humidity, out_temp, out_rh, 1.0):
                reasons.append(f"Schimmelgefahr an Außenwänden ({mold['wall_rh']} %)")
                kind = kind or "mold"
            rise = self._hum_rise(rt, now)
            if rise >= float(room.get("shower_rise") or 10):
                rt["rise_at"] = now
            if now - rt.get("rise_at", 0) < 1800 and humidity is not None:
                if helps is False:
                    wait = "rise"
                else:
                    reasons.append("Feuchte steigt schnell (Duschen/Kochen)")
                    kind = kind or "rise"
            # feucht, aber draußen ist die Luft nicht trockener: Lüften trocknet nicht – später, wenn es draußen trockener ist
            if limit and humidity is not None and humidity >= limit and helps is False:
                wait = wait or "humid"
            co2_max = float(self.settings.get("vent_co2") or 0)
            if co2 is not None and co2_max and co2 >= co2_max:
                reasons.append(f"CO₂ {co2} ppm")
                kind = kind or "co2"
            morning = self.settings.get("vent_morning")
            sleep_room = room.get("vent_morning") if room.get("vent_morning") is not None else (
                (room.get("use") in ("schlafen", "kind")) or any(w in str(room.get("name") or "").lower() for w in ("schlaf", "kinder")))
            if morning and sleep_room and not self._summer:
                start = parse_hm(morning)
                now_min = local.hour * 60 + local.minute
                today0 = dt_util.start_of_local_day().timestamp()
                done_today = morning_vent_done(self.vent_log.get(room_id) or [], today0, start, self._night_window()[0],
                                               open_since is not None)
                if start <= now_min < start + 90 and not done_today:
                    reasons.append("morgens lüften")
                    kind = kind or "morning"
            if cool_on and room_temp >= 23 and out_temp <= room_temp - 2:
                reasons.append(f"kühlen – draußen {self._t(out_temp)} °C")
                kind = kind or "cool"
        if wait and open_since is None and not self._summer:
            dry = next_dry_hour(getattr(self.haus, "hourly", None) or [], now, room_temp, humidity) if room_temp is not None and humidity is not None else None
            wait = {"why": wait, "text": "Draußen ist die Luft feuchter – Lüften trocknet gerade nicht",
                    "dry_at": dt_util.utc_from_timestamp(dry["ts"]).isoformat() if dry else None}
        else:
            wait = None
        need = bool(reasons)
        key = f"vent:{room_id}"
        if need and kind != "cool":
            self.haus.notify(key, "vent", "Lüften empfohlen", f"{name}: {reasons[0]} – {minutes} Min. stoßlüften", room_id, name)
        else:
            self.haus.clear(key)
        # Lüft-Timer: Fenster offen
        session = rt.get("vs")
        info: dict[str, Any] = {}
        done_key = f"ventdone:{room_id}"
        if open_since is not None:
            if not session or session.get("start") != open_since:
                cooling = cool_on and room_temp is not None and out_temp is not None and out_temp < room_temp
                session = rt["vs"] = {"start": open_since, "rh0": humidity, "t0": room_temp, "target": minutes,
                                      "cool": cooling, "done": None, "to": out_temp, "rho": out_rh, "learned": learned}
                self._save(30)
            open_min = (now - session["start"]) / 60
            in_night = self._night_allowed(room) and self._in_night(local)
            if in_night and not session.get("night"):
                # Schlafzimmer: Fenster bleibt nachts offen – gewollt, keine Erinnerung bis zum Morgen
                session["night"] = True
                self._save(30)
                self.haus.clear(done_key)
                self.log.add("window", "Nachts gelüftet – Fenster darf offen bleiben",
                             f"bis {self._night_end(local).strftime('%H:%M')}, keine Erinnerung", room_id, name)
            if session.get("night") and not in_night and not session.get("night_end"):
                # Nacht vorbei, Fenster noch offen: einmal erinnern
                session["night_end"] = now
                self._save(30)
                self.log.add("window", "Nacht vorbei – Fenster noch offen", "Erinnerung „Fenster schließen“", room_id, name)
                self.haus.notify(done_key, "vent_done", "Fenster schließen", f"{name}: Nacht vorbei – Fenster noch offen", room_id, name,
                                 actions=[{"title": "10 Min. später", "do": "snooze", "minutes": 10}, {"title": "Gesehen", "do": "ack"}])
            if session.get("night"):
                pass
            elif not session["done"]:
                if session["cool"]:
                    why = "draußen wärmer als drinnen" if out_temp is not None and room_temp is not None and out_temp >= room_temp else None
                else:
                    why = vent_done(open_min, session["target"], session["rh0"], humidity, session["t0"], room_temp, limit or 65,
                                    out_temp, out_rh)
                if why:
                    session["done"] = why
                    self._save(30)
                    self.log.add("window", "Genug gelüftet – Fenster schließen", why, room_id, name)
                    # je Raum und Tag höchstens zweimal senden, danach nur Hinweis in der Glocke
                    day = dt_util.as_local(dt_util.utcnow()).date().isoformat()
                    cnt = self._ventdone_sent.get(room_id)
                    n = cnt[1] if cnt and cnt[0] == day else 0
                    self.haus.notify(done_key, "vent_done", "Fenster schließen", f"{name}: genug gelüftet ({why})", room_id, name,
                                     quiet_why=f"heute schon {n}× gesendet" if n >= 2 else None,
                                     actions=[{"title": "10 Min. später", "do": "snooze", "minutes": 10}, {"title": "Gesehen", "do": "ack"}])
                    if n < 2:
                        self._ventdone_sent[room_id] = (day, n + 1)
            long_min = float(self.settings.get("vent_long_min") or 30)
            info["open"] = {"since": dt_util.utc_from_timestamp(session["start"]).isoformat(), "minutes": round(open_min, 1),
                            "target": session["target"], "done": session["done"], "cool": session["cool"],
                            "learned": bool(session.get("learned")), "rh0": session.get("rh0"), "t0": session.get("t0"),
                            "night": bool(session.get("night")) and in_night,
                            "night_until": self._night_end(local).isoformat() if session.get("night") and in_night else None}
            # „Kippen kostet Wärme“: nicht in der gewollten Nacht – danach ab Ende der Nacht gezählt
            long_open = (now - session["night_end"]) / 60 if session.get("night_end") else open_min
            if not self._summer and long_open >= long_min and not (session.get("night") and in_night):
                info["long"] = {"minutes": int(long_open), "kwh": window_loss_kwh(long_open, room_temp, out_temp)}
        elif session:
            # Fenster zu: Lüftung in die Bilanz
            open_min = (now - session["start"]) / 60
            if open_min >= 1:
                log = self.vent_log.setdefault(room_id, [])
                kwh = window_loss_kwh(open_min, session["t0"], out_temp)
                log.append({"at": round(session["start"]), "min": round(open_min, 1), "rh0": session["rh0"], "rh1": humidity,
                            "t0": session["t0"], "t1": room_temp, "kwh": kwh, **({"night": True} if session.get("night") else {})})
                # Luftwechsel lernen (nur echte Stoßlüftungen bis 45 Min.)
                tau = vent_tau(open_min, session["t0"], session["rh0"], room_temp, humidity,
                               session.get("to", out_temp), session.get("rho", out_rh)) if open_min <= 45 and not session.get("night") else None
                if tau is not None:
                    self.vent_tau[room_id] = ((self.vent_tau.get(room_id) or []) + [tau])[-10:]
                    self.log.add("window", "Lüften gelernt", f"Luftwechsel τ = {tau:.0f} Min.".replace(".", ","), room_id, name)
                cutoff = now - 14 * 86400
                self.vent_log[room_id] = [v for v in log if v["at"] >= cutoff][-200:]
                self._save(30)
            rt["vs"] = None
            self._save(30)
            self.haus.clear(done_key)
        week_all = [v for v in self.vent_log.get(room_id) or [] if v["at"] >= now - 7 * 86400]
        # Nächte bei offenem Fenster zählen extra – sie verfälschen sonst Dauer, Wärme und Feuchte-Rückgang
        week = [v for v in week_all if not v.get("night")]
        drops = [v["rh0"] - v["rh1"] for v in week if v.get("rh0") is not None and v.get("rh1") is not None]
        last = (self.vent_log.get(room_id) or [None])[-1]
        # Morgen-Feuchte (5–9 Uhr, höchster Wert je Tag) für die Lüft-Bilanz; 10 Tage
        if humidity is not None and 5 <= local.hour < 9:
            days = self.rh_morning.setdefault(room_id, {})
            key = local.date().isoformat()
            if humidity > days.get(key, -1):
                days[key] = round(humidity, 1)
                for old in sorted(days)[:-10]:
                    days.pop(old, None)
        balance = vent_balance(last["at"] if last else None, self.rh_morning.get(room_id) or {}, limit, mold, now,
                               local.date().isoformat()) if limit and humidity is not None and room.get("windows") else None
        air = {
            "limit": limit, "minutes": minutes, "learned": learned, "tau": (sorted(self.vent_tau.get(room_id) or [])[len(self.vent_tau.get(room_id) or []) // 2]
                                                                            if len(self.vent_tau.get(room_id) or []) >= 3 else None),
            "helps": helps, "wait": wait,
            "mold": mold, "co2": co2, "reasons": reasons, "kind": kind,
            "dew_point": advice["dew_point"] if advice else None, **info,
            "last": {"at": dt_util.utc_from_timestamp(last["at"]).isoformat(), "min": last["min"],
                     "rh0": last.get("rh0"), "rh1": last.get("rh1")} if last else None,
            "week": {"count": len(week), "minutes": round(sum(v["min"] for v in week)), "kwh": round(sum(v.get("kwh") or 0 for v in week), 1),
                     "rh_drop": round(sum(drops) / len(drops)) if drops else None, "nights": len(week_all) - len(week),
                     "days": self._vent_days(week_all, local)},
            "night_ok": self._night_allowed(room),
            "balance": balance,
            "abs": {"in": round(abs_humidity(room_temp, humidity), 1) if room_temp is not None and humidity is not None else None,
                    "out": round(abs_humidity(out_temp, out_rh), 1) if out_temp is not None and out_rh is not None else None},
        }
        vent = None
        if need:
            vent = {**(advice or {}), "rh": round(humidity) if humidity is not None else None, "minutes": minutes,
                    "reasons": reasons, "kind": kind}
        return {"vent": vent, "air": air}

    @staticmethod
    def _vent_days(log: list[dict], local) -> list[dict]:
        """Lüften je Tag der letzten 7 Tage (älteste zuerst): wie oft, wie lange, Nacht bei offenem Fenster."""
        today = local.date()
        out = []
        for back in range(6, -1, -1):
            d = today - timedelta(days=back)
            vs = [v for v in log if dt_util.as_local(dt_util.utc_from_timestamp(v["at"])).date() == d]
            day = [v for v in vs if not v.get("night")]
            out.append({"d": d.isoformat(), "count": len(day), "min": round(sum(v["min"] for v in day)), "night": len(vs) > len(day)})
        return out

    def _room_notices(self, room_id: str, room: dict, result: dict, open_since: float | None, now: float) -> None:
        """Nachrichten aufs Handy: Fenster lange offen, Thermostat nicht erreichbar, Batterie schwach."""
        name = room.get("name") or room_id
        hs = self.haus.settings
        key = f"window:{room_id}"
        limit = float(hs.get("notify_window_min") or 30)
        vs = self._rt(room_id).get("vs") or {}
        since = vs.get("night_end") or open_since if vs.get("night") else open_since
        if vs.get("night") and not vs.get("night_end"):
            since = None  # nachts gewollt offen (Schlafzimmer)
        if open_since is not None and since is not None and now - since >= limit * 60:
            self.haus.notify(key, "window", "Fenster lange offen",
                             f"{name}: seit {int((now - open_since) // 60)} Min. offen", room_id, name,
                             actions=[{"title": "In 30 Min.", "do": "snooze", "minutes": 30}, {"title": "Gesehen", "do": "ack"}])
        else:
            self.haus.clear(key)
        limit = float(hs.get("notify_offline_min") or 15) * 60
        for entity_id in room.get("climates") or []:
            state = self.hass.states.get(entity_id)
            key = f"offline:{entity_id}"
            if state is not None and state.state in BAD_STATES and now - state.last_changed.timestamp() >= limit:
                self.haus.notify(key, "offline", "Thermostat nicht erreichbar",
                                 f"{state.name} ({name}) seit {int((now - state.last_changed.timestamp()) // 60)} Min.", room_id, name)
            else:
                self.haus.clear(key)
        low = {b["id"]: b for b in result.get("battery_low") or []}
        for entity_id in self._batteries.get(room_id) or []:
            key = f"battery:{entity_id}"
            if entity_id in low:
                level = low[entity_id]["level"]
                text = "schwach" if level == 0 else f"{level:.0f} %"
                self.haus.notify(key, "battery", "Batterie schwach", f"{low[entity_id]['name']} ({name}): {text}", room_id, name,
                                 actions=[{"title": "Gesehen", "do": "ack"}])
            else:
                state = self.hass.states.get(entity_id)
                lvl = battery_level(state.state, state.attributes.get("device_class"), state.attributes.get("unit_of_measurement")) if state else None
                if lvl is not None and lvl > float(hs.get("battery_low") or 0) + 5:
                    self.haus.clear(key)

    async def _apply(self, room: dict, rt: dict, result: dict, room_temp: float | None, now: float) -> None:
        if result["target"] is None:  # Automatik aus
            for entity_id in room.get("climates") or []:
                if entity_id in self.turned_off:
                    await self._restore_mode(entity_id, room)
            return
        followers = rt.get("followers") or set()
        ccu = set(rt.get("window_ccu") or []) | set(self._ccu_window_entities(room, rt, now))
        for entity_id in room.get("climates") or []:
            if self._duty_blocked(entity_id):
                continue  # Gerät darf gerade nicht funken
            if entity_id in ccu:
                continue  # Fensterpause macht die CCU über die Direktverknüpfung
            if entity_id in followers:
                if entity_id in self.turned_off and not result["hvac_off"]:
                    await self._restore_mode(entity_id, room)  # von früher (vor der Kopplung) noch aus
                continue  # folgt dem Wandthermostat
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
                    await self._call(
                        "climate", "set_hvac_mode", {"entity_id": entity_id, "hvac_mode": "off"}
                    )
                    self.log.add("command", f"{self._name(entity_id)} → aus", MODES[result["mode"]], room.get("id"), room.get("name"))
                continue

            if entity_id in self.turned_off:
                await self._restore_mode(entity_id, room)
            elif state.state == "off":
                continue  # vom Nutzer ausgeschaltet: respektieren

            if entity_id in self._assist_ids(room):
                await self._set_assist(room, rt, result, now, entity_id)
                continue
            await self._calibrate(room, rt, room_temp, now, entity_id)
            await self._set_temperature(room, rt, result, room_temp, now, entity_id)
            await self._set_valve(room, rt, result, room_temp, now, entity_id)

    async def _set_assist(self, room: dict, rt: dict, result: dict, now: float, entity_id: str) -> None:
        """Heizkörper im Mischbetrieb: mitheizen (Raum-Soll, auf den Raumsensor ausgeglichen) oder zu (Frostschutz)."""
        if rt.get("assist_on"):
            temp = rt.get("assist_temp")
            state = self.hass.states.get(entity_id)
            target = result["target"]
            if result["mode"] not in ("boost", "entkalken") and state is not None and temp is not None:
                # Das Thermostat misst am Heizkörper wärmer als der Raum: um den Unterschied höher stellen
                target = compensated(target, _float(state.attributes.get("current_temperature")), temp)
            res = dict(result, target=round(min(MAX_TEMP, max(target, result["target"])), 1))
            label = "Zusatzheizung an"
        else:
            res = dict(result, target=float(self.settings.get("frost_temp") or 7))
            label = "Zusatzheizung aus – Fußbodenheizung allein"
        await self._set_temperature(room, rt, res, None, now, entity_id, tuned=False, label=label,
                                    send_key=f"assist:{bool(rt.get('assist_on'))}")

    async def _calibrate(self, room: dict, rt: dict, room_temp: float | None, now: float, entity_id: str) -> None:
        """Offset des Thermostats so setzen, dass es die Temperatur des Raumsensors misst."""
        if not room.get("calibration") or not room.get("temp_sensor") or self.haus.radio_busy:
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
                await self._call(
                    "number", "set_value", {"entity_id": number_id, "value": new}
                )
                self.log.add("command", f"{self._name(number_id)} → Offset {self._t(new)} °C",
                             f"Raumsensor {self._t(room_temp)} °C", room.get("id"), room.get("name"))
            return

    async def _set_valve(
        self, room: dict, rt: dict, result: dict, room_temp: float | None, now: float, entity_id: str
    ) -> None:
        """Ventilöffnung direkt vorgeben (für Thermostate mit Ventil-Entität)."""
        if not room.get("valve_control") or (self.haus.radio_busy and result["mode"] != "entkalken"):
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
            await self._call(
                "number", "set_value", {"entity_id": number_id, "value": value}
            )
            self.log.add("command", f"{self._name(number_id)} → Ventil {value:.0f} %",
                         MODES[result["mode"]], room.get("id"), room.get("name"))

    async def _restore_mode(self, entity_id: str, room: dict | None = None) -> None:
        previous = self.turned_off.pop(entity_id, None) or "heat"
        self._save()
        await self._call(
            "climate", "set_hvac_mode", {"entity_id": entity_id, "hvac_mode": previous}
        )
        room = room or {}
        self.log.add("command", f"{self._name(entity_id)} → wieder {previous}", "vorheriger Modus nach der Pause", room.get("id"), room.get("name"))

    async def _set_temperature(
        self, room: dict, rt: dict, result: dict, room_temp: float | None, now: float, entity_id: str,
        tuned: bool = True, label: str | None = None, send_key: str | None = None,
    ) -> None:
        state = self.hass.states.get(entity_id)
        if state is None:
            return
        attrs = state.attributes
        target = result["target"]
        tunable = tuned and result["mode"] not in NO_TUNING_MODES and target > MIN_TEMP
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
        retry = rt.setdefault("retry", {})
        last = rt["last_sent"].get(entity_id)
        if current is not None and abs(current - value) < hysteresis:
            # erst nach der Bestätigungszeit gilt der Wert als übernommen (Homematic zeigt ihn vorher schon „optimistisch“)
            if (not last or now - last[1] >= RETRY_CONFIRM) and retry.pop(entity_id, None) is not None:
                self._retry_publish()
                self.log.add("health", f"{self._name(entity_id)} übernimmt den Sollwert wieder", f"{self._t(value)} °C bestätigt",
                             room.get("id"), room.get("name"))
            return
        if last and abs(last[0] - value) < 0.05 and now - last[1] < RETRY_CONFIRM:
            return  # eben gesendet – erst die Bestätigung abwarten statt sofort nachzulegen
        # Nicht im Kreis senden: bleibt ein gesendeter Wert nicht stehen (Gerät antwortet nicht, CCU-Verknüpfung stellt zurück),
        # höchstens zweimal senden, dann nach 15 Min. und danach stündlich – jeder Fehlversuch kostet Funkzeit.
        if last and now - last[1] >= RETRY_CONFIRM:
            r = retry.get(entity_id) or {"fails": 0}
            if abs(last[0] - value) < 0.05 and r.get("counted") != last[1]:
                r.update(fails=r["fails"] + 1, counted=last[1], value=value, current=current, room=room.get("name"))
                retry[entity_id] = r
                if r["fails"] == 2:
                    self.log.add("health", f"{self._name(entity_id)} übernimmt den Sollwert nicht",
                                 f"{self._t(value)} °C zweimal gesendet, bleibt bei {self._t(current)} °C – Gerät nicht erreichbar oder "
                                 "eine Verknüpfung in der CCU stellt zurück · Hauswerk versucht es nur noch alle 15 Min. bzw. stündlich",
                                 room.get("id"), room.get("name"))
            if r.get("fails", 0) >= 2:
                wait = retry_wait(r["fails"])
                r["next"] = dt_util.utc_from_timestamp(last[1] + wait).isoformat()
                retry[entity_id] = r
                self._retry_publish()
                if now - last[1] < wait:
                    return
        # Funk ausgelastet: nur Wechsel der Betriebsart oder größere Änderungen, höchstens alle 15 Minuten
        last_mode = rt.setdefault("sent_mode", {}).get(entity_id)
        mode_key = send_key or result["mode"]
        if not radio_should_send(self.haus.radio_busy, current, value, now - last[1] if last else None,
                                 important=last_mode != mode_key):
            return
        rt["sent_mode"][entity_id] = mode_key
        rt["last_sent"][entity_id] = (value, now)
        await self._call(
            "climate", "set_temperature", {"entity_id": entity_id, "temperature": value}
        )
        extra = f" · gesendet {self._t(value)} °C (Ausgleich)" if abs(value - result["target"]) >= 0.05 else ""
        self.log.add("command", f"{self._name(entity_id)} → {self._t(value)} °C",
                     label or f"Ziel {self._t(result['target'])} °C · {MODES[result['mode']]}{extra}", room.get("id"), room.get("name"))

    def _retry_publish(self) -> None:
        """Unbestätigte Sollwerte aller Räume an Hauswerk melden (Funk-Auslastung, Glocke)."""
        out = {}
        for rid in self.rooms:
            rt = self._rt(rid)
            for ent, r in list((rt.get("retry") or {}).items()):
                if ent not in (self.rooms[rid].get("climates") or []) or ent in (rt.get("followers") or set()):
                    rt["retry"].pop(ent, None)  # wird nicht mehr von Hauswerk gestellt
                    continue
                if r.get("fails", 0) >= 2:
                    out[ent] = {"room_id": rid, "room": r.get("room"), "value": r.get("value"), "current": r.get("current"),
                                "fails": r["fails"], "next": r.get("next")}
        self.haus.radio_retry = out

    # ------------------------------------------------------------ Kalte Heizkörper
    def _cold_notice(self, room_id: str, room: dict, result: dict) -> None:
        cold = result.get("cold_radiator")
        key = f"cold:{room_id}"
        if cold:
            name = room.get("name") or room_id
            text = (f"{name}: Ventil {cold['valve']:.0f} % offen seit {cold['minutes']} Min., Raum nur +{self._t(cold['rise'])} °C – "
                    "Luft im Heizkörper, hängender Ventilstift oder Heizung ohne Wärme?")
            if key not in self._flags:
                self._flags[key] = True
                self.log.add("health", "Heizkörper bleibt kalt", text, room_id, name)
            self.haus.notify(key, "cold", "Heizkörper bleibt kalt", text, room_id, name)
        else:
            self._flags.pop(key, None)
            self.haus.clear(key)

    # ------------------------------------------------------------ Wärmeanforderung
    async def _demand(self, now: float) -> None:
        """Wärmeerzeuger (z. B. Zone der Vaillant-Anlage) absenken, wenn kein Raum Wärme braucht."""
        entity_id = self.settings.get("demand_entity")
        d = self.demand
        if not entity_id:
            if d.get("state") in ("low", "raise") and d.get("entity"):
                await self._demand_restore(d["entity"], "Wärmeanforderung ausgeschaltet")
            self.demand = {}
            self._no_need_since = None
            return
        state = self.hass.states.get(entity_id)
        if state is None or state.state in BAD_STATES:
            d["error"] = "nicht erreichbar"
            return
        d.pop("error", None)
        if d.get("entity") not in (None, entity_id) and d.get("state") in ("low", "raise"):
            await self._demand_restore(d["entity"], "anderer Wärmeerzeuger gewählt")
            d.clear()
        d["entity"] = entity_id
        threshold = float(self.settings.get("demand_valve") or 15)
        need_rooms: list[str] = []
        preheat = False
        for room_id, room in self.rooms.items():
            res = self._rt(room_id).get("result") or {}
            if not room.get("enabled", True) or res.get("target") is None or res.get("hvac_off"):
                continue
            mode = res.get("mode")
            valve = res.get("valve_all")
            if mode in ("vorheizen", "boost"):
                preheat = preheat or mode == "vorheizen"
                need_rooms.append(room.get("name") or room_id)
            elif valve is not None:
                if valve >= threshold:
                    need_rooms.append(room.get("name") or room_id)
            elif res.get("room_temp") is not None and res["room_temp"] < res["target"] - 0.3:
                need_rooms.append(room.get("name") or room_id)  # ohne Ventilwert: nach Temperatur
        need = bool(need_rooms)
        if need:
            self._no_need_since = None
        elif self._no_need_since is None:
            self._no_need_since = now
        before = d.get("state") or "normal"
        new = demand_state(need, before, self._no_need_since, now, float(self.settings.get("demand_hold") or 20),
                           preheat, float(self.settings.get("demand_preheat") or 0))
        d.update(need=need_rooms, since_no_need=self._no_need_since)
        attrs = state.attributes
        current_t = _float(attrs.get("temperature"))
        action = self.settings.get("demand_action") or "lower"
        if new == before:
            # Abgesenkt, aber der Wärmeerzeuger steht wieder anders (z. B. Schnellwahl abgelaufen): höchstens alle 30 Min. erneut senden
            if new in ("low", "raise") and now - float(d.get("sent_at") or 0) >= 1800:
                wanted = d.get("sent_temp")
                if (action == "off" and new == "low" and state.state != "off") or (
                        wanted is not None and current_t is not None and abs(current_t - wanted) >= 0.25):
                    await self._demand_apply(entity_id, new, action, "erneut gesendet", now)
            self._save()
            return
        if before == "normal":
            # Werte des Wärmeerzeugers merken, um sie später wiederherzustellen
            d["orig_temp"] = current_t
            d["orig_mode"] = state.state if state.state != "off" else (d.get("orig_mode") or "auto")
        why = f"braucht Wärme: {', '.join(need_rooms[:4])}" if need else f"seit {int((now - (self._no_need_since or now)) // 60)} Min. kein Raum über {threshold:.0f} % Ventil"
        if new == "normal":
            await self._demand_restore(entity_id, why)
        else:
            await self._demand_apply(entity_id, new, action, why, now)
        d["state"] = new
        d["changed"] = now
        self._save()

    async def _demand_apply(self, entity_id: str, new: str, action: str, why: str, now: float) -> None:
        d = self.demand
        name = self._name(entity_id)
        if new == "low" and action == "off":
            await self._call("climate", "set_hvac_mode", {"entity_id": entity_id, "hvac_mode": "off"})
            d["sent_temp"] = None
            self.log.add("target", f"Wärmeanforderung: keine – {name} aus", why)
        else:
            if new == "low":
                value = float(self.settings.get("demand_low") or 17)
                title = f"Wärmeanforderung: keine – {name} auf {self._t(value)} °C"
            else:
                base = d.get("orig_temp") or _float(self.hass.states.get(entity_id).attributes.get("temperature")) or 20.0
                value = base + float(self.settings.get("demand_preheat") or 0)
                title = f"Wärmeanforderung: Vorheizen – {name} auf {self._t(value)} °C"
            state = self.hass.states.get(entity_id)
            if state is not None and state.state == "off":
                await self._call("climate", "set_hvac_mode", {"entity_id": entity_id, "hvac_mode": d.get("orig_mode") or "auto"})
            await self._call("climate", "set_temperature", {"entity_id": entity_id, "temperature": round(value, 1)})
            d["sent_temp"] = round(value, 1)
            self.log.add("target", title, why)
        d["sent_at"] = now

    async def _demand_restore(self, entity_id: str, why: str) -> None:
        """Wärmeerzeuger auf die gemerkten Werte zurück."""
        d = self.demand
        state = self.hass.states.get(entity_id)
        if state is None or state.state in BAD_STATES:
            return
        if state.state == "off" and d.get("orig_mode"):
            await self._call("climate", "set_hvac_mode", {"entity_id": entity_id, "hvac_mode": d["orig_mode"]})
        orig = d.get("orig_temp")
        current = _float(state.attributes.get("temperature"))
        if orig is not None and (current is None or abs(current - orig) >= 0.05):
            await self._call("climate", "set_temperature", {"entity_id": entity_id, "temperature": orig})
        d["sent_temp"] = None
        d["sent_at"] = dt_util.utcnow().timestamp()
        self.log.add("target", f"Wärmeanforderung: {self._name(entity_id)} wieder normal"
                     + (f" ({self._t(orig)} °C)" if orig is not None else ""), why)

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
            temp, target, mode = result.get("room_temp"), result.get("target"), result.get("mode")
            if self._rt(room_id).get("fire"):
                # Kamin bzw. zusätzliche Wärme: nicht in die Bewertung der Heizleistung (Komfort, überheizt, Ventil)
                bucket["fire"] = bucket.get("fire", 0) + 1
                temp = None
            # Für die Analyse der Heizleistung: Komfort erreicht? Überheizt? Ventil ganz offen? Außentemperatur?
            # Nach dem Lüften erst wieder bewerten, wenn der Raum Zeit zum Aufheizen hatte (Heizkörper 30 Min., Fußbodenheizung 3 Std.)
            recover = (3 * 3600 if (self.rooms[room_id].get("type") == "flaeche") else 1800)
            after_vent = dt_util.utcnow().timestamp() - (self._rt(room_id).get("win_change_at") or 0) < recover
            if temp is not None and target is not None and mode in COMFORT_MODES and not after_vent:
                bucket["cn"] = bucket.get("cn", 0) + 1
                bucket["cdev"] = round(bucket.get("cdev", 0.0) + (temp - target), 2)
                if temp < target - 0.5:
                    bucket["under"] = bucket.get("under", 0) + 1
                # zu warm nur in der Komfortzeit zählen – nach dem Absenken auf Eco ist der Raum natürlich noch wärmer
                bucket["co"] = bucket.get("co", 0) + (1 if temp > target + 1.0 else 0)
                room = self.rooms[room_id]
                if room.get("type") == "flaeche":
                    fv = self._floor_valve(room_id)
                    if fv is not None:
                        bucket["fv"] = round(bucket.get("fv", 0.0) + fv, 1)
                        bucket["fvn"] = bucket.get("fvn", 0) + 1
                    if room.get("assist_entities"):
                        bucket["as"] = bucket.get("as", 0) + (1 if self._rt(room_id).get("assist_on") else 0)
            if temp is not None and target is not None and mode not in ("fenster", "aus", "sommer", "entkalken"):
                bucket["mn"] = bucket.get("mn", 0) + 1
                if temp > target + 1.0:
                    bucket["over"] = bucket.get("over", 0) + 1
            self._record_punctual(room_id, bucket, mode, temp, target, after_vent)
            self._record_savings(room_id, bucket, result, temp)
            if temp is not None and (result.get("valve_all") or 0) >= 90:
                bucket["full"] = bucket.get("full", 0) + 1
            outside = self.haus.outside_temp()
            if outside is not None:
                bucket["osum"] = round(bucket.get("osum", 0.0) + outside, 1)
                bucket["on"] = bucket.get("on", 0) + 1
            valve = result.get("valve_all")
            if valve is not None:
                hour = dt_util.now().hour
                bucket.setdefault("vh", [0.0] * 24)[hour] += valve
                bucket.setdefault("vn", [0] * 24)[hour] += 1
            for day in [d for d in self.stats[room_id] if d < cutoff]:
                del self.stats[room_id][day]
        self._save(30)

    def _record_punctual(self, room_id: str, bucket: dict, mode: str | None, temp: float | None, target: float | None, after_vent: bool) -> None:
        """Pünktlich warm? Beim Beginn der Komfortzeit laut Plan: wie viele Minuten später war der Raum warm genug
        (höchstens 0,5 °C unter Soll) bzw. wie viele Minuten vorher schon (beim Vorheizen)."""
        rt = self._rt(room_id)
        now = dt_util.utcnow().timestamp()
        prev = rt.get("p_mode")
        rt["p_mode"] = mode
        warm = temp is not None and target is not None and temp >= target - 0.5
        if mode == "vorheizen":
            if warm and not rt.get("p_pre_warm"):
                rt["p_pre_warm"] = now
            return
        if mode == "komfort" and prev in ("vorheizen", "eco", "abwesend", "leer", "warm") and not after_vent and temp is not None:
            early = round((now - rt["p_pre_warm"]) / 60) if prev == "vorheizen" and rt.get("p_pre_warm") else 0
            rt["p_start"] = {"at": now, "early": early, "hm": dt_util.now().strftime("%H:%M")}
            rt["p_pre_warm"] = None
            if warm:
                bucket.setdefault("pw", []).append([rt["p_start"]["hm"], 0, early])
                rt["p_start"] = None
            return
        rt["p_pre_warm"] = None if mode != "vorheizen" else rt.get("p_pre_warm")
        st = rt.get("p_start")
        if not st:
            return
        if mode != "komfort" or after_vent:
            # Komfortzeit vorbei, Fenster, von Hand …: nicht rechtzeitig warm geworden bzw. keine Aussage
            if mode not in ("fenster", "manuell", "boost"):
                bucket.setdefault("pw", []).append([st["hm"], None, 0])
            rt["p_start"] = None
            return
        late = round((now - st["at"]) / 60)
        if warm or late >= 240:
            bucket.setdefault("pw", []).append([st["hm"], late if warm else None, 0])
            rt["p_start"] = None
        if len(bucket.get("pw") or []) > 12:
            bucket["pw"] = bucket["pw"][-12:]

    def _record_savings(self, room_id: str, bucket: dict, result: dict, temp: float | None) -> None:
        """Was das Absenken bringt: je Anlass Minuten und Grad-Minuten, um die der Raum wirklich kühler war als ohne Absenken."""
        mode = result.get("mode")
        room = self.rooms[room_id]
        target = result.get("target")
        if mode == "eco":
            ref = float(room.get("comfort", 21))
        elif mode in ("fenster", "abwesend", "urlaub", "frost", "leer", "eco_fix"):
            ref = result.get("plan_target")
        else:
            return
        if ref is None:
            return
        drop = ref - (target if target is not None and not result.get("hvac_off") else (temp if temp is not None else ref))
        if temp is not None:
            drop = min(drop, ref - temp)  # nur so weit, wie der Raum wirklich kühler war
        key = {"leer": "abwesend", "eco_fix": "eco", "frost": "urlaub"}.get(mode, mode)
        sav = bucket.setdefault("sav", {})
        m, dm = sav.get(key, [0, 0.0])
        sav[key] = [m + 1, round(dm + max(0.0, drop), 1)]

    # ------------------------------------------------------------ Therme
    # (Schlüssel, Domänen, Muster der Entitäts-ID) – myVaillant u. Ä.; eigene Wahl über boiler_<schlüssel>
    BOILER_FIND = (
        ("climate", ("climate",), r"circuit_\d+_climate$|heizkreis"),
        ("flow_set", ("sensor",), r"circuit_\d+_flow_temperature_setpoint$|vorlauf_?soll"),
        ("curve", ("number", "sensor"), r"circuit_\d+_heating_curve$"),
        ("min_flow", ("number",), r"min_flow_temperature_setpoint$"),
        ("limit_out", ("number",), r"heat_demand_limited_by_outside_temperature$"),
        ("outside", ("sensor",), r"_outdoor_temperature$"),
        ("pressure", ("sensor",), r"water_pressure$|wasserdruck|anlagendruck"),
        ("state", ("sensor",), r"circuit_\d+_state$"),
        ("burner", ("sensor",), r"energy_manager_state$"),
        ("room_set", ("sensor",), r"circuit_\d+_desired_heating_temperature$"),
        ("dhw_temp", ("sensor",), r"hot_water_\d+_tank_temperature$"),
        ("dhw_set", ("sensor",), r"hot_water_\d+_setpoint$"),
        ("trouble", ("binary_sensor",), r"trouble_codes$"),
        ("gas_heat", ("sensor",), r"consumed_primary_energy_heating$"),
        ("gas_dhw", ("sensor",), r"consumed_primary_energy_domestic_hot_water$"),
    )
    BOILER_OWN = ("circuit_flow", "circuit_return", "fbh_flow", "fbh_return")

    def boiler(self) -> dict[str, Any]:
        """Entitäten der Therme (automatisch erkannt bzw. gewählt) und der Temperaturfühler an Heizkreis und Fußbodenheizung."""
        import re  # noqa: PLC0415
        ids = getattr(self.hass.states, "async_entity_ids", None)
        ent: dict[str, str | None] = {}
        for key, domains, pat in self.BOILER_FIND:
            own = self.settings.get(f"boiler_{key}")
            if own:
                ent[key] = own
                continue
            rx = re.compile(pat)
            ent[key] = next((e for d in domains for e in sorted(ids(d) if ids else []) if rx.search(e)), None)
        # eigene Fühler: am Namen erkennen (Vorlauf/Rücklauf + Fußboden/FBH bzw. Heizkreis)
        temps = []
        for e in sorted(ids("sensor") if ids else []):
            st = self.hass.states.get(e)
            if st is not None and (st.attributes.get("device_class") == "temperature" or st.attributes.get("unit_of_measurement") == "°C"):
                temps.append((e, f"{e} {getattr(st, 'name', '') or ''}".lower()))
        fbh = r"fbh|fu(ß|ss)boden|fussboden|flächen|flaechen"
        guess = {
            "fbh_flow": lambda t: re.search(r"vorlauf", t) and re.search(fbh, t),
            "fbh_return": lambda t: re.search(r"r(ü|ue|u)cklauf", t) and re.search(fbh, t),
            "circuit_flow": lambda t: re.search(r"heiz(ungs)?kreis", t) and not re.search(r"r(ü|ue|u)cklauf|soll", t),
            "circuit_return": lambda t: re.search(r"heiz(ungs)?kreis", t) and re.search(r"r(ü|ue|u)cklauf", t),
        }
        for key in self.BOILER_OWN:
            ent[key] = self.settings.get(f"boiler_{key}") or next((e for e, t in temps if guess[key](t)), None)
        if not ent.get("circuit_flow") and ent.get("fbh_flow"):
            # Heizkreis-Fühler am selben Gerät wie die Fußboden-Fühler (z. B. Shelly mit drei Fühlern)
            try:
                reg = er.async_get(self.hass)
                dev = getattr(reg.async_get(ent["fbh_flow"]), "device_id", None)
                if dev:
                    taken = {ent.get("fbh_flow"), ent.get("fbh_return")}
                    ent["circuit_flow"] = next((e for e, _ in temps if e not in taken and getattr(reg.async_get(e), "device_id", None) == dev), None)
            except Exception:  # noqa: BLE001
                pass
        found = bool(ent.get("flow_set") or ent.get("climate") or ent.get("circuit_flow") or ent.get("fbh_flow"))
        return {"found": found, "entities": ent}

    async def async_boiler_history(self, days: int = 14) -> list[list]:
        """Stundenwerte aus den Statistiken: [Zeit, außen, Vorlauf-Soll, Heizkreis, FBH-Vorlauf, FBH-Rücklauf, Heizkreis-Rücklauf]."""
        try:
            from homeassistant.components.recorder import get_instance  # noqa: PLC0415
            from homeassistant.components.recorder.statistics import statistics_during_period  # noqa: PLC0415
        except ImportError:
            return []
        ent = self.boiler()["entities"]
        out_id = ent.get("outside") or self.haus.settings.get("outside_sensor")
        cols = [out_id, ent.get("flow_set"), ent.get("circuit_flow"), ent.get("fbh_flow"), ent.get("fbh_return"), ent.get("circuit_return")]
        ids = {c for c in cols if c}
        if not out_id or len(ids) < 2:
            return []
        start = dt_util.utcnow() - timedelta(days=days)
        try:
            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period, self.hass, start, None, ids, "hour", None, {"mean"})
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Thermen-Statistik nicht lesbar: %s", err)
            return []
        rows: dict[float, list] = {}
        for i, c in enumerate(cols):
            for r in stats.get(c) or [] if c else []:
                t = r.get("start")
                t = t.timestamp() if hasattr(t, "timestamp") else float(t)
                if r.get("mean") is None:
                    continue
                rows.setdefault(t, [round(t)] + [None] * len(cols))[i + 1] = round(r["mean"], 1)
        return [rows[t] for t in sorted(rows) if rows[t][1] is not None]

    # ------------------------------------------------------------ weitere Berichte
    def _heat_meter(self) -> str | None:
        """Gas- bzw. Wärmezähler: eigene Wahl, sonst Energie-Dashboard (wird in async_report_extra ergänzt), sonst erster Gaszähler."""
        if self.settings.get("heat_meter"):
            return self.settings["heat_meter"]
        ids = getattr(self.hass.states, "async_entity_ids", None)
        for eid in sorted(ids("sensor")) if ids else []:
            st = self.hass.states.get(eid)
            if st is not None and st.attributes.get("device_class") == "gas" and st.attributes.get("state_class") in ("total", "total_increasing"):
                return eid
        return None

    async def _async_heat_energy(self, start_day, days: int) -> dict[str, Any] | None:
        """Wärme (Gas) je Tag in kWh aus den Statistiken, dazu Kosten aus dem Energie-Dashboard, wenn dort eingetragen."""
        try:
            from homeassistant.components.recorder import get_instance  # noqa: PLC0415
            from homeassistant.components.recorder.statistics import statistics_during_period  # noqa: PLC0415
        except ImportError:
            return None
        src: dict[str, Any] = {}
        if not self.settings.get("heat_meter"):
            try:
                from homeassistant.components.energy.data import async_get_manager  # noqa: PLC0415
                prefs = (await async_get_manager(self.hass)).data or {}
                src = next((s for s in prefs.get("energy_sources") or [] if s.get("type") == "gas" and s.get("stat_energy_from")), {})
            except Exception:  # noqa: BLE001
                src = {}
        meter = src.get("stat_energy_from") or self._heat_meter()
        if not meter:
            return None
        st = self.hass.states.get(meter)
        unit = (st.attributes.get("unit_of_measurement") if st is not None else None) or "kWh"
        factor = 1.0 if unit.lower() in ("kwh",) else 0.001 if unit.lower() == "wh" else float(self.settings.get("gas_factor") or 10.3)
        start = dt_util.start_of_local_day(datetime.combine(start_day, datetime.min.time()))
        ids = {meter} | ({src["stat_cost"]} if src.get("stat_cost") else set())
        try:
            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period, self.hass, start, dt_util.utcnow(), ids, "day", None, {"change"})
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Wärmestatistik nicht lesbar: %s", err)
            return None

        def per_day(sid: str) -> dict[str, float]:
            out: dict[str, float] = {}
            for r in stats.get(sid) or []:
                t = r.get("start")
                t = dt_util.utc_from_timestamp(t) if isinstance(t, (int, float)) else t
                out[dt_util.as_local(t).date().isoformat()] = (out.get(dt_util.as_local(t).date().isoformat(), 0.0) + (r.get("change") or 0))
            return out
        raw = per_day(meter)
        if not raw:
            return None
        kwh = {d: round(v * factor, 2) for d, v in raw.items()}
        cost = None
        if src.get("stat_cost"):
            cost = per_day(src["stat_cost"])
        elif src.get("number_energy_price") or src.get("entity_energy_price"):
            price = src.get("number_energy_price")
            if price is None:
                ps = self.hass.states.get(src["entity_energy_price"])
                try:
                    price = float(ps.state) if ps is not None else None
                except ValueError:
                    price = None
            if price:
                cost = {d: round(v * float(price), 2) for d, v in raw.items()}
        return {"meter": meter, "unit": unit, "factor": factor, "kwh": kwh, "cost": cost, "dashboard": bool(src)}

    async def async_report_extra(self, days: int) -> dict[str, Any]:
        """Weitere Berichte: pünktlich warm, Verbrauch je Gradtag, Anteil je Raum, was das Absenken bringt, Geräte."""
        days2 = min(STATS_DAYS, days * 2)
        rep = self.report(days2)
        rep.pop("_analysis", None)
        today = dt_util.now().date()
        dates = [(today - timedelta(days=days2 - 1 - i)).isoformat() for i in range(days2)]
        # Außentemperatur je Tag (Mittel über die Räume mit Wert)
        outs = []
        for i in range(days2):
            vals = [rows[i]["outside_avg"] for rows in rep.values() if rows[i].get("outside_avg") is not None]
            outs.append(round(sum(vals) / len(vals), 1) if vals else None)
        cur = {rid: rows[-days:] for rid, rows in rep.items()}
        energy = await self._async_heat_energy(today - timedelta(days=days2 - 1), days2)
        out: dict[str, Any] = {}
        # Verbrauch je Gradtag
        if energy:
            def period(idx: range) -> dict[str, Any]:
                k = sum(energy["kwh"].get(dates[i], 0) for i in idx if i < len(dates) - 0)
                g = sum(degree_days(outs[i]) for i in idx)
                c = sum((energy["cost"] or {}).get(dates[i], 0) for i in idx) if energy["cost"] else None
                full = [i for i in idx if dates[i] in energy["kwh"]]
                return {"kwh": round(k, 1), "gt": round(g, 1), "per_gt": round(k / g, 2) if g >= 5 and len(full) >= len(idx) * 0.7 else None,
                        "cost": round(c, 2) if c is not None else None,
                        "out": round(sum(o for o in (outs[i] for i in idx) if o is not None) / max(1, sum(1 for i in idx if outs[i] is not None)), 1) if any(outs[i] is not None for i in idx) else None}
            now_p, prev_p = period(range(days2 - days, days2)), period(range(0, days2 - days)) if days2 > days else None
            out["energy"] = {"meter": energy["meter"], "unit": energy["unit"], "factor": energy["factor"], "dashboard": energy["dashboard"],
                             "now": now_p, "prev": prev_p,
                             "days": [{"date": dates[i], "kwh": energy["kwh"].get(dates[i]), "gt": degree_days(outs[i]), "out": outs[i]} for i in range(days2 - days, days2)]}
        per_gt = out.get("energy", {}).get("now", {}).get("per_gt") if out.get("energy") else None
        # Anteil je Raum (nach Ventil-Stunden)
        vh = {rid: sum(v for r in rows for v in (r.get("valve_hours") or []) if v is not None) / 100 for rid, rows in cur.items()}
        tot = sum(vh.values())
        if tot > 0:
            kwh_now = out.get("energy", {}).get("now", {}).get("kwh") if out.get("energy") else None
            cost_now = out.get("energy", {}).get("now", {}).get("cost") if out.get("energy") else None
            out["share"] = sorted(({"room": rid, "valve_h": round(v, 1), "pct": round(100 * v / tot),
                                    "kwh": round(kwh_now * v / tot, 1) if kwh_now else None,
                                    "cost": round(cost_now * v / tot, 2) if cost_now else None} for rid, v in vh.items() if v > 0),
                                  key=lambda x: -x["pct"])
        # Pünktlich warm
        out["punctual"] = {rid: x for rid, rows in cur.items()
                           if (x := punctual_summary(rows, self._preheat_mode(self.rooms[rid]), self.rooms[rid].get("type") == "flaeche"))}
        # Was das Absenken bringt
        out["savings"] = savings_summary(cur, per_gt)
        # Geräte: Probleme aus dem Protokoll und der Stand jetzt
        cut = dt_util.utcnow().timestamp() - days * 86400
        groups: dict[str, dict] = {}
        for e in getattr(self.log, "entries", []):
            if e.get("ts", 0) < cut or e.get("mod"):
                continue
            title = e.get("title") or ""
            if not (e.get("cat") == "health" or (e.get("cat") == "notify" and "nicht erreichbar" in title)) or " wieder" in title:
                continue
            g = groups.setdefault(title, {"title": title, "n": 0, "last": 0, "rooms": set(), "why": e.get("why")})
            g["n"] += 1
            g["last"] = max(g["last"], e["ts"])
            if e.get("rn"):
                g["rooms"].add(e["rn"])
        issues = [{**g, "rooms": sorted(g["rooms"])} for g in sorted(groups.values(), key=lambda g: -g["n"])][:12]
        now_bad = []
        for rid, room in self.rooms.items():
            res = self._rt(rid).get("result") or {}
            for b in res.get("battery_low") or []:
                now_bad.append({"kind": "battery", "room": room.get("name"), "name": b.get("name"), "level": b.get("level")})
            for c in room.get("climates") or []:
                stt = self.hass.states.get(c)
                if stt is None or stt.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                    now_bad.append({"kind": "offline", "room": room.get("name"), "name": self._name(c)})
        out["devices"] = {"issues": issues, "now": now_bad}
        return out

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
                        # Ø Ventilöffnung je Stunde (None = keine Werte) und über den Tag
                        "valve_hours": [round(s / n) if n else None for s, n in zip(b.get("vh") or [0] * 24, b.get("vn") or [0] * 24)],
                        "valve_avg": round(sum(b["vh"]) / sum(b["vn"])) if sum(b.get("vn") or []) else None,
                        # Analyse: Minuten in Komfort mit Messwert, davon zu kalt; Ø Abweichung; überheizt; Ventil ≥ 90 %
                        "comfort_n": b.get("cn", 0), "under_min": b.get("under", 0),
                        "comfort_dev": round(b["cdev"] / b["cn"], 2) if b.get("cn") else None,
                        "measured_min": b.get("mn", 0), "over_min": b.get("over", 0), "full_min": b.get("full", 0),
                        "comfort_over": b.get("co"),
                        "punctual": b.get("pw") or [],
                        "savings": b.get("sav") or {},
                        "outside_avg": round(b["osum"] / b["on"], 1) if b.get("on") else None,
                        "fire_min": b.get("fire", 0),
                        # Fußbodenheizung: Ø Einschaltdauer des Stellantriebs in der Komfortzeit; Mischbetrieb: Minuten mit Zusatz
                        "floor_valve": round(b["fv"] / b["fvn"]) if b.get("fvn") else None, "floor_n": b.get("fvn", 0),
                        "assist_min": b.get("as"),
                    }
                )
            out[room_id] = rows
        out["_analysis"] = {
            room_id: room_analysis(out[room_id], self.heat_rates.get(room_id), room.get("type") or "heizkoerper",
                                   mixed=room.get("type") == "flaeche" and bool(room.get("assist_entities")))
            for room_id, room in self.rooms.items()
        }
        return out
