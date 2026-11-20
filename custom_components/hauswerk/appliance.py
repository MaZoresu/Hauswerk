"""Kraftwerk: Fertigerkennung in Home Assistant – Sensoren beobachten, Gelerntes speichern, einmal melden.

Die Erkennung und das Lernen selbst stehen in appliance_logic.py (ohne Home Assistant, testbar).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Callable

from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .appliance_logic import KEEP_RUNS, TYPES, Detector, to_watt

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = "hauswerk.geraete"


class Appliances:
    """Geräte in Home Assistant: Sensoren beobachten, Zustand dauerhaft speichern, einmal melden."""

    def __init__(self, hass: HomeAssistant, log, haus, get_config: Callable[[], list[dict]]) -> None:
        self.hass = hass
        self.log = log
        self.haus = haus
        self._config = get_config
        self._store: Store = Store(hass, 1, STORAGE_KEY)
        self.det: dict[str, Detector] = {}
        self.sent: dict[str, list[str]] = {}       # Durchlauf-ID → Kanäle, an die schon gemeldet wurde
        self._stored: dict = {}
        self._unsubs: list[Callable] = []
        self._listeners: set[Callable[[], None]] = set()

    async def async_load(self) -> None:
        self._stored = await self._store.async_load() or {}
        self.sent = self._stored.get("sent") or {}

    def _data(self) -> dict:
        return {"devices": {k: d.dump() for k, d in self.det.items()}, "sent": dict(list(self.sent.items())[-100:])}

    def _save(self, now: bool = False) -> None:
        if now:
            self.hass.async_create_task(self._store.async_save(self._data()))
        else:
            self._store.async_delay_save(self._data, 10)

    @callback
    def async_setup(self) -> None:
        """(Neu) aufbauen, z. B. nach geänderten Einstellungen. Gelerntes bleibt."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs = []
        cfg = {c["id"]: c for c in self._config()}
        stored = (self._stored.get("devices") or {})
        old = self.det
        self.det = {}
        for dev_id, c in cfg.items():
            det = old.get(dev_id)
            if det is None or det.kind != c.get("type"):
                det = Detector(c.get("type") or "sonstiges", stored.get(dev_id) if det is None else det.dump())
            self.det[dev_id] = det
        watch = [e for c in cfg.values() for e in (c.get("power"), c.get("door"), c.get("status")) if e]
        if watch:
            self._unsubs.append(async_track_state_change_event(self.hass, watch, self._on_state))
        self._unsubs.append(async_track_time_interval(self.hass, self._on_tick, timedelta(seconds=30)))
        now = dt_util.utcnow().timestamp()
        for dev_id, c in cfg.items():
            st = self.hass.states.get(c.get("power") or "")
            self._feed(dev_id, c, st, now)
        self._save()

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs = []

    def subscribe(self, cb: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(cb)
        return lambda: self._listeners.discard(cb)

    def _changed(self) -> None:
        for cb in list(self._listeners):
            cb()

    def _cfg(self, dev_id: str) -> dict | None:
        return next((c for c in self._config() if c["id"] == dev_id), None)

    @callback
    def _on_state(self, event: Event) -> None:
        entity_id = event.data["entity_id"]
        new: State | None = event.data.get("new_state")
        now = dt_util.utcnow().timestamp()
        for c in self._config():
            dev_id = c["id"]
            if dev_id not in self.det:
                continue
            if entity_id == c.get("power"):
                self._feed(dev_id, c, new, now)
            elif entity_id == c.get("door") and new is not None and new.state == "on":
                self.det[dev_id].door_open(now)
                self._events(dev_id, c)
            elif entity_id == c.get("status") and new is not None:
                done_vals = [v.strip().lower() for v in (c.get("status_done") or []) if v.strip()]
                if new.state.lower() in done_vals:
                    self.det[dev_id].status_done(now)
                    self._events(dev_id, c)

    @callback
    def _on_tick(self, _now: datetime) -> None:
        now = dt_util.utcnow().timestamp()
        for c in self._config():
            det = self.det.get(c["id"])
            if det is not None:
                before = det.state
                det.tick(now)
                self._events(c["id"], c, changed=before != det.state)

    def _feed(self, dev_id: str, c: dict, st: State | None, now: float) -> None:
        det = self.det[dev_id]
        watt = None if st is None else to_watt(st.state, st.attributes.get("unit_of_measurement"))
        before = det.state
        det.feed(now, watt)
        self._events(dev_id, c, changed=before != det.state)

    def _events(self, dev_id: str, c: dict, changed: bool = False) -> None:
        det = self.det[dev_id]
        events, det.events = det.events, []
        name = c.get("name") or TYPES[det.kind]["label"]
        for kind, info in events:
            if kind == "start":
                self.log.add("appliance", f"{name} läuft", "Durchlauf erkannt" + (" · Lernphase" if det.model["learning"] else ""), module="kraftwerk")
            elif kind == "discard":
                self.log.add("appliance", f"{name}: kein Durchlauf",
                             f"nur {round(info['dur'] / 60)} Min. / {info['wh']:.0f} Wh – nicht gemeldet", module="kraftwerk")
            elif kind == "done":
                self._announce(dev_id, c, info)
        if events or changed:
            self._save(now=any(k == "done" for k, _ in events))
            self._changed()

    def _announce(self, dev_id: str, c: dict, rec: dict) -> None:
        """Fertigmeldung: je Durchlauf und Kanal höchstens einmal – auch über Neustarts hinweg."""
        name = c.get("name") or TYPES[self.det[dev_id].kind]["label"]
        dur = rec["dur"]
        text = f"{name} ist fertig – {dur // 3600}:{(dur % 3600) // 60:02d} Std., {rec['wh'] / 1000:.2f} kWh".replace(".", ",")
        if rec.get("why") and rec["why"] not in ("Ruhe",):
            text += f" ({rec['why']})"
        run_key = f"{dev_id}:{rec['id']}"
        done = set(self.sent.get(run_key) or [])
        channels = self.channels(c)
        new = [ch for ch in channels if ch not in done]
        self.sent[run_key] = sorted(done | set(new))
        self._save(now=True)  # erst merken, dann senden: kein Doppel nach Absturz/Neustart
        sent = self.haus.send(new, f"{name} fertig", text, bool(c.get("important")), key=f"geraet_{dev_id}") if new else []
        new = [self.haus.channel_name(ch) for ch in sent]
        how = f"gesendet an {', '.join(new)}" if new else ("schon gemeldet" if channels else "keine Kanäle gewählt")
        self.log.add("appliance", f"{name} fertig", f"{text} · {how}", module="kraftwerk")

    @staticmethod
    def channels(c: dict) -> list[str]:
        """Kanäle eines Geräts (gemeinsame Benachrichtigung); alte Einträge (nur Dienstname, notify_ha) übernehmen."""
        out = [ch if ":" in ch or ch == "ha" else f"svc:{ch}" for ch in c.get("notify") or []]
        if c.get("notify_ha") and "ha" not in out:
            out.append("ha")
        return out

    # ------------------------------------------------------------ Panel
    def status(self) -> dict:
        now = dt_util.utcnow().timestamp()
        return {dev_id: det.status(now) for dev_id, det in self.det.items()}

    async def async_action(self, dev_id: str, action: str, by: str | None = None) -> dict:
        det = self.det.get(dev_id)
        c = self._cfg(dev_id)
        if det is None or c is None:
            return {"ok": False, "error": "Gerät nicht gefunden"}
        now = dt_util.utcnow().timestamp()
        if action == "learn_history":
            n = await self._async_learn_history(dev_id, c)
            return {"ok": True, "runs": n}
        text = det.correct(action, now)
        if text is None:
            return {"ok": False, "error": "Passt gerade nicht zum Zustand"}
        name = c.get("name") or TYPES[det.kind]["label"]
        if action == "ack" and "ha" in self.channels(c):
            self.hass.async_create_task(self.haus._async_call(
                "persistent_notification", "dismiss", {"notification_id": self.haus._ha_id(f"geraet_{dev_id}")}))
        if action != "ack":
            self.log.add("appliance", f"{name}: {text.split(' – ')[0]}", text + (f" · {by}" if by else ""), module="kraftwerk")
        self._events(dev_id, c, changed=True)
        self._save(now=True)
        return {"ok": True, "text": text}

    async def _async_learn_history(self, dev_id: str, c: dict, days: int = 10) -> int:
        """Aus dem Verlauf von Home Assistant lernen: die letzten Tage nachspielen – ohne Meldungen."""
        try:
            from homeassistant.components.recorder import get_instance, history
        except ImportError:
            return 0
        end = dt_util.utcnow()
        start = end - timedelta(days=days)
        entity = c.get("power")
        try:
            states = await get_instance(self.hass).async_add_executor_job(
                history.state_changes_during_period, self.hass, start, end, entity, True, False)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Verlauf von %s nicht lesbar: %s", entity, err)
            return 0
        sim = Detector(c.get("type") or "sonstiges", {"confirm": self.det[dev_id].confirm, "false": self.det[dev_id].false})
        unit = (self.hass.states.get(entity).attributes.get("unit_of_measurement") if self.hass.states.get(entity) else "W")
        for st in states.get(entity, []):
            sim.feed(st.last_updated.timestamp(), to_watt(st.state, unit))
            sim.events = []
        sim.tick(end.timestamp())
        det = self.det[dev_id]
        known = {r["id"] for r in det.runs}
        new = [r for r in sim.runs if r["id"] not in known and not any(abs(r["start"] - k["start"]) < 600 for k in det.runs)]
        det.runs = sorted(det.runs + new, key=lambda r: r["start"])[-KEEP_RUNS:]
        det.quiet_levels = (sim.quiet_levels + det.quiet_levels)[-50:]
        det.intervals = (sim.intervals + det.intervals)[-100:]
        for rec in new:  # nachgespielte Durchläufe nie melden
            self.sent[f"{dev_id}:{rec['id']}"] = ["history"]
        det._learn()
        name = c.get("name") or TYPES[det.kind]["label"]
        self.log.add("appliance", f"{name}: aus dem Verlauf gelernt", f"{len(new)} Durchläufe der letzten {days} Tage", module="kraftwerk")
        self._save(now=True)
        self._changed()
        return len(new)
