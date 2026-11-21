"""Modul Beetwerk: Garten – Mähroboter und Bewässerung.

Beetwerk kennt den Mähroboter (lawn_mower.*) und die Bewässerung (Ventil, Bodenfeuchte, „gießen nötig“,
„gießt gerade“, z. B. aus Smart Irrigation). Bedient wird direkt über Home Assistant; Beetwerk selbst
- macht eine Mähpause bei Regen, nassem Boden, Frost und während bzw. kurz nach dem Bewässern
  (fährt den Mäher in die Station) und startet ihn danach wieder, wenn es die Pause selbst ausgelöst hat,
- meldet Fehler („braucht Hilfe“) und Wartung (Messer wechseln).
Gewählte Entitäten stehen in den Einstellungen (bw_…); leer = automatisch gefunden.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import GARDEN_STORAGE_KEY
from .core import Haus
from .log import Protokoll, log_settings

_LOGGER = logging.getLogger(__name__)

BW_DEFAULTS: dict[str, Any] = {
    "bw_mower": None,        # Mähroboter (lawn_mower.*), leer = erster gefundener
    "bw_soil": None,         # Bodenfeuchte (%), leer = automatisch
    "bw_watering": None,     # „gießt gerade“ (binary_sensor), leer = automatisch
    "bw_need": None,         # „gießen nötig“ (binary_sensor), leer = automatisch
    "bw_valve": None,        # Ventil der Bewässerung (valve.* oder switch.*), leer = automatisch
    "bw_pause": ["rain", "soil", "frost", "water"],  # Mähpause bei …
    "bw_soil_wet": 85,       # Boden zu nass ab … %
    "bw_frost": 3,           # Frost: Außentemperatur unter … °C
    "bw_water_after": 60,    # nach dem Bewässern … Min. nicht mähen
    "bw_resume": True,       # nach der Pause selbst wieder starten (nur wenn Beetwerk pausiert hat)
    "bw_resume_wait": 60,    # … Min. nach Ende des Grundes
    "bw_resume_until": "19:00",  # danach nicht mehr starten
    "bw_blades_days": 60,    # Hinweis „Messer wechseln“ ab … Tagen
    # Bewässerung mit Smart Irrigation: Zonen (Dauer-Sensor) und je Zone das echte Ventil
    "bw_zones": [],          # [{"zone": "sensor.smart_irrigation_rasen_1", "valves": ["valve.…", "switch.…"], "auto": True}] – Ventile nacheinander
    "bw_water_auto": False,  # Beetwerk gießt selbst (statt eigener Automationen)
    "bw_water_time": "05:00",  # Startzeit
    "bw_water_skip": True,   # nicht gießen, wenn es regnet oder in den nächsten 6 Std. Regen kommt
    # Garten frei: Kamera meldet Person/Haustier -> Mäher in die Station, nach … Min. ohne Meldung weiter
    "bw_guard": True,
    "bw_guard_sensors": [],  # leer = automatisch (Person/Haustier-Sensoren im Garten, z. B. Kamera)
    "bw_guard_wait": 30,
    "bw_camera": None,       # Kamera für das Bild in der Nachricht, leer = automatisch
    # Igelschutz: nie zwischen Sonnenuntergang und Sonnenaufgang mähen (… Min. Puffer)
    "bw_night": True,
    "bw_night_margin": 0,
    # Hitze: ab … °C draußen pausieren
    "bw_heat": True,
    "bw_heat_temp": 30,
    "bw_season": True,       # Hinweise Winterpause / Saison starten
    # Wächter: Mäher außerhalb der Station ohne Verbindung, steht im Garten, nachts nicht zu Hause
    "bw_watch": True,
    "bw_watch_min": 20,
    "bw_battery_min": 70,    # Hinweis „Akku altert“ unter … % der Kapazität im Neuzustand
}
BW_KEYS = frozenset(BW_DEFAULTS)
RAINY = ("rainy", "pouring", "snowy", "snowy-rainy", "hail", "lightning-rainy")
BAD = ("unavailable", "unknown", None)
PAUSE_TEXT = {"rain": "es regnet", "soil": "Boden zu nass", "frost": "Frost", "water": "Bewässerung",
              "guard": "jemand im Garten", "busy": "Garten belegt", "night": "Igelschutz – es ist dunkel", "heat": "Hitze"}
WEATHER_REASONS = ("rain", "soil", "frost", "water", "heat")
UNSAFE = ("mowing", "paused", "returning", "error")
DAY_KEYS = ("mo", "tu", "we", "th", "fr", "sa", "su")


def _num(state) -> float | None:
    try:
        return float(state.state) if state is not None and state.state not in BAD else None
    except (TypeError, ValueError):
        return None


class Beetwerk:
    """Garten: Mähroboter und Bewässerung."""

    def __init__(self, hass: HomeAssistant, log: Protokoll, haus: Haus) -> None:
        self.hass = hass
        self.log = log
        self.haus = haus
        self._store: Store = Store(hass, 1, GARDEN_STORAGE_KEY)
        self.settings: dict[str, Any] = dict(BW_DEFAULTS)
        self._persist: dict[str, Any] = {}
        self._unsubs: list = []
        self._dev: tuple[float, dict] | None = None
        self._water_end: float | None = None
        self._was_watering = False
        self._calm_since: float | None = None
        self._stop_timer = None
        haus.extra_status["beetwerk"] = self.status

    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        self.settings.update({k: v for k, v in (stored.get("settings") or {}).items() if k in BW_KEYS})
        self._persist = stored.get("persist") or {}

    async def async_start(self) -> None:
        self._unsubs.append(async_track_time_interval(self.hass, self._async_tick, timedelta(minutes=1)))
        # nach einem Neustart: laufende Bewässerung zu Ende führen bzw. Ventil schließen
        await self._async_water_step()

    async def async_stop(self) -> None:
        if self._stop_timer:
            self._stop_timer()
            self._stop_timer = None
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self._store.async_save(self._data())

    def _save(self) -> None:
        self._store.async_delay_save(self._data, 5)

    def _data(self) -> dict[str, Any]:
        return {"settings": self.settings, "persist": self._persist}

    async def async_save_settings(self, settings: dict[str, Any], by: str | None = None) -> None:
        settings = {k: v for k, v in settings.items() if k in BW_KEYS}
        changed = [k for k, v in settings.items() if self.settings.get(k) != v]
        if not changed:
            return
        log_settings(self.log, settings, changed, by, module="beetwerk", old=self.settings)
        self.settings.update(settings)
        self._dev = None
        self._save()

    # ------------------------------------------------------------ Entitäten
    def _ids(self, domain: str) -> list[str]:
        ids = getattr(self.hass.states, "async_entity_ids", None)
        return sorted(ids(domain)) if ids else []

    def _name(self, entity_id: str | None) -> str:
        st = self.hass.states.get(entity_id) if entity_id else None
        return (st.name if st is not None and getattr(st, "name", None) else None) or (entity_id or "–")

    def mower(self) -> str | None:
        return self.settings.get("bw_mower") or next(iter(self._ids("lawn_mower")), None)

    def _find(self, domain: str, words: tuple[str, ...], device_class: str | None = None) -> str | None:
        """Erste Entität der Domäne, deren ID oder Name eines der Wörter enthält (bzw. mit passender Geräteklasse)."""
        best = None
        for eid in self._ids(domain):
            st = self.hass.states.get(eid)
            hay = f"{eid} {getattr(st, 'name', '') or ''}".lower()
            dc = (st.attributes.get("device_class") if st is not None else None)
            if any(w in hay for w in words) and (device_class is None or dc in (device_class, None)):
                if "rasen" in hay or "garten" in hay:
                    return eid
                best = best or eid
        return best

    def entities(self) -> dict[str, str | None]:
        """Alle Entitäten des Gartens: gewählt oder automatisch gefunden."""
        s = self.settings
        dev = self._mower_device()
        return {
            "mower": self.mower(),
            "soil": s.get("bw_soil") or self._find("sensor", ("bodenfeuchte", "soil_moisture", "soil moisture", "moisture"), "moisture"),
            "watering": s.get("bw_watering") or self._find("binary_sensor", ("watering_now", "gießt", "giesst", "bewässerung_aktiv")),
            "need": s.get("bw_need") or self._find("binary_sensor", ("irrigation_needed", "gießen_nötig", "bewasserung_notig")),
            "valve": s.get("bw_valve") or self._find("valve", ("irrigation", "bewässer", "bewasser", "rasen", "garten", "ventil"))
            or self._find("switch", ("bewässerung", "bewasserung", "irrigation", "gartenventil")),
            "bucket": self._find("sensor", ("irrigation_rasen_1_bucket", "_bucket")),
            **dev,
        }

    def _mower_device(self) -> dict[str, str | None]:
        """Weitere Entitäten am Gerät des Mähers: Akku, Fehler, Messer, Stunden, Winterpause, Feierabend (alle 10 Min. neu gesucht)."""
        now = dt_util.utcnow().timestamp()
        if self._dev is not None and now - self._dev[0] < 600:
            return self._dev[1]
        found: dict[str, Any] = {"battery": None, "error": None, "blades_days": None, "hours": None, "winter": None,
                                 "eod": None, "status": None, "blade_rpm": None, "blades_quality": None, "capacity": None,
                                 "wire": None, "wlan": None, "humidity": None, "duration": None, "next_start": None,
                                 "auto": None, "timers": []}
        mower = self.mower()
        try:
            reg = er.async_get(self.hass)
            entry = reg.async_get(mower) if mower else None
            ents = er.async_entries_for_device(reg, entry.device_id) if entry is not None and getattr(entry, "device_id", None) else []
        except Exception:  # noqa: BLE001 - ohne Register (z. B. Tests) nur die Hauptentität
            ents = []
        for e in ents:
            if getattr(e, "disabled_by", None) is not None:
                continue
            eid = e.entity_id
            dc = getattr(e, "device_class", None) or getattr(e, "original_device_class", None)
            if e.domain == "sensor" and (dc == "battery" or eid.endswith(("_battery_charge", "_batterie", "_battery"))):
                if not found["battery"] or eid.endswith("_charge"):
                    found["battery"] = eid
            elif e.domain == "sensor" and eid.endswith(("_error_message", "_fehlermeldung")):
                found["error"] = eid
            elif e.domain == "sensor" and ("blades_days" in eid or "messer_tage" in eid):
                found["blades_days"] = eid
            elif e.domain == "sensor" and ("statistic_hours" in eid or "betriebsstunden" in eid):
                found["hours"] = eid
            elif e.domain == "switch" and "winter" in eid:
                found["winter"] = eid
            elif e.domain == "button" and eid.endswith(("_eod", "_feierabend")):
                found["eod"] = eid
            elif e.domain == "sensor" and eid.endswith(("_status_plain", "_substatus_plain")) and not found["status"]:
                found["status"] = eid
            elif e.domain == "sensor" and eid.endswith("_motor_blade"):
                found["blade_rpm"] = eid
            elif e.domain == "sensor" and eid.endswith("_blades_quality"):
                found["blades_quality"] = eid
            elif e.domain == "sensor" and eid.endswith("_battery_capacity"):
                found["capacity"] = eid
            elif e.domain == "sensor" and eid.endswith("_wire"):
                found["wire"] = eid
            elif e.domain == "sensor" and eid.endswith(("_wlan_rssi", "_wifi_signal")):
                found["wlan"] = eid
            elif e.domain == "sensor" and eid.endswith("_climate_humidity"):
                found["humidity"] = eid
            elif e.domain == "sensor" and eid.endswith("_status_duration"):
                found["duration"] = eid
            elif e.domain == "sensor" and eid.endswith("_timer_next_unix"):
                found["next_start"] = eid
            elif e.domain == "button" and eid.endswith("_auto"):
                found["auto"] = eid
            elif e.domain == "switch" and "_timer_" in eid:
                found["timers"].append(eid)
        found["timers"].sort(key=lambda x: int(x.rsplit("_", 1)[-1]) if x.rsplit("_", 1)[-1].isdigit() else 99)
        self._dev = (now, found)
        return found

    # ------------------------------------------------------------ Regeln
    def _reasons(self, ent: dict, now: float) -> list[str]:
        """Gründe für eine Mähpause gerade jetzt."""
        on = set(self.settings.get("bw_pause") or [])
        out: list[str] = []
        weather = self.hass.states.get(self.haus.weather_entity() or "")
        if "rain" in on and weather is not None and weather.state in RAINY:
            out.append("rain")
        soil = _num(self.hass.states.get(ent["soil"])) if ent.get("soil") else None
        if "soil" in on and soil is not None and soil >= float(self.settings.get("bw_soil_wet") or 85):
            out.append("soil")
        out_temp, _rh = self.haus.outside_air()
        if "frost" in on and out_temp is not None and out_temp < float(self.settings.get("bw_frost") or 3):
            out.append("frost")
        watering = self._watering(ent)
        if watering:
            self._was_watering = True
        elif self._was_watering:
            self._was_watering = False
            self._water_end = now
        after = float(self.settings.get("bw_water_after") or 0) * 60
        if "water" in on and (watering or (self._water_end and now - self._water_end < after)):
            out.append("water")
        before = set(self._persist.get("reasons") or [])
        if self.settings.get("bw_heat", True) and out_temp is not None:
            limit = float(self.settings.get("bw_heat_temp") or 30)
            if out_temp >= limit or ("heat" in before and out_temp > limit - 2):
                out.append("heat")
        if self.settings.get("bw_guard", True) and self.guard_seen(now):
            out.append("guard")
        if (self._persist.get("busy_until") or 0) > now:
            out.append("busy")
        if self.settings.get("bw_night", True) and self.is_night():
            out.append("night")
        return out

    # ------------------------------------------------------------ Garten frei, Igelschutz
    def guard_sensors(self) -> list[str]:
        """Person/Haustier-Sensoren im Garten (z. B. Kamera), gewählt oder automatisch."""
        chosen = [e for e in self.settings.get("bw_guard_sensors") or [] if e]
        if chosen:
            return chosen
        out = []
        for eid in self._ids("binary_sensor"):
            st = self.hass.states.get(eid)
            hay = f"{eid} {getattr(st, 'name', '') or ''}".lower()
            if any(w in hay for w in ("garten", "garden", "rasen", "lawn", "terrasse")) and any(
                    w in hay for w in ("person", "haustier", "pet", "animal", "tier", "kind", "child")) and "battery" not in hay:
                out.append(eid)
        return out

    def guard_seen(self, now: float) -> bool:
        """Jemand im Garten: Sensor an oder vor weniger als „Wartezeit“ zuletzt an."""
        wait = float(self.settings.get("bw_guard_wait") or 30) * 60
        seen = self._persist.get("guard_at") or 0
        hit = None
        for eid in self.guard_sensors():
            st = self.hass.states.get(eid)
            if st is not None and st.state == "on":
                hit = eid
                break
        if hit:
            self._persist["guard_at"] = seen = now
            self._persist["guard_by"] = hit
        return bool(seen) and now - seen < wait

    def camera(self) -> str | None:
        chosen = self.settings.get("bw_camera")
        if chosen:
            return chosen
        cams = [e for e in self._ids("camera") if any(w in e for w in ("garten", "garden", "rasen"))]
        return next((c for c in cams if "schnapp" not in c and "snapshot" not in c), cams[0] if cams else None)

    def _image(self) -> str | None:
        cam = self.camera()
        return f"/api/camera_proxy/{cam}" if cam else None

    def _sun(self) -> tuple[Any, Any, Any]:
        sun = self.hass.states.get(self.haus.settings.get("sun_entity") or "sun.sun")
        if sun is None:
            return None, None, None
        return sun.state, dt_util.parse_datetime(str(sun.attributes.get("next_setting") or "")), dt_util.parse_datetime(str(sun.attributes.get("next_rising") or ""))

    def is_night(self) -> bool:
        """Dunkel: Sonne unter dem Horizont (mit Puffer vor Sonnenuntergang und nach Sonnenaufgang)."""
        state, setting, rising = self._sun()
        if state is None:
            return False
        margin = float(self.settings.get("bw_night_margin") or 0) * 60
        now = dt_util.utcnow()
        if state == "below_horizon":
            return True
        if margin and setting is not None and (setting - now).total_seconds() < margin:
            return True
        # kurz nach Sonnenaufgang: next_rising liegt dann ~24 Std. in der Zukunft
        if margin and rising is not None and 86400 - (rising - now).total_seconds() < margin:
            return True
        return False

    async def async_busy(self, hours: float | None = None, until: str | None = None, by: str | None = None) -> None:
        """„Garten belegt“: Mäher fährt heim und wartet bis zur Uhrzeit (bzw. … Stunden); None = aufheben."""
        now = dt_util.utcnow().timestamp()
        if until == "evening":
            end = dt_util.now().replace(hour=23, minute=59, second=0, microsecond=0).timestamp()
        elif hours:
            end = now + float(hours) * 3600
        else:
            end = None
        self._persist["busy_until"] = end
        self._persist["busy_evening"] = until == "evening"
        if end:
            self.log.add("garden", "Garten belegt – Mäher bleibt in der Station",
                         f"bis {dt_util.as_local(dt_util.utc_from_timestamp(end)).strftime('%H:%M')}" + (f" · {by}" if by else ""), module="beetwerk")
        else:
            self.log.add("garden", "Garten wieder frei", by or "", module="beetwerk")
        self._save()
        await self.async_evaluate()

    def _watering(self, ent: dict) -> bool:
        if (self._persist.get("run") or {}).get("cur"):
            return True
        for z in self.zones():
            for valve in z.get("valves") or []:
                v = self.hass.states.get(valve)
                if v is not None and v.state in ("open", "opening", "on"):
                    return True
        st = self.hass.states.get(ent["watering"]) if ent.get("watering") else None
        if st is not None and st.state == "on":
            return True
        v = self.hass.states.get(ent["valve"]) if ent.get("valve") else None
        return v is not None and v.state in ("open", "opening", "on")

    async def _async_tick(self, _now=None) -> None:
        try:
            await self.async_evaluate()
        except Exception:  # noqa: BLE001 - Beetwerk darf den Takt nicht stoppen
            _LOGGER.exception("Beetwerk: Auswertung fehlgeschlagen")

    async def async_evaluate(self) -> None:
        await self._async_water_step()
        await self._async_water_plan()
        ent = self.entities()
        mower = ent.get("mower")
        now = dt_util.utcnow().timestamp()
        reasons = self._reasons(ent, now)
        self._persist["reasons"] = reasons
        st = self.hass.states.get(mower) if mower else None
        state = st.state if st is not None else None
        paused = self._persist.get("paused")
        today = dt_util.now().date().isoformat()
        if paused and paused.get("day") != today:
            paused = self._persist["paused"] = None
        winter = self._on(ent.get("winter"))
        await self._async_pause(ent, mower, state, reasons, paused, winter, now, today)
        self._track(ent, mower, state, now)
        # Fehler: „braucht Hilfe“
        err = self.error_text(ent, state)
        if err:
            self.haus.notify("bw_mower_error", "mower", "Mähroboter braucht Hilfe", f"{self._name(mower)}: {err}", image=self._image())
        else:
            self.haus.clear("bw_mower_error")
        # Wartung: Messer
        days = _num(self.hass.states.get(ent["blades_days"])) if ent.get("blades_days") else None
        limit = float(self.settings.get("bw_blades_days") or 0)
        if days is not None and limit and days >= limit and not winter:
            self.haus.notify("bw_blades", "mower_care", "Mähroboter: Messer wechseln", f"seit {days:.0f} Tagen im Einsatz (Hinweis ab {limit:.0f})")
        else:
            self.haus.clear("bw_blades")
        for key, text in self.wear(ent).items():
            if text and not winter:
                self.haus.notify(f"bw_wear_{key}", "mower_care", "Mähroboter: Wartung", text)
            else:
                self.haus.clear(f"bw_wear_{key}")
        self._season(ent, winter)
        self._watch(ent, mower, state, winter, now)

    async def _async_pause(self, ent: dict, mower: str | None, state: str | None, reasons: list[str],
                           paused: dict | None, winter: bool, now: float, today: str) -> None:
        """Mähpause: mäht, aber ein Grund spricht dagegen -> zur Station; Grund vorbei -> wieder starten."""
        if mower and state == "mowing" and reasons:
            why = ", ".join(PAUSE_TEXT[r] for r in reasons)
            # Igelschutz und „belegt bis heute Abend“: Feierabend (Robonect mäht am nächsten Tag nach Plan weiter)
            if ent.get("eod") and set(reasons) <= {"night", "busy"} and ("busy" not in reasons or self._persist.get("busy_evening")):
                await self._call("button", "press", ent["eod"])
            else:
                await self._call("lawn_mower", "dock", mower)
            self._persist["paused"] = {"at": now, "why": why, "reasons": reasons, "day": today}
            self._calm_since = None
            msg = why
            if "guard" in reasons and self._persist.get("guard_by"):
                msg += f" ({self._name(self._persist['guard_by'])})"
            self.log.add("garden", "Mähpause – Mäher fährt in die Station", msg, module="beetwerk")
            if "guard" in reasons:
                self.haus.notify("bw_guard", "mower_guard", "Mäher fährt heim", f"Jemand im Garten – {self._name(mower)} wartet in der Station",
                                 image=self._image())
            self._save()
            return
        if paused:
            # Gründe während der Pause sammeln (für die Wartezeit)
            seen = set(paused.get("reasons") or []) | set(reasons)
            if seen != set(paused.get("reasons") or []):
                paused["reasons"] = sorted(seen)
        if paused and not reasons and mower and not winter:
            self.haus.clear("bw_guard")
            got = set(paused.get("reasons") or [])
            if got <= {"night"} or (got <= {"night", "busy"} and self._persist.get("busy_evening")):
                # Igelschutz: nicht selbst wieder starten – der Zeitplan des Mähers übernimmt
                self._persist["paused"] = None
                self._save()
                return
            self._calm_since = self._calm_since or now
            wait = 0.0
            if got & set(WEATHER_REASONS):
                wait = float(self.settings.get("bw_resume_wait") or 60) * 60
            if "guard" in got:
                wait = max(wait, 0.0)  # die Wartezeit steckt schon in guard_seen()
            until = str(self.settings.get("bw_resume_until") or "19:00")
            local = dt_util.now()
            h, m = (int(x) for x in until.split(":")[:2])
            if self.settings.get("bw_resume", True) and now - self._calm_since >= wait and local.hour * 60 + local.minute < h * 60 + m:
                if state in ("docked", "paused"):
                    await self._call("lawn_mower", "start_mowing", mower)
                    self.log.add("garden", "Mähpause vorbei – Mäher startet wieder", paused.get("why"), module="beetwerk")
                self._persist["paused"] = None
                self._calm_since = None
                self._save()
        elif reasons:
            self._calm_since = None

    # ------------------------------------------------------------ Statistik, Verschleiß, Saison, Wächter
    def _track(self, ent: dict, mower: str | None, state: str | None, now: float) -> None:
        """Je Minute: Mähzeit, Ladevorgänge, Fehler, Messer-Drehzahl und Akku-Kapazität je Tag merken."""
        if not mower:
            return
        p = self._persist
        day = dt_util.now().date().isoformat()
        stats = p.setdefault("stats", {})
        d = stats.setdefault(day, {"min": 0, "charges": 0, "errors": 0})
        last = p.get("last_state")
        if state not in BAD:
            if state == "mowing":
                d["min"] = d.get("min", 0) + 1
                rpm = _num(self.hass.states.get(ent["blade_rpm"])) if ent.get("blade_rpm") else None
                if rpm:
                    d["rpm_sum"] = d.get("rpm_sum", 0) + rpm
                    d["rpm_n"] = d.get("rpm_n", 0) + 1
            if state == "docked" and last in ("returning", "mowing"):
                d["charges"] = d.get("charges", 0) + 1
            if state == "error" and last != "error":
                d["errors"] = d.get("errors", 0) + 1
                err = self.error_text(ent, state) or "Fehler"
                p["errors"] = (p.get("errors") or [])[-99:] + [{"at": now, "text": err}]
            if state != last:
                p["last_state"], p["last_state_at"] = state, now
        cap = _num(self.hass.states.get(ent["capacity"])) if ent.get("capacity") else None
        if cap:
            d["cap"] = max(d.get("cap") or 0, cap)
            p["cap_max"] = max(p.get("cap_max") or 0, cap)
        hours = _num(self.hass.states.get(ent["hours"])) if ent.get("hours") else None
        if hours is not None:
            d.setdefault("hours0", hours)
            d["hours1"] = hours
        out_temp, _rh = self.haus.outside_air()
        if out_temp is not None:
            d["tmin"] = min(d.get("tmin", out_temp), out_temp)
            d["tmax"] = max(d.get("tmax", out_temp), out_temp)
        if len(stats) > 60:
            for k in sorted(stats)[:-60]:
                stats.pop(k, None)
        if now - (p.get("saved_at") or 0) > 600:
            p["saved_at"] = now
            self._save()

    def _days(self, n: int, skip_today: bool = False) -> list[tuple[str, dict]]:
        stats = self._persist.get("stats") or {}
        today = dt_util.now().date()
        out = []
        for i in range(1 if skip_today else 0, n + (1 if skip_today else 0)):
            k = (today - timedelta(days=i)).isoformat()
            out.append((k, stats.get(k) or {}))
        return out

    def wear(self, ent: dict) -> dict[str, str | None]:
        """Verschleiß und Zustand: Messer stumpf, Akku altert, Draht- und WLAN-Signal schwach, Feuchte im Gehäuse."""
        out: dict[str, str | None] = {"blades": None, "battery": None, "wire": None, "wlan": None, "humid": None}
        quality = _num(self.hass.states.get(ent["blades_quality"])) if ent.get("blades_quality") else None
        recent = [d for _k, d in self._days(7) if d.get("rpm_n", 0) >= 30]
        older = [d for _k, d in self._days(30)[7:] if d.get("rpm_n", 0) >= 30]
        if quality and quality < 30:
            out["blades"] = f"Messerqualität nur noch {quality:.0f} % – Messer bald wechseln"
        elif len(recent) >= 3 and len(older) >= 5:
            now_rpm = sum(d["rpm_sum"] for d in recent) / sum(d["rpm_n"] for d in recent)
            base = sum(d["rpm_sum"] for d in older) / sum(d["rpm_n"] for d in older)
            if base and now_rpm < base * 0.9:
                out["blades"] = f"Messer drehen {100 - now_rpm / base * 100:.0f} % langsamer als sonst – Messer stumpf oder Gras sehr hoch"
        cap = _num(self.hass.states.get(ent["capacity"])) if ent.get("capacity") else None
        best = self._persist.get("cap_max") or 0
        lim = float(self.settings.get("bw_battery_min") or 70)
        if cap and best and cap < best * lim / 100:
            out["battery"] = f"Akku hat nur noch {cap:.0f} mAh ({cap / best * 100:.0f} % von {best:.0f}) – Akku altert"
        st = self.hass.states.get(self.mower() or "")
        mowing = st is not None and st.state == "mowing"
        wire = _num(self.hass.states.get(ent["wire"])) if ent.get("wire") else None
        if mowing and wire is not None and wire < 40:
            out["wire"] = f"Signal des Begrenzungsdrahts schwach ({wire:.0f} %) – Draht oder Ladestation prüfen"
        wlan = _num(self.hass.states.get(ent["wlan"])) if ent.get("wlan") else None
        if wlan is not None and 0 <= wlan < 25:
            out["wlan"] = f"WLAN am Mäher schwach ({wlan:.0f} %) – Verbindung kann abreißen"
        humid = _num(self.hass.states.get(ent["humidity"])) if ent.get("humidity") else None
        if humid is not None and humid >= 80:
            out["humid"] = f"Feuchte im Gehäuse {humid:.0f} % – Mäher trocknen lassen, Dichtungen prüfen"
        return out

    def _season(self, ent: dict, winter: bool) -> None:
        """Herbst: dauerhaft kalt -> „Winterpause einlegen?“; Frühjahr in der Winterpause: dauerhaft mild -> „Saison starten?“."""
        if not self.settings.get("bw_season", True) or not self.mower():
            self.haus.clear("bw_season")
            return
        month = dt_util.now().month
        days = [d for _k, d in self._days(5, skip_today=True)]
        if not winter and month in (9, 10, 11, 12, 1, 2):
            last3 = days[:3]
            if len(last3) == 3 and all("tmax" in d and d["tmax"] < 5 for d in last3):
                self.haus.notify("bw_season", "mower_care", "Mähroboter: Winterpause einlegen?",
                                 "Seit 3 Tagen kaum über 5 °C – der Rasen wächst nicht mehr. Mäher reinigen, laden und einlagern.")
                return
        if winter and month in (2, 3, 4, 5, 6):
            if len(days) == 5 and all("tmin" in d and d["tmin"] >= 5 for d in days):
                self.haus.notify("bw_season", "mower_care", "Mähroboter: Saison starten?",
                                 "Seit 5 Tagen nachts über 5 °C – der Rasen wächst wieder.")
                return
        self.haus.clear("bw_season")

    def _watch(self, ent: dict, mower: str | None, state: str | None, winter: bool, now: float) -> None:
        """Wächter: außerhalb der Station ohne Verbindung, steht lange im Garten, nachts nicht in der Station."""
        if not mower or not self.settings.get("bw_watch", True) or winter:
            for k in ("bw_watch_lost", "bw_watch_stuck", "bw_watch_night"):
                self.haus.clear(k)
            return
        p = self._persist
        lim = float(self.settings.get("bw_watch_min") or 20) * 60
        name = self._name(mower)
        st = self.hass.states.get(mower)
        since = (now - st.last_changed.timestamp()) if st is not None and getattr(st, "last_changed", None) else 0
        last = p.get("last_state")
        if state in ("unavailable", None) and last in UNSAFE and since >= lim:
            self.haus.notify("bw_watch_lost", "mower", "Mähroboter nicht erreichbar",
                             f"{name} ist seit {since / 60:.0f} Min. ohne Verbindung und war nicht in der Station – WLAN weg oder gestohlen?",
                             image=self._image())
        else:
            self.haus.clear("bw_watch_lost")
        if state == "paused" and since >= lim and not p.get("paused"):
            self.haus.notify("bw_watch_stuck", "mower", "Mähroboter steht im Garten",
                             f"{name} steht seit {since / 60:.0f} Min. außerhalb der Station", image=self._image())
        else:
            self.haus.clear("bw_watch_stuck")
        local = dt_util.now()
        if state in UNSAFE and (local.hour >= 22 or local.hour < 5) and self.is_night():
            self.haus.notify("bw_watch_night", "mower", "Mähroboter nachts nicht in der Station",
                             f"{name}: {state} – bitte nachsehen", image=self._image())
        else:
            self.haus.clear("bw_watch_night")

    def stats(self) -> dict[str, Any]:
        """Statistik: Mähstunden, Ladevorgänge, Fehler – 7 Tage und je Tag (14), häufigste Fehler."""
        days = self._days(14)
        def hrs(d: dict) -> float:
            if "hours0" in d and "hours1" in d and d["hours1"] >= d["hours0"]:
                return max(d["hours1"] - d["hours0"], d.get("min", 0) / 60)
            return d.get("min", 0) / 60
        week = days[:7]
        now = dt_util.utcnow().timestamp()
        errs = [e for e in self._persist.get("errors") or [] if now - e["at"] < 7 * 86400]
        top: dict[str, dict] = {}
        for e in errs:
            t = top.setdefault(e["text"], {"text": e["text"], "count": 0, "hours": []})
            t["count"] += 1
            t["hours"].append(dt_util.as_local(dt_util.utc_from_timestamp(e["at"])).hour)
        for t in top.values():
            h = sorted(t.pop("hours"))
            t["from"], t["to"] = h[len(h) // 4], h[(len(h) * 3) // 4]
        return {
            "week_hours": round(sum(hrs(d) for _k, d in week), 1),
            "week_charges": sum(d.get("charges", 0) for _k, d in week),
            "week_errors": sum(d.get("errors", 0) for _k, d in week),
            "days": [{"day": k, "hours": round(hrs(d), 2), "charges": d.get("charges", 0), "errors": d.get("errors", 0)} for k, d in reversed(days)],
            "errors": sorted(top.values(), key=lambda t: -t["count"]),
            "last_errors": [{"at": dt_util.utc_from_timestamp(e["at"]).isoformat(), "text": e["text"]} for e in reversed((self._persist.get("errors") or [])[-10:])],
            "cap_max": self._persist.get("cap_max"),
        }

    def timers(self, ent: dict) -> list[dict[str, Any]]:
        """Zeitpläne des Mähers (Robonect: 14 Timer mit Start, Ende, Wochentagen)."""
        out = []
        for eid in ent.get("timers") or []:
            st = self.hass.states.get(eid)
            if st is None:
                continue
            a = st.attributes or {}
            wd = a.get("weekdays") or {}
            out.append({"entity": eid, "id": a.get("id") or int(eid.rsplit("_", 1)[-1]), "on": st.state == "on",
                        "start": a.get("start"), "end": a.get("end"),
                        "days": [k for k in DAY_KEYS if (wd.get(k) if isinstance(wd, dict) else False)]})
        return out

    async def async_timer(self, timer: int, enable: bool, start: str, end: str, days: list[str], by: str | None = None) -> None:
        """Zeitplan am Mäher ändern (Robonect: Aktion robonect.timer)."""
        mower = self.mower()
        if not mower:
            return
        await self._call_data("robonect", "timer", {"entity_id": mower, "timer": str(timer), "enable": bool(enable),
                                                     "start": start, "end": end, "weekdays": [d for d in DAY_KEYS if d in days]})
        self.log.add("garden", f"Zeitplan {timer} geändert", f"{'an' if enable else 'aus'} · {start}–{end} · "
                     + (", ".join({'mo': 'Mo', 'tu': 'Di', 'we': 'Mi', 'th': 'Do', 'fr': 'Fr', 'sa': 'Sa', 'su': 'So'}[d] for d in DAY_KEYS if d in days) or "kein Tag")
                     + (f" · {by}" if by else ""), module="beetwerk")
        self._dev = None

    def error_text(self, ent: dict, state: str | None) -> str | None:
        if state == "error":
            msg = self.hass.states.get(ent["error"]) if ent.get("error") else None
            text = msg.state if msg is not None and msg.state not in BAD else None
            return text or "Fehler"
        return None

    def _on(self, entity_id: str | None) -> bool:
        st = self.hass.states.get(entity_id) if entity_id else None
        return st is not None and st.state == "on"

    async def _call(self, domain: str, service: str, entity_id: str) -> None:
        try:
            await self.hass.services.async_call(domain, service, {"entity_id": entity_id}, blocking=False, context=self.haus.own_context("Beetwerk"))
        except Exception as err:  # noqa: BLE001 - Dienst nicht verfügbar: nur protokollieren
            self.log.add("garden", f"Befehl an {self._name(entity_id)} fehlgeschlagen", str(err), module="beetwerk")

    # ------------------------------------------------------------ Bewässerung (Smart Irrigation)
    def zones(self) -> list[dict[str, Any]]:
        """Zonen: gewählte (mit Ventil) plus automatisch alle Zonen-Sensoren von Smart Irrigation (Dauer in s, Attribut bucket)."""
        chosen = {z.get("zone"): z for z in self.settings.get("bw_zones") or [] if z.get("zone")}
        found = [e for e in self._ids("sensor") if e.startswith("sensor.smart_irrigation_")
                 and (st := self.hass.states.get(e)) is not None and "bucket" in (st.attributes or {})]
        out = []
        for zid in list(chosen) + [e for e in found if e not in chosen]:
            cfg = chosen.get(zid) or {}
            valves = [v for v in (cfg.get("valves") or ([cfg["valve"]] if cfg.get("valve") else [])) if v]
            guessed = not valves
            if guessed:
                g = self._guess_valve(zid)
                valves = [g] if g else []
            out.append({"zone": zid, "valves": valves, "valve": valves[0] if valves else None, "guessed": guessed,
                        "auto": cfg.get("auto", True) is not False})
        return out

    def _guess_valve(self, zone: str) -> str | None:
        """Ventil mit gleichem Namen wie die Zone (z. B. Zone „Beet Links“ ↔ Ventil „Beet_Links“) – nicht die Ventile von Smart Irrigation selbst."""
        st = self.hass.states.get(zone)
        name = ((getattr(st, "name", None) or "") if st is not None else "").lower().removesuffix(" dauer")
        key = "".join(ch for ch in name if ch.isalnum())
        if not key:
            return None
        for eid in self._ids("valve"):
            if eid.startswith("valve.smart_irrigation_"):
                continue
            vs = self.hass.states.get(eid)
            vname = "".join(ch for ch in (getattr(vs, "name", None) or "").lower() if ch.isalnum())
            if vname == key:
                return eid
        return None

    def _zone_info(self, z: dict) -> dict[str, Any]:
        st = self.hass.states.get(z["zone"])
        a = (st.attributes if st is not None else {}) or {}
        base = z["zone"].removeprefix("sensor.smart_irrigation_")
        mult = self.hass.states.get(f"number.smart_irrigation_{base}_multiplier")
        need = self.hass.states.get(f"binary_sensor.smart_irrigation_{base}_irrigation_needed")
        valve = self.hass.states.get(z["valve"]) if z.get("valve") else None
        run = self._persist.get("run") or {}
        cur = run.get("cur") or {}
        mine = cur.get("zone") == z["zone"]
        queued = [q for q in run.get("queue") or [] if q["zone"] == z["zone"]]
        return {
            **z, "name": (a.get("friendly_name") or base).removesuffix(" Dauer"),
            "duration": _num(st), "bucket": a.get("bucket"), "max_bucket": a.get("maximum_bucket"),
            "multiplier": _num(mult) if mult is not None else a.get("multiplier"), "multiplier_entity": f"number.smart_irrigation_{base}_multiplier" if mult is not None else None,
            "need": None if need is None else need.state == "on", "state": a.get("state"), "last_calculated": a.get("last_calculated"),
            "throughput": a.get("throughput"), "size": a.get("size"),
            "valve_state": valve.state if valve is not None else None,
            "running_until": dt_util.utc_from_timestamp(cur["until"]).isoformat() if mine else None,
            # Ablauftimer der ganzen Zone (alle Ventile nacheinander) und welches Ventil gerade läuft
            "zone_until": dt_util.utc_from_timestamp(cur["until"] + sum(q["seconds"] for q in queued)).isoformat() if mine else None,
            "running_valve": cur.get("valve") if mine else None,
            "part": cur.get("part") if mine else None, "parts": cur.get("parts") if mine else None,
            "waiting": bool(queued) and not mine,
            "valve_states": {v: (self.hass.states.get(v).state if self.hass.states.get(v) is not None else None) for v in z.get("valves") or []},
        }

    def _rain_soon(self) -> bool:
        weather = self.hass.states.get(self.haus.weather_entity() or "")
        if weather is not None and weather.state in RAINY:
            return True
        now = dt_util.utcnow().timestamp()
        return any(h.get("rain") and now <= (h.get("ts") or 0) <= now + 6 * 3600 for h in getattr(self.haus, "hourly", None) or [])

    async def async_water(self, zone: str | None = None, seconds: float | None = None, by: str | None = None) -> str:
        """Gießen starten: eine Zone (Dauer frei oder berechnet) oder alle Zonen mit Bedarf nacheinander."""
        queue = []
        for z in self.zones():
            if zone and z["zone"] != zone:
                continue
            valves = z.get("valves") or []
            if not valves:
                continue
            calc = _num(self.hass.states.get(z["zone"])) or 0
            secs = float(seconds) if seconds else calc
            if secs <= 0:
                continue
            # Ventile nacheinander, jedes für die volle Zeit; Wasserbilanz erst nach dem letzten zurücksetzen
            reset = not seconds or abs(secs - calc) < 1
            for i, v in enumerate(valves):
                queue.append({"zone": z["zone"], "valve": v, "seconds": round(secs), "part": i + 1, "parts": len(valves),
                              "reset": reset and i == len(valves) - 1})
        if not queue:
            return "nichts zu gießen"
        run = self._persist.get("run") or {}
        run["queue"] = (run.get("queue") or []) + queue
        self._persist["run"] = run
        def what(q: dict) -> str:
            part = f" ({q['part']}/{q['parts']} {self._name(q['valve'])})" if q.get("parts", 1) > 1 else ""
            return f"{self._name(q['zone']).removesuffix(' Dauer')}{part} {q['seconds'] // 60} Min."

        self.log.add("garden", "Bewässerung gestartet", ", ".join(what(q) for q in queue)
                     + (f" · {by}" if by else ""), module="beetwerk")
        # Mäher währenddessen in die Station
        mower = self.mower()
        if mower and (st := self.hass.states.get(mower)) is not None and st.state == "mowing":
            await self._call("lawn_mower", "dock", mower)
        await self._async_water_step()
        self._save()
        return "gestartet"

    async def async_water_stop(self, by: str | None = None) -> None:
        run = self._persist.get("run") or {}
        cur = run.get("cur")
        self._persist["run"] = None
        if cur:
            await self._valve(cur["valve"], False)
            self.log.add("garden", "Bewässerung gestoppt", (self._name(cur["zone"]).removesuffix(" Dauer")) + (f" · {by}" if by else ""), module="beetwerk")
        self._save()

    async def _async_water_step(self, _now=None) -> None:
        """Laufende Zone fertig? Ventil zu, Wasserbilanz zurücksetzen, nächste Zone öffnen."""
        run = self._persist.get("run") or {}
        now = dt_util.utcnow().timestamp()
        cur = run.get("cur")
        if cur and now >= cur["until"] - 1:
            await self._valve(cur["valve"], False)
            if cur.get("reset"):
                await self._call_data("smart_irrigation", "set_bucket", {"entity_id": cur["zone"]})
            part = f" · Ventil {cur['part']}/{cur['parts']} {self._name(cur['valve'])}" if cur.get("parts", 1) > 1 else ""
            self.log.add("garden", f"{self._name(cur['zone']).removesuffix(' Dauer')} gegossen", f"{round((now - cur['start']) / 60)} Min.{part}"
                         + (" · Wasserbilanz zurückgesetzt" if cur.get("reset") else ""), module="beetwerk")
            run["cur"] = cur = None
        if not cur and run.get("queue"):
            nxt = run["queue"].pop(0)
            await self._valve(nxt["valve"], True)
            run["cur"] = {**nxt, "start": now, "until": now + nxt["seconds"]}
            if self._stop_timer:
                self._stop_timer()
            self._stop_timer = async_call_later(self.hass, nxt["seconds"] + 1, self._async_water_step)
        self._persist["run"] = run if (run.get("cur") or run.get("queue")) else None
        if run.get("cur") is None and not run.get("queue"):
            self._persist["run"] = None
        self._save()

    async def _async_water_plan(self) -> None:
        """Täglich zur Startzeit: alle Zonen mit berechneter Dauer gießen (außer bei Regen)."""
        if not self.settings.get("bw_water_auto"):
            return
        local = dt_util.now()
        h, m = (int(x) for x in str(self.settings.get("bw_water_time") or "05:00").split(":")[:2])
        today = local.date().isoformat()
        if local.hour * 60 + local.minute < h * 60 + m or self._persist.get("water_day") == today:
            return
        if local.hour * 60 + local.minute > h * 60 + m + 120:  # mehr als 2 Std. verpasst (z. B. Neustart): heute auslassen
            self._persist["water_day"] = today
            return
        self._persist["water_day"] = today
        if self.settings.get("bw_water_skip", True) and self._rain_soon():
            self.log.add("garden", "Bewässerung ausgelassen", "Regen jetzt oder in den nächsten 6 Std.", module="beetwerk")
            self._save()
            return
        zones = [z for z in self.zones() if z.get("auto") and z.get("valves") and (_num(self.hass.states.get(z["zone"])) or 0) > 0]
        if not zones:
            self.log.add("garden", "Heute kein Gießen nötig", "Wasserbilanz aller Zonen im Plus", module="beetwerk")
            self._save()
            return
        for z in zones:
            await self.async_water(z["zone"], by="Gießplan")

    async def _valve(self, entity_id: str, on: bool) -> None:
        domain = entity_id.split(".")[0]
        if domain == "valve":
            await self._call("valve", "open_valve" if on else "close_valve", entity_id)
        else:
            await self._call("homeassistant", "turn_on" if on else "turn_off", entity_id)

    async def _call_data(self, domain: str, service: str, data: dict) -> None:
        try:
            await self.hass.services.async_call(domain, service, data, blocking=False, context=self.haus.own_context("Beetwerk"))
        except Exception as err:  # noqa: BLE001 - Dienst nicht verfügbar
            self.log.add("garden", f"{domain}.{service} fehlgeschlagen", str(err), module="beetwerk")

    def automations(self) -> list[dict[str, Any]]:
        """Bestehende Bewässerungs-Automationen (zum Abschalten, wenn Beetwerk gießt)."""
        out = []
        for eid in self._ids("automation"):
            st = self.hass.states.get(eid)
            hay = f"{eid} {getattr(st, 'name', '') or ''}".lower()
            if any(w in hay for w in ("bewässer", "bewasser", "beregn", "irrigation", "gießen", "giessen", "sprinkler")):
                out.append({"id": eid, "name": getattr(st, "name", None) or eid, "on": st.state == "on" if st is not None else False})
        return out

    def _water_until(self) -> str | None:
        """Ablauftimer der ganzen Bewässerung: Ende der laufenden plus aller wartenden Ventile."""
        run = self._persist.get("run") or {}
        cur = run.get("cur")
        if not cur and not run.get("queue"):
            return None
        end = (cur["until"] if cur else dt_util.utcnow().timestamp()) + sum(q["seconds"] for q in run.get("queue") or [])
        return dt_util.utc_from_timestamp(end).isoformat()

    def next_water(self) -> str | None:
        if not self.settings.get("bw_water_auto"):
            return None
        local = dt_util.now()
        h, m = (int(x) for x in str(self.settings.get("bw_water_time") or "05:00").split(":")[:2])
        at = local.replace(hour=h, minute=m, second=0, microsecond=0)
        if self._persist.get("water_day") == local.date().isoformat() or at <= local:
            at += timedelta(days=1)
        return at.isoformat()

    # ------------------------------------------------------------ Für das Panel
    def status(self) -> dict[str, Any]:
        ent = self.entities()
        mower = ent.get("mower")
        st = self.hass.states.get(mower) if mower else None
        now = dt_util.utcnow().timestamp()
        paused = self._persist.get("paused")
        return {
            "entities": ent,
            "configured": bool(mower or ent.get("valve") or self.zones()),
            "reasons": [{"k": r, "text": PAUSE_TEXT[r]} for r in self._persist.get("reasons") or []],
            "paused": {**paused, "at": dt_util.utc_from_timestamp(paused["at"]).isoformat()} if paused else None,
            "error": self.error_text(ent, st.state if st is not None else None),
            "watering": self._watering(ent),
            "water_end": dt_util.utc_from_timestamp(self._water_end).isoformat() if self._water_end and now - self._water_end < 86400 else None,
            "zones": [self._zone_info(z) for z in self.zones()],
            "queue": len(((self._persist.get("run") or {}).get("queue")) or []),
            "water_until": self._water_until(),
            "next_water": self.next_water(),
            "automations": self.automations(),
            "guard": {"sensors": self.guard_sensors(), "camera": self.camera(),
                      "seen": dt_util.utc_from_timestamp(self._persist["guard_at"]).isoformat() if self._persist.get("guard_at") and now - self._persist["guard_at"] < 86400 else None,
                      "by": self._persist.get("guard_by")},
            "busy_until": dt_util.utc_from_timestamp(self._persist["busy_until"]).isoformat() if (self._persist.get("busy_until") or 0) > now else None,
            "night": self.is_night(),
            "sun": self._sun_times(),
            "wear": {k: v for k, v in self.wear(ent).items() if v},
            "stats": self.stats(),
            "timers": self.timers(ent),
            "next_start": self._next_start(ent),
            "since": dt_util.utc_from_timestamp(self._persist["last_state_at"]).isoformat() if self._persist.get("last_state_at") else None,
        }

    def _sun_times(self) -> dict[str, str | None]:
        _state, setting, rising = self._sun()
        return {"set": setting.isoformat() if setting else None, "rise": rising.isoformat() if rising else None}

    def _next_start(self, ent: dict) -> str | None:
        st = self.hass.states.get(ent["next_start"]) if ent.get("next_start") else None
        if st is None or st.state in BAD:
            return None
        ts = dt_util.parse_datetime(str(st.state))
        return ts.isoformat() if ts else None
