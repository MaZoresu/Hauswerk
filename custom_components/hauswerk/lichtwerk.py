"""Hauswerk-Modul Lichtwerk: Licht nach dem Vorbild des Blueprints „Smart Light“ (Blackshome).

Jede Leuchte (oder Gruppe, Schalter) nutzt ein **Profil** – das entspricht einer Smart-Light-Automation:
Einschalten bei Sonne/Helligkeit/Uhrzeit/Entität/Rollläden, Ausschalten entsprechend, Wochentage, Helligkeit,
Übergang, Farbe, dynamisches Licht, Nachtlicht, Pause-Schalter. Dazu Bewegung (optional), Anwesenheit und
Urlaubs-Simulation aus Hauswerk. Schaltet jemand von Hand, wartet die Automatik bis zum nächsten Wechsel.

Wie im Blueprint zählt der Wechsel (Flanke): Lichtwerk merkt sich je Licht den Stand der Auslöser („latch“)
und rechnet feste Auslöser (Sonne, Uhrzeit) für heute und gestern voraus – so stimmt der Stand auch nach
einem Neustart, und die Tagesleiste zeigt die Zeiten im Voraus.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
import random
from typing import Any

from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import LIGHT_STORAGE_KEY
from .core import Haus
from .hmlinks import HmLinks, sensor_kind, split_peer
from .light_logic import (LW_PROFILE_DEFAULTS, LW_PROFILE_SPEC, day_allowed, day_events, day_plan, decide, latched_at, light_params,
                          manual_suggestions, plan_offset)
from .log import Protokoll, log_settings

_LOGGER = logging.getLogger(__name__)

BAD = {"unavailable", "unknown", None}
LIGHT_DOMAINS = ("light", "switch", "input_boolean")

LW_DEFAULTS: dict[str, Any] = {
    "lw_lights": [],          # Leuchten, Gruppen und Schalter, die Lichtwerk schaltet
    "lw_lux_sensor": None,    # Helligkeit für alle Profile (leer = erster Lux-Sensor im Freien)
    "lw_away_min": 30,        # Benachrichtigung, wenn Licht so lange brennt, obwohl niemand zu Hause ist
}
LW_KEYS = frozenset(LW_DEFAULTS)


class Lichtwerk:
    """Licht-Steuerung mit Profilen, Ursache je Licht und Vorausschau."""

    def __init__(self, hass: HomeAssistant, log: Protokoll, haus: Haus) -> None:
        self.hass = hass
        self.log = log
        self.haus = haus
        self._store: Store = Store(hass, 1, LIGHT_STORAGE_KEY)
        self.settings: dict[str, Any] = dict(LW_DEFAULTS)
        self.profiles: dict[str, dict[str, Any]] = {}
        self.lights: dict[str, dict[str, Any]] = {}     # je Licht: profile, auto, name
        self._rt: dict[str, dict[str, Any]] = {}
        self._ctx: list[str] = []                        # eigene Befehle (Context-IDs) – alles andere ist „von Hand“
        self._last_min: float | None = None
        self._last_day: str | None = None
        self._unsubs: list[Callable[[], None]] = []
        self._state_unsub: Callable[[], None] | None = None
        self._pending: Callable[[], None] | None = None
        self._subscribers: set[Callable[[dict], None]] = set()
        self._sunfn_cache: dict = {}
        self._status: dict = {}
        self._away_since: float | None = None
        # Direktverknüpfungen der Homematic-CCU (nur lesen): Licht → Gegenstellen; Sender → zuletzt geändert
        self.hmlinks = HmLinks(hass)
        self._links: dict[str, dict] = {}
        self._link_findings: list[dict] = []
        self._links_next = 0.0
        self._sensor_seen: dict[str, float] = {}
        # gelernt: wie lange nach dem letzten Melden die CCU wirklich ausschaltet (Leuchte → Sender-Adresse → Sekunden)
        self._learn: dict[str, dict[str, list[float]]] = {}
        # Bericht: Brenndauer/Energie je Tag und Leuchte, Schaltungen von Hand (für Vorschläge), Gerätezustand
        self._stats: dict[str, dict[str, dict[str, float]]] = {}
        self._manual_ev: list[dict] = []
        self._last_tick: float | None = None
        self._dev_cache: tuple[float, dict] | None = None

    # ------------------------------------------------------------ Speicher
    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        self.settings.update({k: v for k, v in (stored.get("settings") or {}).items() if k in LW_KEYS})
        self.lights = stored.get("lights") or {}
        self.profiles = stored.get("profiles") or {}
        self._learn = stored.get("learn") or {}
        self._stats = stored.get("stats") or {}
        self._manual_ev = stored.get("manual_ev") or []
        for eid, rt in (stored.get("rt") or {}).items():
            self._rt[eid] = {k: v for k, v in rt.items() if k in ("latch", "latch_reason", "latch_at", "manual", "ours")}
        if not self.profiles:
            self.profiles = {"standard": {**LW_PROFILE_DEFAULTS, "name": "Abendlicht"}}

    def _data(self) -> dict[str, Any]:
        rt = {eid: {k: r.get(k) for k in ("latch", "latch_reason", "latch_at", "manual", "ours")} for eid, r in self._rt.items()}
        return {"settings": self.settings, "lights": self.lights, "profiles": self.profiles, "rt": rt, "learn": self._learn,
                "stats": self._stats, "manual_ev": self._manual_ev}

    def _save(self, delay: float = 2) -> None:
        self._store.async_delay_save(self._data, delay)

    async def async_start(self) -> None:
        self._unsubs.append(async_track_time_interval(self.hass, self._async_tick, timedelta(minutes=1)))
        self._unsubs.append(self.haus.subscribe(self._on_house))
        self._track()
        await self.async_evaluate()

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None
        await self._store.async_save(self._data())

    # ------------------------------------------------------------ Beobachten
    def _track(self) -> None:
        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None
        ids: set[str] = set(self.settings.get("lw_lights") or [])
        for eid in list(ids):
            prof = self.profile(eid)
            ids.update(e for e in (prof.get("entity"), prof.get("bypass"), prof.get("lux_sensor")) if e)
            ids.update(prof.get("motion") or [])
            if prof.get("on_covers"):
                ids.update(self._covers_near(eid))
        if self.settings.get("lw_lux_sensor"):
            ids.add(self.settings["lw_lux_sensor"])
        for info in self._links.values():
            for p in info["peers"]:
                ids.update(p.get("entities") or [])
        if ids:
            self._state_unsub = async_track_state_change_event(self.hass, sorted(ids), self._on_change)

    @callback
    def _on_change(self, event: Event) -> None:
        eid = event.data.get("entity_id")
        new, old = event.data.get("new_state"), event.data.get("old_state")
        if eid not in self.lights:
            self._sensor_seen[eid] = dt_util.utcnow().timestamp()
        if eid in self.lights and eid in (self.settings.get("lw_lights") or []):
            self._note_light(eid, old, new)
        if self._pending is None:
            self._pending = async_call_later(self.hass, 1, self._async_later)

    def _note_light(self, eid: str, old, new) -> None:
        """Änderung einer Leuchte: eigener Befehl oder von Hand (bzw. andere Automation/Schalter)?"""
        if new is None or old is None or new.state in BAD or old.state in BAD:
            return
        changed = old.state != new.state
        if not changed and new.state == "on":
            a, b = old.attributes.get("brightness"), new.attributes.get("brightness")
            changed = a is not None and b is not None and abs(int(a) - int(b)) > 25
        if not changed:
            return
        ctx = new.context
        if ctx is not None and (ctx.id in self._ctx or (ctx.parent_id and ctx.parent_id in self._ctx)):
            return
        rt = self._rt.setdefault(eid, {})
        prof = self.profile(eid)
        now = dt_util.utcnow().timestamp()
        # über eine Direktverknüpfung der CCU? (Sender der Verknüpfung hat sich gerade geändert)
        peers = (self._links.get(eid) or {}).get("peers", [])
        sender = next((p for p in peers if any(now - self._sensor_seen.get(e, 0) <= 10 for e in p.get("entities") or [])), None)
        if sender is None and new.state == "off":
            # Ausschalten nach der Nachlaufzeit der CCU: Melder ist seit höchstens 30 Min. wieder ruhig
            sender = next((p for p in peers if p.get("kind") == "motion" and any(
                (st := self.hass.states.get(e)) is not None and st.state == "off"
                and now - st.last_changed.timestamp() <= 1800 for e in p.get("entities") or [])), None)
        if sender is not None and new.state == "off":
            self._learn_off(eid, sender, now)
        if sender is not None:
            if new.state == "on":
                rt["manual"] = {"since": now, "until": None, "state": "on", "ccu": sender["name"]}
            elif (rt.get("manual") or {}).get("ccu"):
                rt["manual"] = None  # die CCU hat wieder ausgeschaltet: Lichtwerk übernimmt
            rt["ours"] = False
            self.log.add("light", f"{self._name(eid)}: HmIP {'an' if new.state == 'on' else 'aus'}",
                         f"Direktverknüpfung {sender['name']}" + (" · Lichtwerk wartet, bis sie wieder ausschaltet" if new.state == "on" else ""),
                         module="lichtwerk")
            self._save()
            return
        if new.state == "off" and (rt.get("manual") or {}).get("ccu"):
            sender = rt["manual"]["ccu"]
            peer = next((p for p in peers if p["name"] == sender), None)
            if peer:
                self._learn_off(eid, peer, now)
            rt["manual"] = None  # CCU-Verknüpfung (Nachlaufzeit) hat ausgeschaltet
            self.log.add("light", f"{self._name(eid)}: HmIP aus", f"Direktverknüpfung {sender}", module="lichtwerk")
            self._save()
            return
        until = None
        if prof.get("manual_hold") == "hours":
            until = dt_util.utcnow().timestamp() + float(prof.get("manual_hours") or 2) * 3600
        rt["manual"] = {"since": dt_util.utcnow().timestamp(), "until": until, "state": new.state}
        rt["ours"] = False
        if new.state in ("on", "off") and old.state != new.state and (self.lights.get(eid) or {}).get("auto", True) is not False:
            loc = dt_util.as_local(dt_util.utcnow())
            self._manual_ev.append({"t": round(now), "e": eid, "a": new.state, "p": (self.lights.get(eid) or {}).get("profile") or "standard",
                                    "d": plan_offset(rt.get("plan") or [], loc.hour * 60 + loc.minute, new.state)})
            cut = now - 30 * 86400
            self._manual_ev = [e for e in self._manual_ev if e.get("t", 0) >= cut][-500:]
        if (self._links.get(eid) or {}).get("peers"):
            # Meldung des Senders kann kurz nach der Leuchte kommen: in 3 s nachsehen, ob es doch die CCU war
            async_call_later(self.hass, 3, lambda _n, eid=eid, st=new.state, t=now: self._recheck_ccu(eid, st, t))
        self.log.add("light", f"{self._name(eid)}: von Hand {'an' if new.state == 'on' else 'aus' if new.state == 'off' else new.state}",
                     "Automatik wartet " + (f"bis {dt_util.as_local(dt_util.utc_from_timestamp(until)).strftime('%H:%M')}"
                                            if until else "bis zum nächsten Wechsel"), module="lichtwerk")
        self._save()

    @callback
    def _check_switched(self, eid: str, on: bool) -> None:
        """30 s nach einem Befehl: hat die Leuchte geschaltet? Sonst merken und melden (einmal je Störung)."""
        rt = self._rt.setdefault(eid, {})
        st = self.hass.states.get(eid)
        if st is None or st.state in BAD:
            return
        if (st.state == "on") == on:
            if rt.pop("fail", None):
                self.log.add("health", f"{self._name(eid)} schaltet wieder", "Befehl ausgeführt", module="lichtwerk")
                self._save()
            return
        if rt.get("manual"):
            return  # in der Zwischenzeit von Hand bzw. über HmIP geschaltet
        first = not rt.get("fail")
        rt["fail"] = {"at": dt_util.utcnow().isoformat(), "want": "on" if on else "off", "n": int((rt.get("fail") or {}).get("n", 0)) + 1}
        if first:
            self.log.add("health", f"{self._name(eid)} schaltet nicht", f"Lichtwerk wollte {'an' if on else 'aus'}, die Leuchte blieb {st.state}"
                         " – Funk, Strom oder Schalter prüfen", module="lichtwerk")

    def _learn_off(self, eid: str, peer: dict, now: float) -> None:
        """CCU hat ausgeschaltet: Abstand zum letzten Melden des Melders merken (letzte 10, Median zählt)."""
        sts = [st for e in peer.get("entities") or [] if (st := self.hass.states.get(e)) is not None]
        if not sts or any(st.state == "on" for st in sts):
            return
        delta = now - max(st.last_changed.timestamp() for st in sts)
        if not 0 <= delta <= 3600:
            return
        lst = self._learn.setdefault(eid, {}).setdefault(peer["address"], [])
        lst.append(round(delta, 1))
        del lst[:-10]
        self._save()

    def learned_off(self, eid: str, peer: dict) -> float | None:
        lst = sorted((self._learn.get(eid) or {}).get(peer.get("address"), []))
        return lst[len(lst) // 2] if len(lst) >= 3 else None

    @callback
    def _recheck_ccu(self, eid: str, state: str, at: float) -> None:
        rt = self._rt.get(eid) or {}
        sender = next((p for p in (self._links.get(eid) or {}).get("peers", [])
                       if any(abs(self._sensor_seen.get(e, 0) - at) <= 10 for e in p.get("entities") or [])), None)
        if sender is None or not rt.get("manual") or rt["manual"].get("since", 0) < at - 1:
            return
        rt["manual"] = {"since": at, "until": None, "state": state, "ccu": sender["name"]} if state == "on" else None
        self._manual_ev = [e for e in self._manual_ev if not (e.get("e") == eid and abs(e.get("t", 0) - at) <= 2)]  # doch HmIP: zählt nicht als von Hand
        self.log.add("light", f"{self._name(eid)}: HmIP {'an' if state == 'on' else 'aus'}",
                     f"Direktverknüpfung {sender['name']} – doch nicht von Hand" + (" · Lichtwerk wartet, bis sie wieder ausschaltet" if state == "on" else ""), module="lichtwerk")
        self._save()
        self.hass.async_create_task(self.async_evaluate())

    async def _async_later(self, _now=None) -> None:
        self._pending = None
        await self.async_evaluate()

    def _count_usage(self) -> None:
        """Brenndauer und Energie je Leuchte für den Bericht (jede Minute, 35 Tage)."""
        now = dt_util.utcnow().timestamp()
        last, self._last_tick = self._last_tick, now
        if last is None:
            return
        dt = min(max(now - last, 0), 180)
        day = dt_util.as_local(dt_util.utcnow()).date().isoformat()
        bucket = self._stats.setdefault(day, {})
        for eid in self.settings.get("lw_lights") or []:
            st = self.hass.states.get(eid)
            if st is None or st.state != "on":
                continue
            x = bucket.setdefault(eid, {"s": 0.0, "wh": 0.0})
            x["s"] = round(x.get("s", 0) + dt, 1)
            w = self._power(eid)
            if w is not None:
                x["wh"] = round(x.get("wh", 0) + w * dt / 3600, 3)
        for old in sorted(self._stats)[:-35]:
            self._stats.pop(old, None)

    def _power(self, eid: str) -> float | None:
        """Leistung der Leuchte: Messung am Gerät (W) oder eingetragene Leistung."""
        sensor = (self._device_sensors(eid) or {}).get("power")
        if sensor:
            st = self.hass.states.get(sensor)
            try:
                v = float(st.state) if st is not None else None
            except (TypeError, ValueError):
                v = None
            if v is not None:
                return v * 1000 if (st.attributes.get("unit_of_measurement") or "").lower() == "kw" else v
        w = (self.lights.get(eid) or {}).get("watt")
        return float(w) if w else None

    def _device_sensors(self, eid: str) -> dict:
        """Batterie, Funk und Leistung am Gerät der Leuchte (alle 10 Minuten neu gesucht)."""
        now = dt_util.utcnow().timestamp()
        if self._dev_cache is None or now - self._dev_cache[0] > 600:
            self._dev_cache = (now, {})
        found = self._dev_cache[1].get(eid)
        if found is None:
            found = {"battery": None, "signal": None, "power": None}
            reg = er.async_get(self.hass)
            entry = reg.async_get(eid)
            if entry is not None and getattr(entry, "device_id", None):
                for e in er.async_entries_for_device(reg, entry.device_id):
                    if e.domain not in ("sensor", "binary_sensor") or e.disabled_by is not None:
                        continue
                    dc = getattr(e, "device_class", None) or getattr(e, "original_device_class", None)
                    if dc == "battery" or (dc is None and ("battery" in e.entity_id or e.entity_id.endswith("low_bat"))):
                        found["battery"] = found["battery"] or e.entity_id
                    elif e.domain == "sensor" and (dc == "signal_strength" or e.entity_id.endswith(("_rssi", "_rssi_device", "_signal_strength", "_linkquality"))):
                        found["signal"] = found["signal"] or e.entity_id
                    elif e.domain == "sensor" and dc == "power":
                        found["power"] = found["power"] or e.entity_id
            self._dev_cache[1][eid] = found
        return found

    def _health(self, eid: str) -> dict:
        found = self._device_sensors(eid)
        out: dict[str, Any] = {}
        if found.get("battery"):
            st = self.hass.states.get(found["battery"])
            if st is not None:
                try:
                    out["battery"] = round(float(st.state))
                    out["battery_low"] = out["battery"] <= 20
                except (TypeError, ValueError):
                    out["battery_low"] = st.state == "on"  # binärer Sensor „Batterie schwach“
        if found.get("signal"):
            st = self.hass.states.get(found["signal"])
            try:
                val = float(st.state) if st is not None else None
            except (TypeError, ValueError):
                val = None
            if val is not None:
                unit = (st.attributes.get("unit_of_measurement") or "").lower()
                out["signal"] = round(val)
                out["weak"] = val < -85 if "db" in unit or val < 0 else val < 30
        fail = (self._rt.get(eid) or {}).get("fail")
        if fail:
            out["fail"] = fail
        return out

    def report(self) -> dict:
        """Wochenbericht: Brenndauer, Energie, von Hand je Leuchte; Tage; Vorschläge für die Profile."""
        today = dt_util.as_local(dt_util.utcnow()).date()
        days = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
        lights = {}
        for eid in self.settings.get("lw_lights") or []:
            secs = [((self._stats.get(d) or {}).get(eid) or {}).get("s", 0) for d in days]
            wh = sum(((self._stats.get(d) or {}).get(eid) or {}).get("wh", 0) for d in days)
            cut = (dt_util.utcnow() - timedelta(days=7)).timestamp()
            evs = [e for e in self._manual_ev if e.get("e") == eid and e.get("t", 0) >= cut]
            lights[eid] = {"hours": [round(x / 3600, 2) for x in secs], "week_h": round(sum(secs) / 3600, 1),
                           "today_h": round(secs[-1] / 3600, 1), "kwh": round(wh / 1000, 2) if wh else None,
                           "power": self._power(eid), "power_src": "sensor" if (self._device_sensors(eid) or {}).get("power") else ("set" if (self.lights.get(eid) or {}).get("watt") else None),
                           "manual": sum(1 for e in evs), "manual_on": sum(1 for e in evs if e.get("a") == "on"),
                           "manual_off": sum(1 for e in evs if e.get("a") == "off")}
        cut14 = (dt_util.utcnow() - timedelta(days=14)).timestamp()
        sugg = []
        for x in manual_suggestions([e for e in self._manual_ev if e.get("t", 0) >= cut14]):
            name = (self.profiles.get(x["profile"]) or {}).get("name") or x["profile"]
            sugg.append({**x, "kind": "manual", "profile_name": name,
                         "text": f"Profil „{name}“: {x['count']}× von Hand {'eingeschaltet' if x['action'] == 'on' else 'ausgeschaltet'}, "
                                 f"im Mittel {x['minutes']} Min. vor dem Plan – {x['minutes']} Min. früher {'einschalten' if x['action'] == 'on' else 'ausschalten'}?"})
        for eid, r in lights.items():
            prof = self.profile(eid)
            has_motion = bool(prof.get("motion")) or any(p.get("kind") == "motion" for p in (self._links.get(eid) or {}).get("peers", []))
            if r["week_h"] / 7 >= 5 and not has_motion and (self.lights.get(eid) or {}).get("auto", True) is not False:
                sugg.append({"kind": "usage", "light": eid, "profile": (self.lights.get(eid) or {}).get("profile") or "standard",
                             "text": f"{self._name(eid)} brennt im Mittel {r['week_h'] / 7:.1f} Std. am Tag – Bewegungsmelder oder früher aus statt Dauerlicht?".replace(".", ",", 1)})
        return {"days": days, "lights": lights, "suggestions": sugg,
                "health": {eid: h for eid in self.settings.get("lw_lights") or [] if (h := self._health(eid))}}

    async def _async_tick(self, _now=None) -> None:
        self._count_usage()
        if dt_util.utcnow().timestamp() >= self._links_next:
            await self.async_refresh_links()
        await self.async_evaluate()

    # ------------------------------------------------------------ Homematic: Direktverknüpfungen
    async def async_refresh_links(self, by: str | None = None) -> dict:
        """Verknüpfungen der Leuchten aus der CCU lesen (alle 6 Std. und auf Wunsch)."""
        self._links_next = dt_util.utcnow().timestamp() + 6 * 3600
        if not self.hmlinks.available:
            self._links, self._link_findings = {}, []
            return self.links_status()
        await self.hmlinks.async_refresh(list(self.settings.get("lw_lights") or []))
        self._analyze_links()
        # Einschaltdauer je Verknüpfung (für den Ablauftimer an der Kachel)
        for eid, info in self._links.items():
            a = self.hmlinks.addr(eid)
            for p in info["peers"]:
                for ch in p["channels"] or [1]:
                    ok, sec = await self.hmlinks.async_on_time(f"{p['address']}:{ch}", eid, a)
                    if ok:
                        p["on_time"], p["on_time_known"] = sec, True
                        break
        self._track()
        if by:
            self.log.add("settings", "Lichtwerk: Homematic-Verknüpfungen gelesen",
                         f"{sum(1 for i in self._links.values() if i['peers'])} Leuchten mit Verknüpfung · {by}", module="lichtwerk")
        return self.links_status()

    def _analyze_links(self) -> None:
        old = {f["text"] for f in self._link_findings}
        self._links, self._link_findings = {}, []
        for eid in self.settings.get("lw_lights") or []:
            a = self.hmlinks.addr(eid)
            if not a or a not in self.hmlinks.peers:
                continue
            merged: dict[str, dict] = {}
            own = False
            for p in self.hmlinks.peers.get(a) or []:
                pa, ch = split_peer(p)
                if pa == a:
                    own = True  # eigene Taster bzw. Kanäle des Geräts
                    continue
                dev = self.hmlinks.devices.get(pa) or {}
                if pa in merged:
                    if ch is not None and ch not in merged[pa]["channels"]:
                        merged[pa]["channels"].append(ch)
                    continue
                ents = [e for e in self.hmlinks.entities_of(pa) if e.startswith("binary_sensor.") or e.startswith("event.")]
                ot = next(((True, v) for (snd, le), v in self.hmlinks.on_times.items() if le == eid and snd.split(":")[0] == pa), (False, None))
                merged[pa] = {"on_time": ot[1], "on_time_known": ot[0], "address": pa, "name": dev.get("name") or pa, "model": dev.get("model"), "kind": sensor_kind(dev.get("model")),
                              "channels": [ch] if ch is not None else [], "entities": ents}
            info = {"peers": list(merged.values()), "own": own}
            self._links[eid] = info
            prof = self.profile(eid)
            auto = (self.lights.get(eid) or {}).get("auto", True) is not False
            for p in info["peers"]:
                if p["kind"] != "motion":
                    continue
                if auto and set(p["entities"]) & set(prof.get("motion") or []):
                    self._link_findings.append({"level": "warn", "light": eid,
                        "text": f"{self._name(eid)}: {p['name']} schaltet schon in der CCU – Lichtwerk schaltet bei Bewegung doppelt"})
                elif auto and any(prof.get(k) for k in ("on_sun", "on_lux", "on_time", "on_entity", "on_covers")):
                    self._link_findings.append({"level": "info", "light": eid,
                        "text": f"{self._name(eid)} wird in der CCU direkt von {p['name']} geschaltet – zusätzlich zum Profil „{prof.get('name')}“"})
        for f in self._link_findings:
            if f["text"] not in old:
                self.log.add("health", "Homematic-Verknüpfung", f["text"], module="lichtwerk")

    def links_status(self) -> dict:
        return {"available": self.hmlinks.available, "at": self.hmlinks.at, "error": self.hmlinks.error,
                "lights": self._links, "findings": self._link_findings}

    @callback
    def _on_house(self) -> None:
        self.hass.async_create_task(self.async_evaluate())

    @callback
    def subscribe(self, cb: Callable[[dict], None]) -> Callable[[], None]:
        self._subscribers.add(cb)

        @callback
        def unsub() -> None:
            self._subscribers.discard(cb)

        return unsub

    # ------------------------------------------------------------ Hilfen
    def profile(self, eid: str) -> dict[str, Any]:
        pid = (self.lights.get(eid) or {}).get("profile") or "standard"
        prof = self.profiles.get(pid) or self.profiles.get("standard") or next(iter(self.profiles.values()), {})
        return {**LW_PROFILE_DEFAULTS, **prof}

    def _name(self, eid: str | None) -> str:
        if not eid:
            return "–"
        custom = (self.lights.get(eid) or {}).get("name")
        if custom:
            return custom
        st = self.hass.states.get(eid)
        return (st.name if st is not None else None) or eid

    def _area(self, eid: str) -> str | None:
        try:
            ent = er.async_get(self.hass).async_get(eid)
            area_id = getattr(ent, "area_id", None)
            if not area_id and getattr(ent, "device_id", None):
                dev = dr.async_get(self.hass).async_get(ent.device_id)
                area_id = getattr(dev, "area_id", None)
            if area_id:
                area = ar.async_get(self.hass).async_get_area(area_id)
                return getattr(area, "name", None) or area_id
        except Exception:  # noqa: BLE001
            return None
        return None

    def _covers_near(self, eid: str) -> list[str]:
        area = self._area(eid)
        if not area:
            return []
        return [c for c in self.hass.states.async_entity_ids("cover") if self._area(c) == area] if hasattr(self.hass.states, "async_entity_ids") else []

    def _float(self, eid: str | None) -> float | None:
        st = self.hass.states.get(eid) if eid else None
        if st is None or st.state in BAD:
            return None
        try:
            return float(st.state)
        except (TypeError, ValueError):
            return None

    def _lux(self, prof: dict) -> float | None:
        eid = prof.get("lux_sensor") or self.settings.get("lw_lux_sensor")
        if not eid and hasattr(self.hass.states, "async_all"):
            for st in self.hass.states.async_all("sensor"):
                if st.attributes.get("device_class") == "illuminance" and st.state not in BAD:
                    eid = st.entity_id
                    break
        return self._float(eid)

    def _on(self, eid: str | None) -> bool | None:
        st = self.hass.states.get(eid) if eid else None
        if st is None or st.state in BAD:
            return None
        return st.state in ("on", "open", "detected", "home", "playing", "heat", "true")

    def _sun_fn(self, offset: int = 0):
        """Sonnenhöhe als Funktion der Minute (Ortszeit) an einem Tag – Standort aus Home Assistant."""
        day = dt_util.now().date() + timedelta(days=offset)
        if day in self._sunfn_cache:
            return self._sunfn_cache[day]
        fn = None
        try:
            from homeassistant.helpers.sun import get_astral_location  # noqa: PLC0415

            location, height = get_astral_location(self.hass)
            start = dt_util.start_of_local_day(day)
            memo: dict[float, float] = {}

            def elev(m: float) -> float:
                key = round(m, 3)
                if key not in memo:
                    memo[key] = float(location.solar_elevation(start + timedelta(minutes=m), height))
                return memo[key]

            fn = elev
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Sonnenstand nicht berechenbar: %s", err)
        self._sunfn_cache = {k: v for k, v in self._sunfn_cache.items() if k >= dt_util.now().date() - timedelta(days=1)} | {day: fn}
        return fn

    def _elev_now(self) -> float | None:
        st = self.hass.states.get(self.haus.settings.get("sun_entity") or "sun.sun")
        try:
            return float(st.attributes.get("elevation")) if st is not None else None
        except (TypeError, ValueError):
            return None

    def _events(self, eid: str, prof: dict, offset: int) -> list[tuple[float, str, str]]:
        """Feste Auslöser (Sonne, Uhrzeit) eines Tages; im Urlaub mit Simulation zufällig verschoben."""
        day = dt_util.now().date() + timedelta(days=offset)
        wd = self.haus.is_workday(day)
        allowed = day_allowed(prof, day.weekday(), (wd is False) if wd is not None else None)
        shift = 0
        if prof.get("simulate") and self.haus.vacation:
            shift = random.Random(f"{day.isoformat()}{eid}").randint(-30, 30)
        return day_events(prof, self._sun_fn(offset), allowed, shift)

    # ------------------------------------------------------------ Auswerten
    async def async_evaluate(self) -> None:
        now = dt_util.utcnow().timestamp()
        local = dt_util.now()
        now_min = local.hour * 60 + local.minute + local.second / 60
        today = local.date().isoformat()
        elev = self._elev_now()
        lights = [e for e in self.settings.get("lw_lights") or []]
        prev_min = self._last_min if self._last_day == today else None
        for eid in lights:
            try:
                await self._evaluate_light(eid, now, now_min, prev_min, today, elev)
            except Exception as err:  # noqa: BLE001 - eine Leuchte darf die anderen nicht aufhalten
                _LOGGER.warning("Lichtwerk: %s nicht auswertbar: %s", eid, err)
        self._last_min, self._last_day = now_min, today
        self._notify(now, lights)
        self._status = self._build_status(now_min, elev)
        for cb in list(self._subscribers):
            cb(self._status)

    async def _evaluate_light(self, eid: str, now: float, now_min: float, prev_min: float | None, today: str,
                              elev: float | None) -> None:
        cfg = self.lights.get(eid) or {}
        prof = self.profile(eid)
        rt = self._rt.setdefault(eid, {})
        st = self.hass.states.get(eid)
        ev_today, ev_yday = self._events(eid, prof, 0), self._events(eid, prof, -1)
        rt["plan"] = day_plan(ev_today, ev_yday)
        # Stand der festen Auslöser: beim ersten Mal (bzw. nach > 1 Tag) aus der Vorausrechnung, sonst Wechsel seit letzter Minute
        crossed = None
        if rt.get("latch") is None or not rt.get("latch_at") or now - float(rt["latch_at"]) > 86400:
            on, reason, _m = latched_at(ev_today, ev_yday, now_min)
            rt.update(latch=on, latch_reason=reason, latch_at=now)
        else:
            lo = prev_min if prev_min is not None else None
            if lo is None:  # Tageswechsel oder Neustart: Wechsel seit dem letzten Stand (über die Vorausrechnung)
                on, reason, _m = latched_at(ev_today, ev_yday, now_min)
                if on != rt.get("latch"):
                    crossed = (on, reason)
            else:
                for m, action, reason in ev_today:
                    if lo < m <= now_min:
                        crossed = (action == "on", reason)
        # lebende Auslöser: Helligkeit, Entität, Rollläden (Flanken)
        lux = self._lux(prof)
        if lux is not None:
            was = rt.get("lux_dark")
            if prof.get("on_lux") and lux < float(prof.get("lux_on") or 30) and was is False:
                crossed = (True, f"Helligkeit unter {float(prof.get('lux_on') or 30):.0f} lx")
            if prof.get("off_lux") and lux > float(prof.get("lux_off") or 80) and was is True:
                crossed = (False, f"Helligkeit über {float(prof.get('lux_off') or 80):.0f} lx")
            if lux < float(prof.get("lux_on") or 30):
                rt["lux_dark"] = True
            elif lux > float(prof.get("lux_off") or 80):
                rt["lux_dark"] = False
            elif was is None:
                rt["lux_dark"] = lux < float(prof.get("lux_on") or 30)
        ent = self._on(prof.get("entity"))
        if ent is not None and rt.get("ent") is not None and ent != rt.get("ent"):
            if ent and prof.get("on_entity"):
                crossed = (True, f"{self._name(prof.get('entity'))} an")
            elif not ent and prof.get("off_entity"):
                crossed = (False, f"{self._name(prof.get('entity'))} aus")
        rt["ent"] = ent
        if prof.get("on_covers"):
            covers = self._covers_near(eid)
            states = [self.hass.states.get(c) for c in covers]
            # Nur mit bekanntem Stand aller Rollläden: nach einem Neustart sind sie kurz „nicht verfügbar“ – das ist
            # kein „offen“, sonst gilt ihr erstes „geschlossen“ als Schließen und schaltet das Licht ein.
            if covers and all(x is not None and x.state not in BAD for x in states):
                closed = all(x.state == "closed" for x in states)
                if closed and rt.get("covers_closed") is False and now_min >= 720:
                    crossed = (True, "Rollläden geschlossen")
                rt["covers_closed"] = closed
        if crossed is not None:
            on, reason = crossed
            if on != rt.get("latch") or reason != rt.get("latch_reason"):
                rt.update(latch=on, latch_reason=reason, latch_at=now)
                if (rt.get("manual") or {}).get("until") is None:
                    rt["manual"] = None  # „bis zum nächsten Wechsel“
                self._save()
        man = rt.get("manual")
        if man and man.get("until") and now >= man["until"]:
            rt["manual"] = man = None
        # Bewegung
        motion = [m for m in prof.get("motion") or [] if m]
        motion_on = False
        if motion:
            moving = any(self._on(m) for m in motion)
            dark = True
            conds = []
            if prof.get("on_sun") and elev is not None:
                conds.append(elev < (float(prof.get("sun_on") or -1) if now_min >= 720 else float(prof.get("sun_off") or 1)))
            if prof.get("on_lux") and rt.get("lux_dark") is not None:
                conds.append(bool(rt.get("lux_dark")))
            if prof.get("motion_dark") and conds:
                dark = any(conds)
            if moving and (dark or rt.get("motion_active")):
                if not rt.get("motion_active"):
                    rt["manual"] = None  # Bewegung ist ein neuer Wechsel
                rt["motion_active"], rt["motion_last"] = True, now
            elif rt.get("motion_active") and now - float(rt.get("motion_last") or 0) > float(prof.get("motion_off") or 3) * 60:
                rt["motion_active"] = False
            motion_on = bool(rt.get("motion_active"))
        bypass_on = bool(self._on(prof.get("bypass"))) if prof.get("bypass") else False
        away, vacation = bool(self.haus.away), bool(self.haus.vacation)
        want, cause = decide(auto=cfg.get("auto", True) is not False, bypass_on=bypass_on,
                             bypass_action=prof.get("bypass_action") or "keep", manual=bool(rt.get("manual")),
                             away=away, away_action=prof.get("away") or "off",
                             simulating=bool(prof.get("simulate") and vacation),
                             motion_on=motion_on, motion_reason="Bewegung",
                             latched=bool(rt.get("latch")), latched_reason=rt.get("latch_reason"))
        params = light_params(prof, now_min, elev, lux)
        if (rt.get("manual") or {}).get("ccu") and cfg.get("auto", True) is not False and not bypass_on:
            cause = f"HmIP: {rt['manual']['ccu']} – Lichtwerk wartet"
        if want == "on" and params.get("mode"):
            cause = f"{cause} · {params['mode']}"
        rt.update(want=want, cause=cause, params=params, motion=motion_on)
        if st is None or st.state in BAD:
            rt.setdefault("bad_since", now)
            return
        rt.pop("bad_since", None)
        is_on = st.state == "on"
        if want == "on" and not is_on:
            await self._switch(eid, True, params, prof, cause)
        elif want == "off" and is_on:
            await self._switch(eid, False, params, prof, cause)
        elif want == "on" and is_on and rt.get("ours") and eid.startswith("light."):
            last = rt.get("sent") or {}
            night_change = (last.get("night") != params.get("night") and prof.get("night_adjust", True)) or (
                prof.get("scenes_on") and last.get("scene") != params.get("scene"))
            dyn_change = prof.get("dynamic") not in (None, "off") and (
                abs((last.get("brightness") or 0) - params["brightness"]) >= 8 or abs((last.get("kelvin") or 0) - (params.get("kelvin") or 0)) >= 300)
            if night_change or dyn_change:
                await self._switch(eid, True, params, prof, cause, adjust=True)

    async def _switch(self, eid: str, on: bool, params: dict, prof: dict, cause: str, adjust: bool = False) -> None:
        domain = eid.split(".")[0]
        ctx = self.haus.own_context("Lichtwerk")
        self._ctx = (self._ctx + [ctx.id])[-200:]
        rt = self._rt.setdefault(eid, {})
        if domain == "light":
            st = self.hass.states.get(eid)
            modes = set((st.attributes.get("supported_color_modes") if st else None) or [])
            feats = int((st.attributes.get("supported_features") if st else 0) or 0)
            data: dict[str, Any] = {"entity_id": eid}
            if on:
                if modes - {"onoff"}:
                    data["brightness_pct"] = max(1, min(100, int(params["brightness"])))
                if params.get("kelvin") and "color_temp" in modes:
                    data["color_temp_kelvin"] = int(params["kelvin"])
                elif params.get("rgb") and modes & {"hs", "xy", "rgb", "rgbw", "rgbww"}:
                    data["rgb_color"] = params["rgb"]
            trans = float(prof.get("transition_on" if on else "transition_off") or 0)
            if trans and feats & 32:
                data["transition"] = trans
            await self.hass.services.async_call("light", "turn_on" if on else "turn_off", data, context=ctx)
        else:
            await self.hass.services.async_call(domain if domain in ("switch", "input_boolean") else "homeassistant",
                                                "turn_on" if on else "turn_off", {"entity_id": eid}, context=ctx)
        async_call_later(self.hass, 30, lambda _n, eid=eid, on=on: self._check_switched(eid, on))
        rt["ours"] = on
        rt["sent"] = {"on": on, "brightness": params.get("brightness"), "kelvin": params.get("kelvin"), "night": params.get("night"), "scene": params.get("scene")}
        rt["switched_at"] = dt_util.utcnow().timestamp()
        if not adjust:
            self.log.add("light", f"{self._name(eid)} {'an' if on else 'aus'}", cause
                         + (f" · {params['brightness']} %" if on and domain == "light" else ""), module="lichtwerk")
        else:
            self.log.add("light", f"{self._name(eid)}: {params.get('mode') or 'Helligkeit'} – {params['brightness']} %", cause, module="lichtwerk")
        self._save()

    # ------------------------------------------------------------ Benachrichtigungen
    def _notify(self, now: float, lights: list[str]) -> None:
        if self.haus.away and not self.haus.vacation:
            on = [e for e in lights if (s := self.hass.states.get(e)) is not None and s.state == "on"]
            if on and self._away_since is None:
                self._away_since = now
            since = self._away_since
            if on and now - since >= float(self.settings.get("lw_away_min") or 30) * 60:
                self.haus.notify("lw_away", "light_away", "Licht an, niemand zu Hause",
                                 f"{', '.join(self._name(e) for e in on)} – brennt seit {int((now - since) // 60)} Min.")
            if not on:
                self._away_since = None
                self.haus.clear("lw_away")
        else:
            self._away_since = None
            self.haus.clear("lw_away")
        limit = float(self.haus.settings.get("notify_offline_min") or 15) * 60
        for eid in lights:
            rt = self._rt.get(eid) or {}
            if rt.get("bad_since") and now - rt["bad_since"] >= limit:
                self.haus.notify(f"lw_off:{eid}", "light_offline", "Leuchte nicht erreichbar",
                                 f"{self._name(eid)} meldet sich seit {int((now - rt['bad_since']) // 60)} Min. nicht")
            elif not rt.get("bad_since"):
                self.haus.clear(f"lw_off:{eid}")

    # ------------------------------------------------------------ Panel
    def _next(self, eid: str, prof: dict, now_min: float) -> dict | None:
        """Nächster fester Wechsel (heute oder morgen), der den Stand ändert."""
        rt = self._rt.get(eid) or {}
        cur = bool(rt.get("latch"))
        for offset, events in ((0, self._events(eid, prof, 0)), (1, self._events(eid, prof, 1))):
            for m, action, reason in events:
                if offset == 0 and m <= now_min:
                    continue
                if (action == "on") != cur:
                    return {"day": offset, "min": round(m), "action": action, "reason": reason}
        return None

    def _build_status(self, now_min: float, elev: float | None) -> dict:
        lights = {}
        for eid in self.settings.get("lw_lights") or []:
            st = self.hass.states.get(eid)
            rt = self._rt.get(eid) or {}
            prof = self.profile(eid)
            attrs = st.attributes if st is not None else {}
            bri = attrs.get("brightness")
            lights[eid] = {
                "name": self._name(eid), "area": self._area(eid), "profile": (self.lights.get(eid) or {}).get("profile") or "standard",
                "state": st.state if st is not None else None, "unavailable": st is None or st.state in BAD,
                "brightness": round(int(bri) / 2.55) if bri is not None and st and st.state == "on" else None,
                "kelvin": attrs.get("color_temp_kelvin"), "rgb": attrs.get("rgb_color"),
                "modes": attrs.get("supported_color_modes"),
                "auto": (self.lights.get(eid) or {}).get("auto", True) is not False,
                "want": rt.get("want"), "cause": rt.get("cause"), "latch": rt.get("latch"),
                "manual": ({"since": dt_util.utc_from_timestamp(rt["manual"]["since"]).isoformat(),
                            "until": dt_util.utc_from_timestamp(rt["manual"]["until"]).isoformat() if rt["manual"].get("until") else None}
                           if rt.get("manual") else None),
                "motion": bool(rt.get("motion")), "night": bool((rt.get("params") or {}).get("night")),
                "links": self._links.get(eid), "ccu": (rt.get("manual") or {}).get("ccu"),
                "health": self._health(eid) or None, "power": self._power(eid),
                "params": rt.get("params"), "plan": rt.get("plan") or [],
                "night_window": [prof.get("night_from"), prof.get("night_to")] if prof.get("night") else None,
                "next": self._next(eid, prof, now_min),
                "switched_at": dt_util.utc_from_timestamp(rt["switched_at"]).isoformat() if rt.get("switched_at") else None,
                "since": st.last_changed.isoformat() if st is not None and getattr(st, "last_changed", None) else None,
            }
        for eid, x in lights.items():
            x["off"] = self._off_timer(eid, x) if x["state"] == "on" else None
        on = [e for e, x in lights.items() if x["state"] == "on"]
        nxt = sorted((x["next"]["day"], x["next"]["min"], e) for e, x in lights.items() if x.get("next"))
        return {"lights": lights, "on": len(on), "total": len(lights), "elevation": elev,
                "next": ({**lights[nxt[0][2]]["next"], "entity_id": nxt[0][2],
                          "count": sum(1 for n in nxt if n[:2] == nxt[0][:2])} if nxt else None),
                "manual": sum(1 for x in lights.values() if x["manual"] and not x["ccu"]), "away": bool(self.haus.away),
                "links": self.links_status(), "report": self.report()}

    def _off_timer(self, eid: str, x: dict) -> dict | None:
        """Wann geht die Leuchte wieder aus? Bewegung im Profil (Nachlaufzeit) oder HmIP-Verknüpfung (Einschaltdauer der CCU).
        {"at": ISO} = Ablauf, {"while": Sekunden} = solange Bewegung, danach so lange."""
        rt = self._rt.get(eid) or {}
        if x.get("ccu"):
            peer = next((p for p in (self._links.get(eid) or {}).get("peers", []) if p["name"] == x["ccu"]), None)
            if not peer:
                return None
            learned = self.learned_off(eid, peer)
            dur = learned if learned is not None else peer.get("on_time")
            if not dur:
                return None
            sts = [st for e in peer.get("entities") or [] if (st := self.hass.states.get(e)) is not None and st.state in ("on", "off")]
            if any(st.state == "on" for st in sts) or not sts:
                return {"while": dur, "src": "HmIP", "learned": learned is not None}
            last = max(st.last_changed.timestamp() for st in sts)
            return {"at": dt_util.utc_from_timestamp(max(last + dur, dt_util.utcnow().timestamp())).isoformat(), "src": "HmIP",
                    "learned": learned is not None}
        if x.get("motion") and x.get("auto") and str(x.get("cause") or "").startswith("Bewegung"):
            prof = self.profile(eid)
            off = float(prof.get("motion_off") or 3) * 60
            if any(self._on(m) for m in prof.get("motion") or []):
                return {"while": off, "src": "Bewegung"}
            return {"at": dt_util.utc_from_timestamp(float(rt.get("motion_last") or 0) + off).isoformat(), "src": "Bewegung"}
        return None

    def status(self) -> dict:
        if not self._status:
            local = dt_util.now()
            self._status = self._build_status(local.hour * 60 + local.minute, self._elev_now())
        return self._status

    # ------------------------------------------------------------ Änderungen
    async def async_save_settings(self, settings: dict[str, Any], by: str | None = None) -> None:
        settings = {k: v for k, v in settings.items() if k in LW_KEYS}
        changed = [k for k, v in settings.items() if self.settings.get(k) != v]
        if not changed:
            return
        log_settings(self.log, settings, changed, by, old=self.settings, module="lichtwerk")
        added = set(settings.get("lw_lights") or []) - set(self.settings.get("lw_lights") or [])
        self.settings.update(settings)
        for eid in added:
            self.lights.setdefault(eid, {"profile": "standard", "auto": True})
        if added:
            self._links_next = 0.0
        self._save()
        self._track()
        await self.async_evaluate()

    async def async_save_light(self, eid: str, cfg: dict[str, Any], by: str | None = None) -> None:
        old = self.lights.get(eid) or {}
        self.lights[eid] = {**old, **cfg}
        if eid not in (self.settings.get("lw_lights") or []):
            self.settings["lw_lights"] = list(self.settings.get("lw_lights") or []) + [eid]
        if cfg.get("profile") and cfg.get("profile") != old.get("profile"):
            self._rt.pop(eid, None)  # neues Profil: Stand neu aus der Vorausrechnung
        if eid not in self._links:
            self._links_next = 0.0
        elif self.hmlinks.peers:
            self._analyze_links()
        prof_name = (self.profiles.get(self.lights[eid].get("profile") or "standard") or {}).get("name")
        active = self.lights[eid].get("auto", True) is not False
        if "auto" in cfg and (old.get("auto", True) is not False) != active and set(cfg) <= {"auto"}:
            self.log.add("settings", f"{self._name(eid)}: Profil „{prof_name}“ {'aktiv' if active else 'aus'}",
                         ("Lichtwerk schaltet wieder nach dem Profil" if active else "Lichtwerk zeigt das Licht nur noch an")
                         + (f" · {by}" if by else ""), module="lichtwerk")
        else:
            self.log.add("settings", f"Lichtwerk: {self._name(eid)} geändert", f"Profil {prof_name}"
                         + ("" if active else " (aus)") + (f" · {by}" if by else ""), module="lichtwerk")
        self._save()
        self._track()
        await self.async_evaluate()

    async def async_remove_light(self, eid: str, by: str | None = None) -> None:
        self.settings["lw_lights"] = [e for e in self.settings.get("lw_lights") or [] if e != eid]
        self.lights.pop(eid, None)
        self._rt.pop(eid, None)
        self.log.add("settings", f"Lichtwerk: {self._name(eid)} entfernt", by, module="lichtwerk")
        self._save()
        self._track()
        await self.async_evaluate()

    async def async_save_profile(self, pid: str | None, prof: dict[str, Any], by: str | None = None) -> str:
        if not pid:
            base = "".join(c if c.isalnum() else "_" for c in str(prof.get("name") or "profil").lower())[:30] or "profil"
            pid, n = base, 2
            while pid in self.profiles:
                pid, n = f"{base}_{n}", n + 1
        old = self.profiles.get(pid)
        self.profiles[pid] = {**LW_PROFILE_DEFAULTS, **(old or {}), **prof}
        changed = [k for k in prof if (old or {}).get(k) != prof[k]]
        self.log.add("settings", f"Lichtwerk: Profil „{self.profiles[pid].get('name')}“ {'geändert' if old else 'angelegt'}",
                     (", ".join(changed[:6]) + (" …" if len(changed) > 6 else "") if old else None) or (by or None), module="lichtwerk")
        for eid, cfg in self.lights.items():
            if (cfg.get("profile") or "standard") == pid:
                self._rt.get(eid, {}).pop("latch", None)  # Auslöser geändert: Stand neu berechnen
        if self.hmlinks.peers:
            self._analyze_links()
        self._save()
        self._track()
        await self.async_evaluate()
        return pid

    async def async_delete_profile(self, pid: str, replace_with: str | None = None, by: str | None = None) -> None:
        if pid not in self.profiles or len(self.profiles) <= 1:
            return
        name = self.profiles[pid].get("name")
        self.profiles.pop(pid)
        target = replace_with if replace_with in self.profiles else next(iter(self.profiles))
        for cfg in self.lights.values():
            if (cfg.get("profile") or "standard") == pid:
                cfg["profile"] = target
        self.log.add("settings", f"Lichtwerk: Profil „{name}“ gelöscht", f"Leuchten nutzen jetzt „{self.profiles[target].get('name')}“", module="lichtwerk")
        self._save()
        await self.async_evaluate()

    async def async_command(self, eids: list[str], action: str, brightness: int | None = None, by: str | None = None,
                            kelvin: int | None = None, rgb: list[int] | None = None) -> None:
        """Von Hand schalten (Panel). Gilt als „von Hand“ – außer „resume“: Automatik übernimmt wieder."""
        for eid in eids:
            rt = self._rt.setdefault(eid, {})
            prof = self.profile(eid)
            if action == "resume":
                rt["manual"] = None
                self.log.add("light", f"{self._name(eid)}: Automatik übernimmt", by, module="lichtwerk")
                continue
            until = dt_util.utcnow().timestamp() + float(prof.get("manual_hours") or 2) * 3600 if prof.get("manual_hold") == "hours" else None
            rt["manual"] = {"since": dt_util.utcnow().timestamp(), "until": until, "state": action}
            rt["ours"] = False
            domain = eid.split(".")[0]
            ctx = self.haus.own_context("Lichtwerk")
            self._ctx = (self._ctx + [ctx.id])[-200:]
            if action == "off":
                svc, data = "turn_off", {"entity_id": eid}
            else:
                svc, data = "turn_on", {"entity_id": eid}
                if brightness is not None and domain == "light":
                    data["brightness_pct"] = max(1, min(100, int(brightness)))
                if domain == "light" and rgb:
                    data["rgb_color"] = [max(0, min(255, int(x))) for x in rgb[:3]]
                elif domain == "light" and kelvin:
                    data["color_temp_kelvin"] = int(kelvin)
            await self.hass.services.async_call(domain if domain in LIGHT_DOMAINS else "homeassistant", svc, data, context=ctx)
            self.log.add("light", f"{self._name(eid)}: von Hand {'aus' if action == 'off' else 'an'}"
                         + (f" ({brightness} %)" if brightness is not None and action != "off" else "")
                         + (f" · Farbe {'#%02x%02x%02x' % tuple(rgb[:3])}" if rgb and action != "off" else f" · {kelvin} K" if kelvin and action != "off" else ""),
                         f"im Panel · Automatik wartet {'bis zum nächsten Wechsel' if not until else 'bis ' + dt_util.as_local(dt_util.utc_from_timestamp(until)).strftime('%H:%M')}"
                         + (f" · {by}" if by else ""), module="lichtwerk")
        self._save()
        await self.async_evaluate()

    def automations(self) -> list[dict]:
        """Bestehende Licht-Automationen (zum Abschalten nach der Übernahme in Lichtwerk)."""
        out = []
        if not hasattr(self.hass.states, "async_all"):
            return out
        words = ("licht", "light", "lampe", "leuchte", "nachtlicht", "weihnacht")
        for st in self.hass.states.async_all("automation"):
            name = (st.name or st.entity_id).lower()
            if any(w in name for w in words):
                out.append({"entity_id": st.entity_id, "name": st.name, "state": st.state})
        return out

    async def async_automation_off(self, eid: str, by: str | None = None) -> None:
        await self.hass.services.async_call("automation", "turn_off", {"entity_id": eid})
        self.log.add("settings", f"Automation „{self._name(eid)}“ abgeschaltet", f"übernommen von Lichtwerk{f' · {by}' if by else ''}", module="lichtwerk")
