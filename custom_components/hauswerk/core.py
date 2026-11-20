"""Hauswerk-Kern: Einstellungen und Zustände, die für alle Module gelten.

Anwesenheit (Personen, Zone, Wartezeiten, Heimweg, Gäste), Urlaub (Schalter, Zeitraum, Kalender),
Wetter (mit Frost-Vorhersage), Benachrichtigungen aufs Handy (mit Ruhezeit), Darstellung,
Widgets der Startseite und Berechtigungen. Module (z. B. Heizwerk) lesen
`away`, `approaching`, `away_for` und `vacation` und melden sich mit `subscribe()` für Änderungen an.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
import logging
from typing import Any

from homeassistant.const import STATE_HOME, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CALENDAR_REFRESH,
    FORECAST_REFRESH,
    HOUSE_DEFAULTS,
    HOUSE_KEYS,
    HOUSE_STORAGE_KEY,
    NOTIFY_REPEAT,
)
from .log import Protokoll, log_settings
from .logic import distance_km, in_quiet_hours, is_vacation, keyword_match, keywords


_LOGGER = logging.getLogger(__name__)

BAD_STATES = {STATE_UNAVAILABLE, STATE_UNKNOWN, None}
PROXIMITY_TREND = 15 * 60  # Sekunden: so lange gilt „kommt näher“ nach der letzten Annäherung
VACATION_KEYS = ("vacation_source", "vacation_calendar", "vacation_keywords")


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _de(value: float) -> str:
    """Zahl mit einer Nachkommastelle und deutschem Komma."""
    return f"{value:.1f}".replace(".", ",")


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
        self._prox: dict[str, tuple[float, float]] = {}  # Entfernungs-Sensor -> (letzter Abstand km, Zeit der letzten Annäherung)
        self._dir_ids: dict[str, str | None] = {}         # Entfernungs-Sensor -> Bewegungs-Sensor der Integration „Nähe“
        self.vacation = False
        # Arbeitstage aus dem Kalender der Integration „Arbeitstag“ (ISO-Daten, von/bis gelesen)
        self._workdays: set[str] = set()
        self._wd_range: tuple[str, str] | None = None
        self._wd_at = 0.0
        self._wd_error: str | None = None
        # Müllabholung der nächsten zwei Wochen: [{"date": ISO, "type": Abfallart, "cal": calendar.*}]
        self._waste: list[dict] = []
        self._waste_at = 0.0
        self._waste_error: str | None = None
        # Urlaub aus dem Kalender
        self._cal_vacation = False
        self._cal_events: list[dict[str, Any]] = []
        self._cal_error: str | None = None
        self._cal_at = 0.0
        self._flags: dict[str, Any] = {}
        # Benachrichtigungen: zuletzt gesendet je Schlüssel, in der Ruhezeit zurückgehalten, gerade aktuell
        self._sent: dict[str, float] = {}
        self._queued: dict[str, tuple] = {}
        self._recent: dict[tuple, float] = {}
        self.notify_health: dict[str, dict] = {}   # Kanal → letzte Zustellung {ok, at, error}
        self.notify_hist: list[dict] = []          # letzte Nachrichten {at, title, message, kind, how, channels}
        self._bundle: dict[str, dict] = {}         # Kanal → {last, items, timer}  # (Kanal, Titel, Text) → gesendet um: gegen Doppel nach Neuladen o. Ä.
        self._active: set[str] = set()
        # Wettervorhersage (Frost)
        self._fc_at = 0.0
        self.frost_low: float | None = None
        self.frost_day: str | None = None
        # Funk-Auslastung (Duty Cycle): gefundene Sensoren und aktueller Zustand
        self._radio_found: list[str] = []
        self._radio_at = 0.0
        self.radio_level: float | None = None
        self.radio_entity: str | None = None
        self.radio_busy = False
        self._listeners: set[Callable[[], None]] = set()
        self.extra_status: dict[str, Callable[[], Any]] = {}  # weitere Module (z. B. Kraftwerk-Geräte)
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
        current = dict(stored.get("settings") or {})
        # Später in den Kern gewanderte Einstellungen (z. B. Feiertage) aus Heizwerk nachholen
        for key, value in (legacy or {}).items():
            if key in HOUSE_KEYS and key not in current:
                current[key] = value
        self.settings.update(current)
        # Heimweg-Grenze früher in Kilometern, jetzt in Metern
        old_km = self.settings.pop("proximity_km", None)
        if old_km and not self.settings.get("proximity_m"):
            self.settings["proximity_m"] = float(old_km) * 1000
        # Termin-Kalender früher nur für den Bildschirmschoner, jetzt zentral
        old_cals = self.settings.pop("tablet_calendars", None)
        if old_cals and not self.settings.get("calendars"):
            self.settings["calendars"] = list(old_cals)
        self._waste_new = "waste_calendars" not in current  # Müllabholung einmalig erkennen (async_start)
        # Benachrichtigungen: alte Auswahl (Apps + Home Assistant) als Kanäle übernehmen
        if self.settings.get("notify_channels") is None:
            self.settings["notify_channels"] = [f"svc:{t}" for t in self.settings.get("notify_targets") or []] + (
                ["ha"] if self.settings.get("notify_ha") else [])
        self.settings = {k: v for k, v in self.settings.items() if k in HOUSE_KEYS}
        self.notify_health = stored.get("notify_health") or {}
        self.notify_hist = stored.get("notify_hist") or []
        await self._store.async_save(self._data())

    def _data(self) -> dict:
        return {"settings": self.settings, "notify_health": self.notify_health, "notify_hist": self.notify_hist[-40:]}

    def _save(self) -> None:
        self._store.async_delay_save(self._data, 2)

    # ------------------------------------------------------------ Lebenszyklus
    async def async_start(self) -> None:
        self._unsubs.append(async_track_time_interval(self.hass, self._async_tick, timedelta(minutes=1)))
        self._track()
        self._find_workday_calendar()
        self._find_waste_calendars()
        await self._async_refresh_calendar(force=True)
        await self._async_refresh_workdays(force=True)
        await self._async_refresh_waste(force=True)
        await self._async_refresh_forecast(force=True)
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
        await self._async_refresh_workdays()
        if getattr(self, "_waste_new", False):
            self._find_waste_calendars()
        await self._async_refresh_waste()
        self._waste_remind()
        await self._async_refresh_forecast()
        self._flush_queue()
        self.update_radio()
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
        if ("notify_targets" in settings or "notify_ha" in settings) and "notify_channels" not in settings:
            # alte Auswahl (Apps, Home Assistant) – z. B. aus einem noch nicht neu geladenen Panel – in die Kanäle übernehmen
            targets = settings.get("notify_targets", self.settings.get("notify_targets")) or []
            ha = settings.get("notify_ha", self.settings.get("notify_ha"))
            keep = [c for c in self.settings.get("notify_channels") or [] if not c.startswith("svc:") and c != "ha"]
            settings["notify_channels"] = [f"svc:{t}" for t in targets] + (["ha"] if ha else []) + keep
        changed = [k for k, v in settings.items() if self.settings.get(k) != v]
        if not changed:
            return
        log_settings(self.log, settings, changed, by, old=self.settings)
        self.settings.update(settings)
        self._save()
        self._track()
        if any(k in settings for k in VACATION_KEYS):
            await self._async_refresh_calendar(force=True)
        if "workday_calendar" in settings:
            await self._async_refresh_workdays(force=True)
        if any(k in settings for k in ("waste_calendars", "waste_hidden", "waste_remind")):
            await self._async_refresh_waste(force=True)
            self._waste_remind()
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
        """Auf dem Heimweg: näher als die Grenze UND unterwegs zur Wohnung.

        Wer in der Nähe ist, aber steht (z. B. Arbeit oder Einkauf um die Ecke), zählt nicht –
        sonst würde die Abwesenheit nie greifen. Die Richtung kommt aus dem Bewegungs-Sensor der
        Integration „Nähe“ (gleiches Gerät), sonst daraus, ob der Abstand in den letzten 15 Minuten kleiner wurde.
        """
        limit_km = float(self.settings.get("proximity_m") or 0) / 1000
        if limit_km <= 0:
            return False
        now = dt_util.utcnow().timestamp()
        near = False
        for entity_id in self.settings.get("proximity_sensors") or []:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in BAD_STATES:
                continue
            km = distance_km(_float(state.state), state.attributes.get("unit_of_measurement"))
            if km is None:
                continue
            last = self._prox.get(entity_id)
            if last is None or km < last[0] - 0.05:
                drop = now if last is not None else 0.0
            else:
                drop = last[1]
            self._prox[entity_id] = (km, drop)
            if km > limit_km:
                continue
            direction = self._direction(entity_id)
            if direction is not None:
                near = near or direction == "towards"
            else:
                near = near or (drop and now - drop <= PROXIMITY_TREND)
        return bool(near)

    def _direction(self, entity_id: str) -> str | None:
        """Bewegungsrichtung zum Entfernungs-Sensor („towards“, „away_from“, „stationary“, „arrived“) oder None."""
        if entity_id not in self._dir_ids:
            found = None
            try:
                reg = er.async_get(self.hass)
                entry = reg.async_get(entity_id)
                uid = getattr(entry, "unique_id", None) or ""
                if entry is not None and entry.device_id and "dist_to_zone" in uid:
                    want = uid.replace("dist_to_zone", "dir_of_travel")
                    found = next((e.entity_id for e in er.async_entries_for_device(reg, entry.device_id)
                                  if getattr(e, "unique_id", None) == want), None)
            except Exception:  # noqa: BLE001 - Register nicht verfügbar: Abstand-Trend nutzen
                found = None
            self._dir_ids[entity_id] = found
        dir_id = self._dir_ids[entity_id]
        state = self.hass.states.get(dir_id) if dir_id else None
        if state is None or state.state not in ("towards", "away_from", "stationary", "arrived"):
            return None
        return state.state

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

    # ------------------------------------------------------------ Arbeitstage
    def _find_workday_calendar(self) -> None:
        """Ist nur der Arbeitstag-Sensor gewählt, den Kalender derselben Integration übernehmen (gibt es seit HA 2025)."""
        sensor = self.settings.get("workday_entity")
        if self.settings.get("workday_calendar") or not sensor:
            return
        reg = er.async_get(self.hass)
        entry = reg.async_get(sensor)
        if entry is None or not entry.config_entry_id:
            return
        cal = next((e.entity_id for e in er.async_entries_for_config_entry(reg, entry.config_entry_id)
                    if e.domain == "calendar" and not e.disabled_by), None)
        if cal:
            self.settings["workday_calendar"] = cal
            self._save()
            self.log.add("settings", "Arbeitstage-Kalender übernommen", f"{self._name(cal)} – gehört zu {self._name(sensor)}")

    async def _async_refresh_workdays(self, force: bool = False) -> None:
        """Arbeitstage der nächsten zwei Wochen aus dem Kalender (jeder Arbeitstag ist ein ganztägiger Termin)."""
        now_ts = dt_util.utcnow().timestamp()
        cal = self.settings.get("workday_calendar")
        today = dt_util.now().date()
        stale = self._wd_range is None or self._wd_range[0] != today.isoformat()
        if not force and not stale and now_ts - self._wd_at < 3600:
            return
        self._wd_at = now_ts
        if not cal:
            self._workdays, self._wd_range, self._wd_error = set(), None, None
            return
        start = dt_util.start_of_local_day(today)
        end = start + timedelta(days=15)
        try:
            events = await async_calendar_events(self.hass, cal, start, end)
        except Exception as err:  # noqa: BLE001 - Kalender weg/defekt: Sensor gilt weiter
            self._wd_error = str(err) or type(err).__name__
            _LOGGER.warning("Arbeitstage-Kalender %s nicht lesbar: %s", cal, err)
            return
        days: set[str] = set()
        for ev in events:
            begin, _ = parse_when(ev.get("start"))
            finish, _ = parse_when(ev.get("end"))
            if begin is None:
                continue
            day = begin.date()
            last = (finish - timedelta(seconds=1)).date() if finish is not None and finish > begin else day
            while day <= last:
                days.add(day.isoformat())
                day += timedelta(days=1)
        self._workdays = days
        self._wd_range = (today.isoformat(), (today + timedelta(days=14)).isoformat())
        self._wd_error = None

    # ------------------------------------------------------------ Müllabholung
    def _find_waste_calendars(self) -> None:
        """Einmalig: Kalender von Waste Collection Schedule (oder mit Müll/Abfall im Namen) zur Müllabholung nehmen."""
        if not getattr(self, "_waste_new", False):
            return
        reg = er.async_get(self.hass)
        found = []
        for state in self.hass.states.async_all("calendar"):
            entry = reg.async_get(state.entity_id)
            text = f"{state.entity_id} {state.attributes.get('friendly_name', '')}".lower()
            if (getattr(entry, "platform", None) == "waste_collection_schedule") or any(
                    w in text for w in ("waste", "abfall", "müll", "muell", "abfuhr")):
                found.append(state.entity_id)
        # Kalender-Integrationen laden nach dem Start: bis zu 15 Minuten weiter suchen, dann „keine“ merken
        self._waste_tries = getattr(self, "_waste_tries", 0) + 1
        if not found and self._waste_tries < 15:
            return
        self._waste_new = False
        self.settings["waste_calendars"] = found
        if found:
            self.settings["calendars"] = [c for c in self.settings.get("calendars") or [] if c not in found]
            self.log.add("settings", "Müllabholung erkannt", ", ".join(self._name(c) for c in found))
        self._save()

    async def _async_refresh_waste(self, force: bool = False) -> None:
        """Abholtermine der nächsten zwei Wochen aus den Müll-Kalendern (stündlich und bei Tageswechsel)."""
        now_ts = dt_util.utcnow().timestamp()
        today = dt_util.now().date().isoformat()
        stale = not self._waste or self._waste[0]["date"] < today
        if not force and not stale and now_ts - self._waste_at < 3600:
            return
        self._waste_at = now_ts
        cals = self.settings.get("waste_calendars") or []
        start = dt_util.start_of_local_day(dt_util.now().date())
        end = start + timedelta(days=15)
        out, errors = [], []
        for cal in cals:
            try:
                events = await async_calendar_events(self.hass, cal, start, end)
            except Exception as err:  # noqa: BLE001 - ein defekter Kalender soll die anderen nicht stören
                errors.append(f"{self._name(cal)}: {err or type(err).__name__}")
                continue
            for ev in events:
                begin, _ = parse_when(ev.get("start"))
                kind = str(ev.get("summary") or "Abfall").strip()
                if begin is None or begin.date().isoformat() < today:
                    continue
                out.append({"date": begin.date().isoformat(), "type": kind, "cal": cal})
        self._waste = sorted(out, key=lambda e: (e["date"], e["type"]))
        self._waste_error = "; ".join(errors) or None

    def waste(self) -> list[dict]:
        """Kommende Abholungen ohne ausgeblendete Abfallarten."""
        hidden = {h.lower() for h in self.settings.get("waste_hidden") or []}
        return [e for e in self._waste if e["type"].lower() not in hidden]

    def waste_due(self) -> dict | None:
        """Gerade dran: am Vorabend ab der Erinnerungszeit (morgen) und am Abholtag bis 10 Uhr (heute)."""
        remind = self.settings.get("waste_remind")
        if not remind:
            return None
        now = dt_util.now()
        minute = now.hour * 60 + now.minute
        today = now.date()
        h, m = (int(x) for x in str(remind).split(":")[:2])
        if minute >= h * 60 + m:
            day, when = today + timedelta(days=1), "morgen"
        elif minute < 600:
            day, when = today, "heute"
        else:
            return None
        types = [e["type"] for e in self.waste() if e["date"] == day.isoformat()]
        return {"date": day.isoformat(), "when": when, "types": list(dict.fromkeys(types))} if types else None

    @callback
    def _waste_remind(self) -> None:
        """Erinnerung aufs Handy am Vorabend (einmal je Abholtag), erledigt nach der Abholung."""
        due = self.waste_due()
        key = f"waste_{due['date']}" if due and due["when"] == "morgen" else None
        for old in [k for k in self._active if k.startswith("waste_") and k != key]:
            self.clear(old)
        if key:
            self.notify(key, "waste", "Morgen Müllabfuhr", f"{', '.join(due['types'])} – Tonne heute Abend rausstellen.")

    def is_workday(self, day: date | None = None) -> bool | None:
        """Ist der Tag ein Arbeitstag? Aus dem Kalender (auch künftige Tage), heute sonst aus dem Sensor; None = unbekannt."""
        today = dt_util.now().date()
        day = day or today
        if self._wd_range and self._wd_range[0] <= day.isoformat() <= self._wd_range[1]:
            return day.isoformat() in self._workdays
        if day == today:
            state = self.hass.states.get(self.settings.get("workday_entity") or "")
            if state is not None and state.state in ("on", "off"):
                return state.state == "on"
        return None

    def workday_source(self) -> str | None:
        """Woher Hauswerk die Arbeitstage kennt (für Protokoll und Anzeige)."""
        if self._wd_range and self.settings.get("workday_calendar"):
            return self._name(self.settings["workday_calendar"])
        return self._name(self.settings["workday_entity"]) if self.settings.get("workday_entity") else None

    def free_days(self, days: int = 14) -> list[str]:
        """Freie Werktage (Feiertage, Brückentage …) der nächsten Tage – Mo–Fr, aber kein Arbeitstag."""
        today = dt_util.now().date()
        out = []
        for k in range(days):
            day = today + timedelta(days=k)
            if day.weekday() < 5 and self.is_workday(day) is False:
                out.append(day.isoformat())
        return out

    # ------------------------------------------------------------ Benachrichtigungen
    def _quiet(self) -> bool:
        if not self.settings.get("notify_quiet"):
            return False
        now = dt_util.now()
        return in_quiet_hours(now.hour * 60 + now.minute, self.settings.get("notify_quiet_from"),
                              self.settings.get("notify_quiet_to"))

    # ---- Kanäle
    def channels_for(self, kind: str | None = None) -> list[str]:
        """Kanäle eines Anlasses: eigene Auswahl je Anlass, sonst die Standard-Kanäle."""
        routes = self.settings.get("notify_routes") or {}
        if kind and routes.get(kind):
            return list(routes[kind])
        return list(self.settings.get("notify_channels") or [])

    def channel_name(self, ch: str) -> str:
        if ch == "ha":
            return "Home Assistant"
        kind, _, rest = ch.partition(":")
        if kind == "svc":
            return rest.removeprefix("mobile_app_").replace("_", " ").title()
        if kind == "tts":
            tts, _, player = rest.partition("|")
            return f"Ansage {self._name(player)}"
        return self._name(rest)

    def channel_ok(self, ch: str) -> bool:
        """Nutzbar? Dienst vorhanden bzw. Entität erreichbar."""
        if ch == "ha":
            return True
        kind, _, rest = ch.partition(":")
        if kind == "svc":
            return self.hass.services.has_service("notify", rest)
        if kind == "tts":
            tts, _, player = rest.partition("|")
            return all((st := self.hass.states.get(e)) is not None and st.state != "unavailable" for e in (tts, player)) \
                and self.hass.services.has_service("tts", "speak")
        if kind in ("ent", "sat"):
            st = self.hass.states.get(rest)
            return st is not None and st.state != "unavailable"
        return False

    def _target_names(self, kind: str | None = None) -> str:
        return ", ".join(self.channel_name(c) for c in self.channels_for(kind))

    @callback
    def send(self, channels: list[str], title: str, message: str, important: bool = False, key: str | None = None) -> list[str]:
        """Eine Nachricht an Kanäle schicken – gemeinsam für alle Module. Nicht nutzbare Kanäle werden übersprungen
        (Protokoll), dieselbe Nachricht an denselben Kanal innerhalb von 2 Minuten nur einmal (Schutz vor Doppeln
        durch Neuladen/Wiederverbinden). Ansagen in der Ruhezeit nur, wenn wichtig. Rückgabe: gesendete Kanäle."""
        now = dt_util.utcnow().timestamp()
        self._recent = {k: t for k, t in self._recent.items() if now - t < 120}
        local = dt_util.now()
        now_min = local.hour * 60 + local.minute
        hours = self.settings.get("notify_hours") or {}
        bundle = set(self.settings.get("notify_bundle") or [])
        paused = set(self.settings.get("notify_off") or [])
        sent = []
        for ch in dict.fromkeys(channels):
            if ch in paused:
                continue  # Empfänger pausiert (Benachrichtigungen › Empfänger)
            if (ch, title, message) in self._recent:
                continue
            if not self.channel_ok(ch):
                self.log.add("notify", "Kanal nicht erreichbar", f"{self.channel_name(ch)} ({ch}) – übersprungen")
                self._health(ch, False, "nicht erreichbar")
                continue
            voice = ch.startswith(("tts:", "sat:"))
            if not important:
                if voice and (self._quiet() or (self.settings.get("notify_voice_away", True) and self.away)):
                    continue  # Ansagen nicht nachts und nicht ins leere Haus
                win = hours.get(ch)
                if win and len(win) == 2 and not in_quiet_hours(now_min, win[0], win[1]):
                    continue  # außerhalb der Zeiten dieses Kanals nur Wichtiges
            self._recent[(ch, title, message)] = now
            if ch in bundle and not important and self._bundle_add(ch, title, message, now):
                sent.append(ch)
                continue
            self.hass.async_create_task(self._async_channel(ch, title, message, important, key))
            sent.append(ch)
        return sent

    def _bundle_add(self, ch: str, title: str, message: str, now: float) -> bool:
        """Bündeln: Die erste Meldung geht sofort raus; weitere binnen 5 Min. kommen gesammelt am Ende des Fensters.
        Rückgabe True = zurückgelegt (nicht sofort senden)."""
        b = self._bundle.get(ch)
        if not b or now - b["last"] >= 300:
            self._bundle[ch] = {"last": now, "items": [], "timer": None}
            return False
        b["items"].append((title, message))
        if b["timer"] is None:
            @callback
            def flush(_now=None, ch=ch) -> None:
                bb = self._bundle.get(ch)
                if not bb or not bb["items"]:
                    return
                items, bb["items"], bb["timer"] = bb["items"], [], None
                bb["last"] = dt_util.utcnow().timestamp()
                if len(items) == 1:
                    t, m = items[0]
                else:
                    t, m = f"Hauswerk: {len(items)} Meldungen", "\n".join(f"• {a}: {c}" for a, c in items)
                self.hass.async_create_task(self._async_channel(ch, t, m))
            b["timer"] = async_call_later(self.hass, max(1, 300 - (now - b["last"])), flush)
        return True

    def _health(self, ch: str, ok: bool, error: str | None = None) -> None:
        self.notify_health[ch] = {"ok": ok, "at": dt_util.utcnow().isoformat(), **({"error": error} if error else {})}
        self._save()

    async def _async_channel(self, ch: str, title: str, message: str, important: bool = False,
                             key: str | None = None, raise_errors: bool = False) -> None:
        kind, _, rest = ch.partition(":")
        if ch == "ha":
            domain, service, data = "persistent_notification", "create", {"title": title, "message": message}
            if key:
                data["notification_id"] = self._ha_id(key)
        elif kind == "svc":
            data = {"title": title, "message": message}
            if important:
                # iPhone: durchbricht „Nicht stören“ (zeitkritisch); Android: hohe Priorität, sofort zustellen
                data["data"] = {"push": {"interruption-level": "time-sensitive"}, "priority": "high", "ttl": 0,
                                "channel": "Hauswerk wichtig", "importance": "high"}
            domain, service = "notify", rest
        elif kind == "ent":
            domain, service, data = "notify", "send_message", {"entity_id": rest, "title": title, "message": message}
        elif kind == "tts":
            tts, _, player = rest.partition("|")
            domain, service, data = "tts", "speak", {"entity_id": tts, "media_player_entity_id": player, "message": f"{title}. {message}"}
        elif kind == "sat":
            domain, service, data = "assist_satellite", "announce", {"entity_id": rest, "message": f"{title}. {message}"}
        else:
            return
        try:
            await self.hass.services.async_call(domain, service, data, blocking=True)
            self._health(ch, True)
        except Exception as err:  # noqa: BLE001 - Kanal weg oder falsch eingerichtet: nur protokollieren
            _LOGGER.warning("Benachrichtigung über %s fehlgeschlagen: %s", ch, err)
            self.log.add("notify", "Nachricht nicht zugestellt", f"{self.channel_name(ch)}: {err}")
            self._health(ch, False, str(err) or type(err).__name__)
            if raise_errors:
                raise

    def notify_mode(self, kind: str) -> str:
        """Art der Benachrichtigung je Anlass: off | log | normal | important (früher an/aus)."""
        value = self.settings.get(f"notify_{kind}", "normal")
        if value is True:
            return "normal"
        if value is False or value is None:
            return "off"
        return value if value in ("off", "log", "normal", "important") else "normal"

    @callback
    def notify(self, key: str, kind: str, title: str, message: str,
               room: str | None = None, room_name: str | None = None) -> None:
        """Nachricht je nach Art: aufs Handy (normal oder wichtig), nur ins Protokoll oder gar nicht.

        Dieselbe Nachricht (key) kommt erst wieder, wenn sie mit clear() erledigt ist oder
        NOTIFY_REPEAT vergangen ist. In der Ruhezeit werden normale Nachrichten zurückgehalten
        und danach gesendet, falls der Anlass dann noch besteht; wichtige kommen sofort.
        """
        mode = self.notify_mode(kind)
        if mode == "off":
            return
        self._active.add(key)
        now = dt_util.utcnow().timestamp()
        if key in self._queued or now - self._sent.get(key, 0) < NOTIFY_REPEAT:
            return
        self._sent[key] = now
        important = mode == "important"
        chosen = self.channels_for(kind)
        targets = [c for c in chosen if c not in set(self.settings.get("notify_off") or [])]
        if mode == "log":
            how = "nur Protokoll"
        elif chosen and not targets:
            how = "nur hier – alle Empfänger pausiert"
        elif not targets:
            how = "nur hier – kein Kanal unter Benachrichtigungen gewählt"
        elif self._quiet() and not important:
            self._queued[key] = (title, message, room, room_name, kind)
            how = f"Ruhezeit – wird um {self.settings.get('notify_quiet_to')} gesendet, falls noch aktuell"
        else:
            sent = self.send(targets, title, message, important, key)
            how = f"{'wichtig ' if important else ''}gesendet an {', '.join(self.channel_name(c) for c in sent) or '– (kein Kanal erreichbar)'}"
        state = "log" if mode == "log" or not targets else "held" if key in self._queued else "sent"
        self._hist(title, message, kind, state, how)
        self.log.add("notify", title, f"{message} · {how}", room, room_name)

    def _hist(self, title: str, message: str, kind: str | None, state: str, how: str) -> None:
        self.notify_hist.append({"at": dt_util.utcnow().isoformat(), "title": title, "message": message,
                                 "kind": kind, "state": state, "how": how})
        del self.notify_hist[:-40]
        self._save()

    def notify_summary(self) -> dict:
        """Heute gesendet / zurückgehalten / nur Protokoll / nicht zugestellt, letzte Nachrichten und Zustand der Kanäle."""
        today = dt_util.now().date()
        day = [h for h in self.notify_hist if dt_util.as_local(dt_util.parse_datetime(h["at"])).date() == today]
        failed = sum(1 for v in self.notify_health.values() if not v.get("ok")
                     and dt_util.as_local(dt_util.parse_datetime(v["at"])).date() == today)
        return {"sent": sum(1 for h in day if h["state"] == "sent"), "held": sum(1 for h in day if h["state"] == "held"),
                "log": sum(1 for h in day if h["state"] == "log"), "failed": failed,
                "last": list(reversed(self.notify_hist[-10:])), "health": self.notify_health,
                "queued": len(self._queued)}

    @callback
    def clear(self, key: str) -> None:
        """Anlass erledigt (z. B. Fenster zu): Nachricht darf beim nächsten Mal wieder kommen."""
        if key in self._sent and any(c == "ha" for c in self.channels_for() + [c for r in (self.settings.get("notify_routes") or {}).values() for c in r]):
            self.hass.async_create_task(self._async_call(
                "persistent_notification", "dismiss", {"notification_id": self._ha_id(key)}))
        self._active.discard(key)
        self._sent.pop(key, None)
        self._queued.pop(key, None)

    @callback
    def _flush_queue(self) -> None:
        if not self._queued or self._quiet():
            return
        queued, self._queued = self._queued, {}
        for key, (title, message, room, room_name, *rest) in queued.items():
            if key in self._active:
                kind = rest[0] if rest else None
                sent = self.send(self.channels_for(kind), title, message, False, key)
                self._hist(title, message, kind, "sent", "nach der Ruhezeit gesendet")
                self.log.add("notify", title, f"{message} · nach der Ruhezeit gesendet an {', '.join(self.channel_name(c) for c in sent)}", room, room_name)

    @staticmethod
    def _ha_id(key: str) -> str:
        return "hauswerk_" + "".join(c if c.isalnum() else "_" for c in key)

    @callback
    def _send(self, title: str, message: str, important: bool = False, key: str | None = None, kind: str | None = None) -> None:
        self.send(self.channels_for(kind), title, message, important, key)

    async def _async_send(self, target: str, payload: dict[str, Any]) -> None:
        try:
            await self.hass.services.async_call("notify", target, payload, blocking=True)
        except Exception as err:  # noqa: BLE001 - App weg oder umbenannt: nur protokollieren
            _LOGGER.warning("Benachrichtigung an notify.%s fehlgeschlagen: %s", target, err)
            self.log.add("notify", "Nachricht nicht zugestellt", f"notify.{target}: {err}")

    async def _async_call(self, domain: str, service: str, data: dict[str, Any]) -> None:
        try:
            await self.hass.services.async_call(domain, service, data, blocking=True)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("%s.%s fehlgeschlagen: %s", domain, service, err)

    async def async_test_notify(self, by: str | None = None, channels: list[str] | None = None,
                                title: str | None = None, message: str | None = None) -> list[dict]:
        """Testnachricht aus dem Panel (ohne Ruhezeit) – an die gewählten Kanäle; Ergebnis je Kanal.
        Mit Titel/Text: Probe einer echten Meldung (z. B. Probehören einer Ansage)."""
        title = title or "Hauswerk"
        message = message or "Testnachricht – Benachrichtigungen funktionieren."
        out = []
        for ch in dict.fromkeys(channels if channels is not None else self.channels_for()):
            if not self.channel_ok(ch):
                out.append({"channel": ch, "ok": False, "error": "nicht erreichbar"})
                continue
            try:
                await self._async_channel(ch, title, message, raise_errors=True)
                out.append({"channel": ch, "ok": True})
            except Exception as err:  # noqa: BLE001
                out.append({"channel": ch, "ok": False, "error": str(err) or type(err).__name__})
        ok = [self.channel_name(r["channel"]) for r in out if r["ok"]]
        bad = [f"{self.channel_name(r['channel'])} ({r['error']})" for r in out if not r["ok"]]
        self.log.add("notify", "Testnachricht", (f"gesendet an {', '.join(ok)}" if ok else "nicht gesendet")
                     + (f" · Fehler: {', '.join(bad)}" if bad else "") + (f" · {by}" if by else ""))
        return out

    # ------------------------------------------------------------ Wetter
    def weather_entity(self) -> str | None:
        chosen = self.settings.get("weather_entity")
        if chosen:
            return chosen
        ids = getattr(self.hass.states, "async_entity_ids", None)
        found = sorted(ids("weather")) if ids else []
        return found[0] if found else None

    def outside_air(self) -> tuple[float | None, float | None]:
        """Außentemperatur (eigene Station oder Wetterdienst) und Luftfeuchte draußen."""
        entity_id = self.weather_entity()
        state = self.hass.states.get(entity_id) if entity_id else None
        attrs = state.attributes if state is not None else {}
        temp = self.outside_temp()
        if temp is None:
            temp = _float(attrs.get("temperature"))
        return temp, _float(attrs.get("humidity"))

    async def _async_refresh_forecast(self, force: bool = False) -> None:
        """Tiefstwert der nächsten 3 Tage für die Frost-Nachricht."""
        now_ts = dt_util.utcnow().timestamp()
        if not force and now_ts - self._fc_at < FORECAST_REFRESH:
            return
        self._fc_at = now_ts
        entity_id = self.weather_entity()
        if not entity_id:
            return
        try:
            response = await self.hass.services.async_call(
                "weather", "get_forecasts", {"entity_id": entity_id, "type": "daily"}, blocking=True, return_response=True
            )
        except Exception as err:  # noqa: BLE001 - Dienst ohne Tagesvorhersage
            _LOGGER.debug("Keine Tagesvorhersage von %s: %s", entity_id, err)
            return
        days = list(((response or {}).get(entity_id) or {}).get("forecast") or [])[:3]
        lows = []
        for day in days:
            low = _float(day.get("templow"))
            if low is None:
                low = _float(day.get("temperature"))
            if low is not None:
                lows.append((low, day.get("datetime")))
        if not lows:
            self.frost_low = self.frost_day = None
            return
        low, when = min(lows, key=lambda x: x[0])
        self.frost_low = low
        self.frost_day = when
        limit = float(self.settings.get("cold_snap_temp") or 0)
        if low < limit:
            day_text = ""
            moment, _ = parse_when(when) if when else (None, False)
            if moment is not None:
                day_text = " am " + ("heute" if moment.date() == dt_util.now().date() else moment.strftime("%d.%m."))
            self.notify("frost", "frost", "Frost erwartet",
                        f"Tiefstwert {_de(low)} °C{day_text} (Grenze {_de(limit)} °C)")
        else:
            self.clear("frost")

    # ------------------------------------------------------------ Für das Panel
    def outside_temp(self) -> float | None:
        entity_id = self.settings.get("outside_sensor")
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None or state.state in BAD_STATES:
            return None
        return _float(state.state)

    # ------------------------------------------------------------ Funk (Duty Cycle)
    def radio_entities(self) -> list[str]:
        """Gewählte Sensoren oder automatisch alle %-Sensoren mit „duty_cycle“ (Homematic CCU, Access Point, Router)."""
        chosen = list(self.settings.get("radio_entities") or [])
        if chosen:
            return chosen
        now = dt_util.utcnow().timestamp()
        if now - self._radio_at > 600 or not self._radio_found:
            self._radio_at = now
            self._radio_found = sorted(
                s.entity_id for s in self.hass.states.async_all("sensor")
                if "duty_cycle" in s.entity_id and s.attributes.get("unit_of_measurement") == "%"
            )
        return self._radio_found

    @callback
    def update_radio(self) -> None:
        level = None
        entity = None
        for entity_id in self.radio_entities():
            state = self.hass.states.get(entity_id)
            value = _float(state.state) if state is not None else None
            if value is not None and (level is None or value > level):
                level, entity = value, entity_id
        limit = float(self.settings.get("radio_limit") or 70)
        busy = level is not None and (level >= limit or (self.radio_busy and level >= limit - 10))
        if busy != self.radio_busy:
            name = self._name(entity) if entity else "Funk"
            self.log.add("health", "Funk ausgelastet – Befehle werden gedrosselt" if busy else "Funk wieder frei",
                         f"{name}: {_de(level)} % (Grenze {limit:.0f} %)" if level is not None else None)
        self.radio_level, self.radio_entity, self.radio_busy = level, entity, busy

    def status(self) -> dict[str, Any]:
        return {
            **{k: fn() for k, fn in self.extra_status.items()},
            "away": self.away,
            "notify": self.notify_summary(),
            "approaching": self.approaching,
            "presence_force": self.settings.get("presence_force"),
            "vacation": self.vacation,
            "vacation_events": self._cal_events,
            "vacation_calendar_error": self._cal_error,
            "free_days": self.free_days(),
            "workday_source": self.workday_source(),
            "workday_calendar_error": self._wd_error,
            "waste": self.waste()[:12],
            "waste_due": self.waste_due(),
            "waste_types": sorted({e["type"] for e in self._waste}, key=str.lower),
            "waste_error": self._waste_error,
            "guest": bool(self.settings.get("guest")),
            "outside_temp": self.outside_temp(),
            "frost_low": self.frost_low,
            "notify_queued": len(self._queued),
            "radio": {"level": self.radio_level, "entity": self.radio_entity, "busy": self.radio_busy,
                      "entities": self.radio_entities(), "limit": self.settings.get("radio_limit") or 70},
        }
