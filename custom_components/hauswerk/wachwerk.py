"""Wachwerk: Sicherheit im Haus – Rauch- und CO-Melder, Wassermelder, Unwetterwarnungen, Türen und Tore,
Alarmanlage (z. B. Alarmo), Klingel und der Check beim Verlassen des Hauses.

Wachwerk schaltet selbst nur im Ernstfall: Bei Rauch oder CO fahren die Rollläden von Rollwerk hoch (Fluchtweg)
und die Leuchten von Lichtwerk gehen an. Alles Weitere sind Meldungen (Benachrichtigungen › Wachwerk).
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MODULE_HEATING, MODULE_LIGHT, MODULE_SHUTTER, SECURITY_STORAGE_KEY
from .core import Haus
from .log import Protokoll, log_settings

BAD = ("unavailable", "unknown", None)
WINDOW_OPEN = ("on", "open", "opening", "tilted")

WW_DEFAULTS: dict[str, Any] = {
    "ww_smoke": [],         # Rauchmelder (leer = automatisch)
    "ww_co": [],            # CO- und Gasmelder
    "ww_water": [],         # Wassermelder
    "ww_warn": [],          # amtliche Warnungen (z. B. NINA, DWD)
    "ww_doors": [],         # Haustür, Terrassentür, Garagentor …
    "ww_alarm": None,       # Alarmanlage (alarm_control_panel, z. B. Alarmo)
    "ww_bell": None,        # Klingel (event mit Geräteklasse doorbell)
    "ww_camera": None,      # Kamera für das Bild bei Klingel und Alarm
    "ww_fire_covers": True,  # bei Rauch/CO: Rollläden hoch (Fluchtweg)
    "ww_fire_lights": True,  # bei Rauch/CO: Licht an
    "ww_leave_check": True,  # beim Verlassen: was ist noch offen bzw. an?
    "ww_door_min": 30,       # Tür/Tor lange offen nach … Min.
}
WW_KEYS = set(WW_DEFAULTS)


class Wachwerk:
    """Sicherheit: Melder, Warnungen, Türen, Alarmanlage, Klingel."""

    def __init__(self, hass: HomeAssistant, log: Protokoll, haus: Haus) -> None:
        self.hass = hass
        self.log = log
        self.haus = haus
        self._store: Store = Store(hass, 1, SECURITY_STORAGE_KEY)
        self.settings: dict[str, Any] = dict(WW_DEFAULTS)
        self._persist: dict[str, Any] = {}
        self._unsubs: list = []
        self._state_unsub = None
        self._active: set[str] = set()
        self._was_away: bool | None = None
        self._ctx = Context()
        haus.extra_status["wachwerk"] = self.status

    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        self.settings.update({k: v for k, v in (stored.get("settings") or {}).items() if k in WW_KEYS})
        self._persist = stored.get("persist") or {}

    async def _act_close(self, data: dict, by: str) -> None:
        """Knopf „Schließen“ (Garagentor u. Ä.)."""
        eid = data.get("eid")
        if eid and eid.startswith("cover."):
            await self.hass.services.async_call("cover", "close_cover", {"entity_id": eid}, blocking=True)
            self.log.add("security", f"{self._name(eid)} wird geschlossen", by, module="wachwerk")

    async def async_start(self) -> None:
        self.haus.action_handlers["ww_close"] = self._act_close
        self._unsubs.append(async_track_time_interval(self.hass, self._async_tick, timedelta(minutes=1)))
        self._unsubs.append(self.haus.subscribe(self._on_house))
        self._was_away = bool(getattr(self.haus, "away", False))
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

    def _save(self) -> None:
        self._store.async_delay_save(self._data, 5)

    def _data(self) -> dict[str, Any]:
        return {"settings": self.settings, "persist": self._persist}

    async def async_save_settings(self, settings: dict[str, Any], by: str | None = None) -> None:
        settings = {k: v for k, v in settings.items() if k in WW_KEYS}
        changed = [k for k, v in settings.items() if self.settings.get(k) != v]
        if not changed:
            return
        log_settings(self.log, settings, changed, by, module="wachwerk", old=self.settings)
        self.settings.update(settings)
        self._save()
        self._track()
        await self.async_evaluate()

    # ------------------------------------------------------------ Entitäten
    def _ids(self, domain: str) -> list[str]:
        ids = getattr(self.hass.states, "async_entity_ids", None)
        return sorted(ids(domain)) if ids else []

    def _name(self, entity_id: str | None) -> str:
        st = self.hass.states.get(entity_id) if entity_id else None
        return (st.name if st is not None and getattr(st, "name", None) else None) or (entity_id or "–")

    def _scan(self, domain: str, test) -> list[str]:
        out = []
        for eid in self._ids(domain):
            st = self.hass.states.get(eid)
            if st is None:
                continue
            hay = f"{eid} {getattr(st, 'name', '') or ''}".lower()
            if test(hay, st.attributes.get("device_class")):
                out.append(eid)
        return out

    def entities(self) -> dict[str, Any]:
        """Alle Geräte von Wachwerk: gewählt oder automatisch gefunden."""
        s = self.settings
        skip = ("batter", "mute", "life", "duty", "sabotage", "tamper", "rssi")

        def pick(key: str, auto) -> list[str]:
            return [e for e in s.get(key) or [] if e] or auto()

        smoke = pick("ww_smoke", lambda: self._scan("binary_sensor", lambda h, dc: (dc == "smoke" or (dc is None and (h.split(" ")[0].endswith(("_rauch", "_smoke")))))
                                                    and not any(w in h for w in skip)))
        co = pick("ww_co", lambda: self._scan("binary_sensor", lambda h, dc: dc in ("carbon_monoxide", "gas") and not any(w in h for w in skip)))
        water = pick("ww_water", lambda: self._scan("binary_sensor", lambda h, dc: dc == "moisture" and not any(
            w in h for w in ("regen", "rain", "wetter", "weather", "boden", "soil", "irrigation", *skip))))
        warn = pick("ww_warn", lambda: self._scan("binary_sensor", lambda h, dc: dc == "safety" and any(w in h for w in ("warnung", "warning", "nina", "dwd"))))
        doors = pick("ww_doors", lambda: self._scan("binary_sensor", lambda h, dc: dc in ("door", "garage_door") and not any(
            w in h for w in ("geschirr", "spül", "dishwasher", "wasch", "trockner", "kühl", "fridge", "oven", "ofen", *skip)))
            + self._scan("cover", lambda h, dc: dc in ("garage", "gate")))
        alarm = s.get("ww_alarm") or next(iter(self._ids("alarm_control_panel")), None)
        bells = self._scan("event", lambda h, dc: dc == "doorbell" or "klingel" in h or "doorbell" in h)
        bell = s.get("ww_bell") or next((b for b in bells if "taster" in b or "doorbell" in b), bells[0] if bells else None)
        return {"smoke": smoke, "co": co, "water": water, "warn": warn, "doors": doors, "alarm": alarm, "bell": bell,
                "camera": s.get("ww_camera"), "sirens": self._ids("siren")}

    def _track(self) -> None:
        if self._state_unsub:
            self._state_unsub()
        e = self.entities()
        ids = [*e["smoke"], *e["co"], *e["water"], *e["warn"], *e["doors"], *(x for x in (e["alarm"], e["bell"]) if x)]
        self._state_unsub = async_track_state_change_event(self.hass, ids, self._on_state) if ids else None

    @callback
    def _on_state(self, event) -> None:
        new = event.data.get("new_state")
        old = event.data.get("old_state")
        e = self.entities()
        if new is not None and new.entity_id == e.get("bell") and old is not None and old.state not in BAD and new.state not in BAD \
                and new.state != old.state:
            self._ring(new)
        self.hass.async_create_task(self.async_evaluate())

    @callback
    def _on_house(self) -> None:
        away = bool(getattr(self.haus, "away", False))
        if self._was_away is False and away and self.settings.get("ww_leave_check", True):
            self.leave_check(notify=True)
        self._was_away = away

    async def _async_tick(self, _now=None) -> None:
        await self.async_evaluate()

    # ------------------------------------------------------------ Klingel
    def _ring(self, st) -> None:
        now = dt_util.utcnow()
        self._persist["bell_last"] = now.isoformat()
        rings = [r for r in self._persist.get("bell_log") or [] if now.timestamp() - dt_util.parse_datetime(r).timestamp() < 7 * 86400]
        self._persist["bell_log"] = rings[-199:] + [now.isoformat()]
        cam = self.settings.get("ww_camera")
        self.haus.notify(f"ww_bell_{int(now.timestamp())}", "bell", "Es hat geklingelt",
                         "an der Haustür" + ("" if not getattr(self.haus, "away", False) else " – niemand zu Hause"),
                         image=f"/api/camera_proxy/{cam}" if cam else None,
                         actions=[{"title": "Wachwerk öffnen", "uri": "/hauswerk/wachwerk/sicherheit"}])
        self.log.add("security", "Es hat geklingelt", self._name(st.entity_id), module="wachwerk")
        self._save()

    # ------------------------------------------------------------ Auswertung
    def _on(self, eid: str) -> bool:
        st = self.hass.states.get(eid)
        return st is not None and st.state in ("on", "open", "opening", "detected")

    async def async_evaluate(self) -> None:
        e = self.entities()
        now = dt_util.utcnow().timestamp()
        # Rauch / CO: Ernstfall
        fire = [x for x in e["smoke"] + e["co"] if self._on(x)]
        if fire and "fire" not in self._active:
            self._active.add("fire")
            kind = "CO-Alarm" if all(x in e["co"] for x in fire) else "Rauchalarm"
            names = ", ".join(self._name(x) for x in fire)
            done = await self._async_fire_actions()
            self.haus.notify("ww_fire", "smoke", f"{kind}!", f"{names}{' – ' + done if done else ''}", image=self._image())
            self.log.add("security", kind, f"{names}{' · ' + done if done else ''}", module="wachwerk")
        elif not fire and "fire" in self._active:
            self._active.discard("fire")
            self.haus.clear("ww_fire")
            self.log.add("security", "Rauch- bzw. CO-Alarm vorbei", None, module="wachwerk")
        # Wasser
        wet = [x for x in e["water"] if self._on(x)]
        if wet:
            self.haus.notify("ww_water", "water", "Wasser erkannt!", ", ".join(self._name(x) for x in wet))
            if "water" not in self._active:
                self.log.add("security", "Wasser erkannt", ", ".join(self._name(x) for x in wet), module="wachwerk")
            self._active.add("water")
        else:
            if "water" in self._active:
                self.log.add("security", "Wassermelder wieder trocken", None, module="wachwerk")
            self._active.discard("water")
            self.haus.clear("ww_water")
        # amtliche Warnungen
        for x in e["warn"]:
            key = f"ww_warn:{x}"
            if self._on(x):
                title, text = self._warn_text(x)
                self.haus.notify(key, "warn", title, text)
                if key not in self._active:
                    self.log.add("security", title, text, module="wachwerk")
                self._active.add(key)
            else:
                self._active.discard(key)
                self.haus.clear(key)
        # Türen und Tore lange offen
        lim = float(self.settings.get("ww_door_min") or 30) * 60
        for x in e["doors"]:
            st = self.hass.states.get(x)
            key = f"ww_door:{x}"
            if st is not None and st.state in WINDOW_OPEN and now - st.last_changed.timestamp() >= lim:
                self.haus.notify(key, "door", f"{self._name(x)} offen", f"seit {int((now - st.last_changed.timestamp()) // 60)} Min.",
                                 actions=([{"title": "Schließen", "do": "ww_close", "data": {"eid": x}}] if x.startswith("cover.") else [])
                                 + [{"title": "In 30 Min.", "do": "snooze", "minutes": 30}, {"title": "Gesehen", "do": "ack"}])
            else:
                self.haus.clear(key)

    def _warn_text(self, eid: str) -> tuple[str, str]:
        st = self.hass.states.get(eid)
        a = st.attributes if st is not None else {}
        title = a.get("headline") or a.get("title") or a.get("event") or "Amtliche Warnung"
        text = a.get("description") or a.get("sender") or self._name(eid)
        return str(title), str(text)[:300]

    def _image(self) -> str | None:
        cam = self.settings.get("ww_camera")
        return f"/api/camera_proxy/{cam}" if cam else None

    async def _async_fire_actions(self) -> str:
        """Ernstfall: Rollläden hoch (Fluchtweg), Licht an."""
        done = []
        data = self.hass.data.get(DOMAIN) or {}
        if self.settings.get("ww_fire_covers", True):
            rw = data.get(MODULE_SHUTTER)
            covers = list((rw.settings.get("rw_covers") if rw else None) or [])
            if covers:
                await self.hass.services.async_call("cover", "open_cover", {"entity_id": covers}, blocking=False, context=self._ctx)
                done.append("Rollläden hoch")
        if self.settings.get("ww_fire_lights", True):
            lw = data.get(MODULE_LIGHT)
            lights = [x for x in ((lw.settings.get("lw_lights") if lw else None) or []) if x.startswith("light.")]
            if lights:
                await self.hass.services.async_call("light", "turn_on", {"entity_id": lights, "brightness_pct": 100}, blocking=False, context=self._ctx)
                done.append("Licht an")
        return ", ".join(done)

    # ------------------------------------------------------------ Verlassen
    def leave_check(self, notify: bool = False) -> list[dict[str, str]]:
        """Was ist noch offen bzw. an? Türen, Tore, Fenster (Heizwerk) und Leuchten (Lichtwerk)."""
        e = self.entities()
        out: list[dict[str, str]] = []
        for x in e["doors"]:
            if self._on(x):
                out.append({"entity": x, "name": self._name(x), "what": "offen"})
        data = self.hass.data.get(DOMAIN) or {}
        ctl = data.get(MODULE_HEATING)
        for room in (getattr(ctl, "rooms", None) or {}).values():
            for w in room.get("windows") or []:
                st = self.hass.states.get(w)
                if st is not None and st.state in WINDOW_OPEN:
                    out.append({"entity": w, "name": f"{room.get('name')}: {self._name(w)}", "what": "offen"})
        lw = data.get(MODULE_LIGHT)
        for x in (lw.settings.get("lw_lights") if lw else None) or []:
            st = self.hass.states.get(x)
            if st is not None and st.state == "on":
                out.append({"entity": x, "name": lw.name_room(x) if hasattr(lw, "name_room") else self._name(x), "what": "an"})
        if notify:
            if out:
                lights = [o["entity"] for o in out if o["what"] == "an"]
                self.haus.notify("ww_leave", "leave", "Niemand zu Hause – noch offen",
                                 ", ".join(f"{o['name']} {o['what']}" for o in out[:8]) + (f" und {len(out) - 8} weitere" if len(out) > 8 else ""),
                                 actions=([{"title": "Lichter aus", "do": "lw_off", "data": {"eids": lights}}] if lights else []) + [{"title": "Gesehen", "do": "ack"}])
                self.log.add("security", "Beim Verlassen noch offen bzw. an", ", ".join(o["name"] for o in out), module="wachwerk")
            else:
                self.haus.clear("ww_leave")
        return out

    # ------------------------------------------------------------ Alarmanlage
    async def async_alarm(self, action: str, by: str | None = None) -> None:
        """Alarmanlage scharf (abwesend/zu Hause) oder unscharf – nur ohne Code."""
        alarm = self.entities().get("alarm")
        if not alarm:
            return
        service = {"away": "alarm_arm_away", "home": "alarm_arm_home", "night": "alarm_arm_night", "off": "alarm_disarm"}[action]
        await self.hass.services.async_call("alarm_control_panel", service, {"entity_id": alarm}, blocking=False, context=self._ctx)
        self.log.add("security", {"away": "Alarmanlage scharf (abwesend)", "home": "Alarmanlage scharf (zu Hause)",
                                  "night": "Alarmanlage scharf (Nacht)", "off": "Alarmanlage unscharf"}[action], by or "", module="wachwerk")

    # ------------------------------------------------------------ Status
    def status(self) -> dict[str, Any]:
        e = self.entities()
        now = dt_util.utcnow().timestamp()

        def item(x: str) -> dict[str, Any]:
            st = self.hass.states.get(x)
            return {"entity": x, "name": self._name(x), "state": st.state if st is not None else None,
                    "on": self._on(x), "since": st.last_changed.isoformat() if st is not None else None}

        warns = []
        for x in e["warn"]:
            if self._on(x):
                t, d = self._warn_text(x)
                warns.append({"entity": x, "title": t, "text": d})
        alarm = self.hass.states.get(e["alarm"]) if e.get("alarm") else None
        rings = [r for r in self._persist.get("bell_log") or [] if now - dt_util.parse_datetime(r).timestamp() < 7 * 86400]
        return {
            "configured": bool(e["smoke"] or e["co"] or e["water"] or e["doors"] or e["alarm"] or e["bell"] or e["warn"]),
            "entities": e,
            "smoke": [item(x) for x in e["smoke"]], "co": [item(x) for x in e["co"]], "water": [item(x) for x in e["water"]],
            "doors": [item(x) for x in e["doors"]], "warnings": warns,
            "alarm": {"entity": e["alarm"], "state": alarm.state if alarm is not None else None,
                      "code": bool(alarm.attributes.get("code_arm_required")) if alarm is not None else False} if e.get("alarm") else None,
            "bell": {"entity": e["bell"], "last": self._persist.get("bell_last"), "week": len(rings)} if e.get("bell") else None,
            "fire": "fire" in self._active, "water_alarm": "water" in self._active,
            "leave": self.leave_check(),
        }
