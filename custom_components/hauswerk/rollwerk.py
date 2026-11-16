"""Hauswerk-Modul Rollwerk: Rollläden nach Sonne, Uhrzeit, Hitze und Sturm.

Rollwerk fährt nur bei einem Wechsel (morgens auf, abends zu, Sonnenschutz an/aus, Sturm). Wer einen
Rollladen von Hand verstellt, behält seine Stellung bis zum nächsten Wechsel. Sturm fährt die gewählten
Rollläden hoch; ist eine zugeordnete Tür offen, fährt ihr Rollladen nicht herunter (Aussperrschutz).
Sonnenstand, Wetter, Sturmgrenze, Anwesenheit, Urlaub und Feiertage kommen aus dem Hauswerk-Kern.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
import random
from typing import Any

from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import SHUTTER_STORAGE_KEY, WINDOW_OPEN_STATES
from .core import Haus
from .log import Protokoll, log_settings
from .logic import cover_target, day_window, facade_sun

_LOGGER = logging.getLogger(__name__)

BAD = {"unavailable", "unknown", None}
STORM_RELEASE = 15 * 60  # Sekunden unter 80 % der Sturmgrenze, bis Sturmschutz endet

RW_DEFAULTS: dict[str, Any] = {
    "rw_covers": [],               # Rollläden, die Rollwerk fährt
    "rw_open_mode": "sun",         # sun = Sonnenaufgang | time = feste Uhrzeit | off = morgens nicht öffnen
    "rw_open_offset": 0,           # Minuten nach Sonnenaufgang
    "rw_open_not_before": "06:30", # Werktag frühestens
    "rw_open_not_before_we": "08:00",  # Wochenende/Feiertag frühestens
    "rw_open_time": "07:00",
    "rw_open_time_we": "08:30",
    "rw_close_mode": "sun",        # sun = Sonnenuntergang | time = feste Uhrzeit | off = abends nicht schließen
    "rw_close_offset": 15,         # Minuten nach Sonnenuntergang
    "rw_close_not_after": "22:30", # spätestens
    "rw_close_time": "21:00",
    "rw_shade": False,             # Sonnenschutz (Hitze)
    "rw_shade_temp": 24.0,         # ab dieser Außentemperatur
    "rw_shade_pos": 30,            # Stellung in % (0 = zu)
    "rw_shade_elev": 15,           # Sonne mindestens so hoch (°)
    "rw_storm": True,              # Sturmschutz: hochfahren ab Sturmgrenze (Hauswerk › Wetter)
    "rw_wind_entity": None,        # Böen-Sensor (leer = Wetterdienst)
    "rw_vacation_random": False,   # im Urlaub Zeiten zufällig ±15 Min. (bewohnt wirken)
}
RW_KEYS = frozenset(RW_DEFAULTS)


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class Rollwerk:
    """Modul Rollwerk: Einstellungen, Rollladen-Konfiguration und Steuerung."""

    def __init__(self, hass: HomeAssistant, log: Protokoll, haus: Haus) -> None:
        self.hass = hass
        self.log = log
        self.haus = haus
        self._store: Store = Store(hass, 1, SHUTTER_STORAGE_KEY)
        self.settings: dict[str, Any] = dict(RW_DEFAULTS)
        # je Rollladen: facade, shade, shade_pos, storm, door, auto, night_pos
        self.covers: dict[str, dict[str, Any]] = {}
        self._rt: dict[str, dict[str, Any]] = {}
        self._own: dict[str, float] = {}
        self._storm = False
        self._storm_low_since: float | None = None
        self._gust: float | None = None
        self._window: dict[str, Any] = {}
        self._unsubs: list[Callable[[], None]] = []
        self._subscribers: set[Callable[[dict], None]] = set()

    # ------------------------------------------------------------ Speicher
    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        self.settings.update({k: v for k, v in (stored.get("settings") or {}).items() if k in RW_KEYS})
        self.covers = stored.get("covers") or {}

    def _save(self) -> None:
        self._store.async_delay_save(lambda: {"settings": self.settings, "covers": self.covers}, 2)

    async def async_start(self) -> None:
        self._unsubs.append(async_track_time_interval(self.hass, self._async_tick, timedelta(minutes=1)))
        self._unsubs.append(self.haus.subscribe(self._on_house))
        await self.async_evaluate(initial=True)

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self._store.async_save({"settings": self.settings, "covers": self.covers})

    @callback
    def _on_house(self) -> None:
        self.hass.async_create_task(self.async_evaluate())

    async def _async_tick(self, _now=None) -> None:
        await self.async_evaluate()

    @callback
    def subscribe(self, cb: Callable[[dict], None]) -> Callable[[], None]:
        self._subscribers.add(cb)

        @callback
        def unsub() -> None:
            self._subscribers.discard(cb)

        return unsub

    # ------------------------------------------------------------ Änderungen
    async def async_save_settings(self, settings: dict[str, Any], by: str | None = None) -> None:
        settings = {k: v for k, v in settings.items() if k in RW_KEYS}
        changed = [k for k, v in settings.items() if self.settings.get(k) != v]
        if not changed:
            return
        log_settings(self.log, settings, changed, by)
        self.settings.update(settings)
        self._save()
        await self.async_evaluate()

    async def async_save_cover(self, entity_id: str, cfg: dict[str, Any], by: str | None = None) -> None:
        self.covers[entity_id] = cfg
        self._save()
        self.log.add("settings", f"Rollladen {self._name(entity_id)} geändert", f"Panel{f' · von {by}' if by else ''}")
        await self.async_evaluate()

    async def async_command(self, entity_ids: list[str], action: str, position: int | None = None, by: str | None = None) -> None:
        """Von Hand aus dem Panel: hoch, runter, stopp oder Stellung."""
        for entity_id in entity_ids:
            if action == "stop":
                await self._call("cover", "stop_cover", {"entity_id": entity_id})
            elif action == "position" and position is not None:
                await self._move(entity_id, int(position), own=False)
            else:
                await self._move(entity_id, 100 if action == "open" else 0, own=False)
        names = ", ".join(self._name(e) for e in entity_ids[:4]) + (" …" if len(entity_ids) > 4 else "")
        what = {"open": "hoch", "close": "runter", "stop": "Stopp"}.get(action, f"auf {position} %")
        self.log.add("manual", f"Rollladen {what}", f"{names} · im Panel{f' · von {by}' if by else ''}")

    # ------------------------------------------------------------ Helfer
    def _name(self, entity_id: str) -> str:
        state = self.hass.states.get(entity_id)
        return state.name if state is not None else entity_id

    def _area(self, entity_id: str) -> str | None:
        try:
            entry = er.async_get(self.hass).async_get(entity_id)
            if entry is None:
                return None
            area_id = entry.area_id
            if not area_id and entry.device_id:
                device = dr.async_get(self.hass).async_get(entry.device_id)
                area_id = getattr(device, "area_id", None)
            area = ar.async_get(self.hass).async_get_area(area_id) if area_id else None
            return area.name if area else None
        except Exception:  # noqa: BLE001
            return None

    async def _call(self, domain: str, service: str, data: dict[str, Any]) -> None:
        ctx = Context()
        self._own[ctx.id] = dt_util.utcnow().timestamp()
        await self.hass.services.async_call(domain, service, data, context=ctx)

    async def _move(self, entity_id: str, position: int, own: bool = True) -> None:
        state = self.hass.states.get(entity_id)
        features = int((state.attributes.get("supported_features") if state else 0) or 0)
        if features & 4:  # Stellung anfahrbar
            await self._call("cover", "set_cover_position", {"entity_id": entity_id, "position": position})
        else:
            await self._call("cover", "open_cover" if position >= 50 else "close_cover", {"entity_id": entity_id})

    def _sun(self) -> tuple[float | None, float | None]:
        state = self.hass.states.get(self.haus.settings.get("sun_entity") or "sun.sun")
        if state is None:
            return None, None
        return _float(state.attributes.get("azimuth")), _float(state.attributes.get("elevation"))

    def _sun_minutes(self) -> tuple[int | None, int | None]:
        """Sonnenauf- und -untergang heute als Tagesminuten (lokal)."""
        try:
            from homeassistant.helpers.sun import get_astral_event_date

            today = dt_util.now().date()
            out = []
            for event in ("sunrise", "sunset"):
                when = get_astral_event_date(self.hass, event, today)
                if when is None:
                    out.append(None)
                    continue
                local = dt_util.as_local(when)
                out.append(local.hour * 60 + local.minute)
            return out[0], out[1]
        except Exception:  # noqa: BLE001 - ohne Standort: feste Zeiten
            return None, None

    def _wind(self) -> float | None:
        """Aktuelle Böen in km/h: eigener Sensor, sonst Wetterdienst (Böen, sonst Wind)."""
        entity_id = self.settings.get("rw_wind_entity")
        if entity_id:
            state = self.hass.states.get(entity_id)
            value = _float(state.state) if state is not None else None
            unit = (state.attributes.get("unit_of_measurement") or "km/h") if state is not None else "km/h"
        else:
            weather = self.haus.weather_entity()
            state = self.hass.states.get(weather) if weather else None
            if state is None:
                return None
            attrs = state.attributes
            value = _float(attrs.get("wind_gust_speed"))
            if value is None:
                value = _float(attrs.get("wind_speed"))
            unit = attrs.get("wind_speed_unit") or "km/h"
        if value is None:
            return None
        return round(value * 3.6, 1) if unit == "m/s" else round(value * 1.609, 1) if unit == "mph" else value

    def _free_day(self) -> bool:
        now = dt_util.now()
        if now.weekday() >= 5:
            return True
        workday = self.hass.states.get(self.haus.settings.get("workday_entity") or "")
        return workday is not None and workday.state == "off"

    def _door_open(self, cfg: dict) -> bool:
        door = cfg.get("door")
        state = self.hass.states.get(door) if door else None
        return state is not None and str(state.state).lower() in WINDOW_OPEN_STATES

    # ------------------------------------------------------------ Steuerung
    async def async_evaluate(self, initial: bool = False) -> None:
        now = dt_util.utcnow().timestamp()
        local = dt_util.now()
        now_min = local.hour * 60 + local.minute
        sunrise, sunset = self._sun_minutes()
        free = self._free_day()
        jitter = 0
        if self.settings.get("rw_vacation_random") and self.haus.vacation:
            jitter = random.Random(local.date().toordinal()).randint(-15, 15)
        open_at, close_at = day_window(sunrise, sunset, self.settings, free, jitter)
        azimuth, elevation = self._sun()
        outside, _rh = self.haus.outside_air()
        # Sturm: ab der Grenze aus Hauswerk › Wetter, Ende erst nach 15 Min. unter 80 %
        gust = self._wind()
        limit = float(self.haus.settings.get("storm_kmh") or 70)
        storm_before = self._storm
        if self.settings.get("rw_storm", True) and gust is not None and gust >= limit:
            self._storm, self._storm_low_since = True, None
        elif self._storm and (gust is None or gust < limit * 0.8):
            self._storm_low_since = self._storm_low_since or now
            if now - self._storm_low_since >= STORM_RELEASE:
                self._storm = False
        elif not self.settings.get("rw_storm", True):
            self._storm = False
        if self._storm != storm_before:
            self.log.add("season", "Sturmschutz: Rollläden hoch" if self._storm else "Sturmschutz beendet",
                         f"Böen {gust:.0f} km/h · Grenze {limit:.0f} km/h" if gust is not None else None)
        self._gust = gust
        self._window = {"open_at": open_at, "close_at": close_at, "sunrise": sunrise, "sunset": sunset,
                        "free_day": free, "jitter": jitter}
        for entity_id in self.settings.get("rw_covers") or []:
            state = self.hass.states.get(entity_id)
            cfg = self.covers.get(entity_id) or {}
            rt = self._rt.setdefault(entity_id, {})
            if state is None or state.state in BAD:
                rt["unavailable"] = True
                continue
            rt["unavailable"] = False
            on_facade = facade_sun(azimuth, elevation, cfg.get("facade"), float(self.settings.get("rw_shade_elev") or 15))
            target, reason, shading = cover_target(now_min, open_at, close_at, self.settings, cfg, sun_on_facade=on_facade,
                                                   outside=outside, storm=self._storm, was_shading=bool(rt.get("shading")))
            rt.update(target=target, reason=reason, shading=shading)
            position = _float(state.attributes.get("current_position"))
            if position is None:
                position = 100.0 if state.state == "open" else 0.0 if state.state == "closed" else None
            if initial and "sent" not in rt:
                rt["sent"] = target  # nach dem Start nichts fahren, erst beim nächsten Wechsel
                continue
            if target is None or target == rt.get("sent"):
                rt["blocked"] = None
                continue
            # Aussperrschutz: bei offener Tür nicht herunterfahren
            if self._door_open(cfg) and position is not None and target < position:
                if not rt.get("blocked"):
                    self.log.add("manual", f"{self._name(entity_id)} bleibt oben – Tür offen",
                                 f"{reason} wartet, bis {self._name(cfg['door'])} zu ist")
                rt["blocked"] = "Tür offen"
                continue
            rt["blocked"] = None
            rt["sent"] = target
            rt["sent_at"] = now
            if position is not None and abs(position - target) < 2:
                continue
            await self._move(entity_id, target)
            self.log.add("command", f"{self._name(entity_id)} → {'auf' if target >= 100 else 'zu' if target == 0 else f'{target} %'}",
                         reason)
        status = self.status()
        for cb in list(self._subscribers):
            cb(status)

    # ------------------------------------------------------------ Fürs Panel
    def status(self) -> dict[str, Any]:
        def hm(minutes: int | None) -> str | None:
            return None if minutes is None else f"{minutes // 60:02d}:{minutes % 60:02d}"

        azimuth, elevation = self._sun()
        covers = {}
        for entity_id in self.settings.get("rw_covers") or []:
            rt = self._rt.get(entity_id) or {}
            state = self.hass.states.get(entity_id)
            position = _float(state.attributes.get("current_position")) if state is not None else None
            sent = rt.get("sent")
            covers[entity_id] = {
                "area": self._area(entity_id),
                "target": rt.get("target"),
                "reason": rt.get("reason"),
                "shading": rt.get("shading", False),
                "blocked": rt.get("blocked"),
                "door_open": self._door_open(self.covers.get(entity_id) or {}),
                "manual": sent is not None and position is not None and state is not None
                and state.state not in ("opening", "closing") and abs(position - sent) > 5,
            }
        w = self._window
        return {
            "covers": covers,
            "open_at": hm(w.get("open_at")), "close_at": hm(w.get("close_at")),
            "sunrise": hm(w.get("sunrise")), "sunset": hm(w.get("sunset")),
            "free_day": w.get("free_day"), "jitter": w.get("jitter"),
            "sun": {"azimuth": azimuth, "elevation": elevation},
            "gust": self._gust, "storm": self._storm,
            "storm_kmh": self.haus.settings.get("storm_kmh") or 70,
        }
