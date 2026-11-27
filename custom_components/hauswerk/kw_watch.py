"""Kraftwerk-Wächter: Auffälligkeiten im Stromverbrauch und Störungen der Anlage.

- Stromfresser: ein Gerät aus dem Energie-Dashboard („Einzelne Geräte“) braucht in den letzten 5 Tagen deutlich
  mehr als sonst (Median der 30 Tage davor), z. B. ein Kühlschrank mit vereister Dichtung.
- Grundlast gestiegen: der Verbrauch nachts (1–5 Uhr) liegt deutlich über dem der Wochen davor.
- Wechselrichter liefert bei Sonne nichts bzw. meldet sich nicht.
- Akku wird nicht mehr voll: an Tagen mit Einspeisung (also Überschuss) erreicht der Ladestand keine 95 %.
- Stromzähler sendet nicht.

Die Tageswerte kommen aus den Statistiken von Home Assistant (Energie-Dashboard), nichts wird doppelt erfasst.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from statistics import median
from typing import Any, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later, async_track_time_change, async_track_time_interval
from homeassistant.util import dt as dt_util

from .core import Haus
from .log import Protokoll

_LOGGER = logging.getLogger(__name__)

BAD = ("unavailable", "unknown", None)
SUNNY = ("sunny", "partlycloudy", "clear")


def _f(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def device_jumps(days: dict[str, list[float]], names: dict[str, str]) -> list[dict[str, Any]]:
    """Geräte, deren Verbrauch der letzten 5 Tage ≥ 30 % (und ≥ 0,15 kWh/Tag) über dem Median der Tage davor liegt."""
    out = []
    for sid, vals in days.items():
        if len(vals) < 15:
            continue
        recent, before = vals[-5:], vals[:-5]
        base = median(before)
        now = sum(recent) / len(recent)
        if base > 0.05 and now >= base * 1.3 and now - base >= 0.15:
            out.append({"id": sid, "name": names.get(sid) or sid, "now": round(now, 2), "base": round(base, 2),
                        "pct": round(100 * (now / base - 1))})
    return sorted(out, key=lambda x: -x["pct"])


def base_jump(nights: list[float]) -> dict[str, Any] | None:
    """Grundlast der letzten 5 Nächte gegen die Nächte davor (W): ≥ 25 % und ≥ 30 W mehr."""
    if len(nights) < 15:
        return None
    now, base = median(nights[-5:]), median(nights[:-5])
    if base > 20 and now >= base * 1.25 and now - base >= 30:
        return {"now": round(now), "base": round(base)}
    return None


def battery_not_full(days: list[tuple[float | None, float]]) -> dict[str, Any] | None:
    """(höchster Ladestand, Einspeisung kWh) je Tag: an ≥ 3 Tagen mit ≥ 1,5 kWh Einspeisung nie ≥ 95 %."""
    full = [soc for soc, exp in days if exp >= 1.5 and soc is not None]
    if len(full) >= 3 and max(full) < 95:
        return {"max": round(max(full)), "days": len(full)}
    return None


class KwWatch:
    """Prüft täglich (Statistiken) und alle 5 Min. (Live-Werte) und meldet Auffälliges (Anlass „Kraftwerk“)."""

    def __init__(self, hass: HomeAssistant, log: Protokoll, haus: Haus, settings: Callable[[], dict]) -> None:
        self.hass = hass
        self.log = log
        self.haus = haus
        self._settings = settings
        self._unsubs: list = []
        self.daily: list[dict[str, Any]] = []
        self.live: list[dict[str, Any]] = []
        self._since: dict[str, float] = {}
        self.checked: str | None = None

    def async_setup(self) -> None:
        self._unsubs.append(async_track_time_interval(self.hass, self._async_live, timedelta(minutes=5)))
        self._unsubs.append(async_track_time_change(self.hass, self._async_daily, hour=7, minute=40, second=0))
        self._unsubs.append(async_call_later(self.hass, 180, self._async_daily))

    def async_stop(self) -> None:
        for u in self._unsubs:
            u()
        self._unsubs.clear()

    def status(self) -> dict[str, Any]:
        return {"findings": self.daily + self.live, "checked": self.checked}

    # ------------------------------------------------------------ Melden
    def _sync(self, prefix: str, items: list[dict[str, Any]]) -> None:
        keys = {i["key"] for i in items}
        for f in (self.daily if prefix == "d" else self.live):
            if f["key"] not in keys:
                self.haus.clear(f["key"])
        for i in items:
            self.haus.notify(i["key"], "power", i["title"], i["text"], actions=[{"title": "Gesehen", "do": "ack"}])
        old = {f["key"] for f in (self.daily if prefix == "d" else self.live)}
        for i in items:
            if i["key"] not in old:
                self.log.add("health", i["title"], i["text"], module="kraftwerk")
        if prefix == "d":
            self.daily = items
        else:
            self.live = items

    # ------------------------------------------------------------ Live: Wechselrichter, Zähler
    def _watts(self, eid: str | None) -> float | None:
        st = self.hass.states.get(eid) if eid else None
        if st is None or st.state in BAD:
            return None
        v = _f(st.state)
        if v is None:
            return None
        unit = str(st.attributes.get("unit_of_measurement") or "W")
        return v * 1000 if unit.lower() == "kw" else v

    def _long(self, key: str, cond: bool, now: float, minutes: float) -> bool:
        if not cond:
            self._since.pop(key, None)
            return False
        self._since.setdefault(key, now)
        return now - self._since[key] >= minutes * 60

    async def _async_live(self, _now=None) -> None:
        p = self._settings()
        now = dt_util.utcnow().timestamp()
        items: list[dict[str, Any]] = []
        sun = self.hass.states.get(self.haus.settings.get("sun_entity") or "sun.sun")
        elev = _f(sun.attributes.get("elevation")) if sun is not None else None
        weather = self.hass.states.get(self.haus.weather_entity() or "")
        solar = [e for e in p.get("kw_solar") or [] if e]
        if solar and elev is not None and elev >= 5:
            vals = [self._watts(e) for e in solar]
            if self._long("solar_off", all(v is None for v in vals), now, 30):
                items.append({"key": "kw_solar_off", "icon": "mdi:solar-panel-large", "level": "warn", "title": "Wechselrichter meldet sich nicht",
                              "text": f"{', '.join(self._name(e) for e in solar)} seit über 30 Min. nicht erreichbar – WLAN bzw. Strom des Wechselrichters prüfen."})
            sunny = weather is not None and weather.state in SUNNY and elev >= 15
            total = sum(v for v in vals if v is not None)
            if self._long("solar_zero", sunny and any(v is not None for v in vals) and total < 20, now, 30):
                items.append({"key": "kw_solar_zero", "icon": "mdi:solar-power-variant-outline", "level": "warn", "title": "Solar liefert nichts – trotz Sonne",
                              "text": f"Seit über 30 Min. {round(total)} W bei Sonne ({round(elev)}° hoch, {weather.state if weather else ''}). "
                                      "Störung am Wechselrichter, Sicherung oder Abschaltung prüfen."})
        else:
            self._since.pop("solar_off", None)
            self._since.pop("solar_zero", None)
        grid = p.get("kw_grid")
        if grid:
            st = self.hass.states.get(grid)
            when = (getattr(st, "last_reported", None) or getattr(st, "last_updated", None) or getattr(st, "last_changed", None)) if st is not None else None
            seen = when.timestamp() if when is not None else None
            stale = st is None or st.state in BAD or (seen is not None and now - seen > 30 * 60)
            if self._long("meter", stale, now, 15):
                items.append({"key": "kw_meter", "icon": "mdi:meter-electric-outline", "level": "warn", "title": "Stromzähler sendet nicht",
                              "text": f"{self._name(grid)} meldet seit über 30 Min. keinen neuen Wert – Lesekopf, WLAN bzw. Batterie prüfen."})
        self._sync("l", items)

    def _name(self, eid: str) -> str:
        st = self.hass.states.get(eid)
        return (st.name if st is not None else None) or eid

    # ------------------------------------------------------------ Täglich: Stromfresser, Grundlast, Akku
    async def _async_daily(self, _now=None) -> None:
        try:
            items = await self._daily_items()
        except Exception as err:  # noqa: BLE001 - Statistik nicht lesbar
            _LOGGER.debug("Kraftwerk-Wächter: %s", err)
            return
        self.checked = dt_util.utcnow().isoformat()
        self._sync("d", items)

    async def _stats(self, ids: set[str], start, period: str, types: set[str]) -> dict[str, list[dict]]:
        from homeassistant.components.recorder import get_instance  # noqa: PLC0415
        from homeassistant.components.recorder.statistics import statistics_during_period  # noqa: PLC0415
        end = dt_util.start_of_local_day()
        return await get_instance(self.hass).async_add_executor_job(
            statistics_during_period, self.hass, start, end, ids, period, None, types)

    async def _daily_items(self) -> list[dict[str, Any]]:
        from homeassistant.components.energy.data import async_get_manager  # noqa: PLC0415
        prefs = (await async_get_manager(self.hass)).data or {}
        items: list[dict[str, Any]] = []
        start = dt_util.start_of_local_day() - timedelta(days=35)
        # Stromfresser
        devs = {d["stat_consumption"]: d.get("name") or self._name(d["stat_consumption"])
                for d in prefs.get("device_consumption") or [] if d.get("stat_consumption")}
        if devs:
            st = await self._stats(set(devs), start, "day", {"change"})
            days = {sid: [max(0.0, r.get("change") or 0) for r in st.get(sid) or []] for sid in devs}
            for j in device_jumps(days, devs)[:3]:
                items.append({"key": f"kw_dev:{j['id']}", "icon": "mdi:trending-up", "level": "warn",
                              "title": f"{j['name']} braucht mehr Strom",
                              "text": f"Seit 5 Tagen im Schnitt {str(j['now']).replace('.', ',')} kWh am Tag statt {str(j['base']).replace('.', ',')} kWh "
                                      f"(+{j['pct']} %). Läuft es öfter oder länger als sonst? Beim Kühlschrank: Dichtung, Eis, Lüftungsgitter prüfen."})
        # Grundlast nachts: Bezug + Solar − Einspeisung + Akku entladen − laden, 1–5 Uhr
        groups: dict[str, list[str]] = {"imp": [], "exp": [], "solar": [], "bin": [], "bout": []}
        for s in prefs.get("energy_sources") or []:
            if s.get("type") == "grid":
                groups["imp"] += [f["stat_energy_from"] for f in s.get("flow_from") or [] if f.get("stat_energy_from")]
                groups["exp"] += [f["stat_energy_to"] for f in s.get("flow_to") or [] if f.get("stat_energy_to")]
            elif s.get("type") == "solar" and s.get("stat_energy_from"):
                groups["solar"].append(s["stat_energy_from"])
            elif s.get("type") == "battery":
                if s.get("stat_energy_from"):
                    groups["bout"].append(s["stat_energy_from"])
                if s.get("stat_energy_to"):
                    groups["bin"].append(s["stat_energy_to"])
        ids = {i for v in groups.values() for i in v}
        if groups["imp"]:
            st = await self._stats(ids, start, "hour", {"change"})
            night: dict[str, float] = {}
            hours: dict[str, int] = {}
            sign = {"imp": 1, "solar": 1, "bout": 1, "exp": -1, "bin": -1}
            for g, lst in groups.items():
                for sid in lst:
                    for r in st.get(sid) or []:
                        t = r.get("start")
                        t = dt_util.utc_from_timestamp(t) if isinstance(t, (int, float)) else t
                        loc = dt_util.as_local(t)
                        if 1 <= loc.hour < 5:
                            d = loc.date().isoformat()
                            night[d] = night.get(d, 0.0) + sign[g] * max(0.0, r.get("change") or 0)
                            if g == "imp":
                                hours[d] = hours.get(d, 0) + 1
            nights = [night[d] / hours[d] * 1000 for d in sorted(night) if hours.get(d, 0) >= 3 and night[d] > 0]
            j = base_jump(nights)
            if j:
                items.append({"key": "kw_base", "icon": "mdi:power-sleep", "level": "warn", "title": "Grundlast gestiegen",
                              "text": f"Nachts jetzt ca. {j['now']} W statt {j['base']} W (+{j['now'] - j['base']} W, ca. "
                                      f"{round((j['now'] - j['base']) * 8.76)} kWh im Jahr). Neues Gerät, das dauernd läuft, oder ein Gerät, das nicht mehr abschaltet?"})
        # Akku wird nicht mehr voll
        soc = self._settings().get("kw_battery_soc")
        if soc and groups["exp"]:
            st = await self._stats({soc, *groups["exp"]}, dt_util.start_of_local_day() - timedelta(days=10), "day", {"max", "change"})

            def day(r):
                t = r.get("start")
                t = dt_util.utc_from_timestamp(t) if isinstance(t, (int, float)) else t
                return dt_util.as_local(t).date().isoformat()
            mx = {day(r): _f(r.get("max")) for r in st.get(soc) or []}
            ex: dict[str, float] = {}
            for sid in groups["exp"]:
                for r in st.get(sid) or []:
                    ex[day(r)] = ex.get(day(r), 0.0) + max(0.0, r.get("change") or 0)
            j = battery_not_full([(mx.get(d), ex.get(d, 0.0)) for d in sorted(set(mx) | set(ex))])
            if j:
                items.append({"key": "kw_batt_full", "icon": "mdi:battery-alert-variant-outline", "level": "warn", "title": "Akku wird nicht mehr voll",
                              "text": f"An {j['days']} Tagen mit Einspeisung höchstens {j['max']} % geladen. Ladegrenze in der App des Speichers prüfen – "
                                      "oder der Akku altert (Kapazität sinkt)."})
        return items
