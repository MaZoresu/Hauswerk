"""Hausdienste – gehören zum Hauswerk-Kern und wirken über alle Module:

- Hausmodi: „Gute Nacht“, „Guten Morgen“, „Wir gehen“, „Wir sind da“ – ein Tipp, alle Module.
- Wartung: was im Haus fällig ist (eigene Aufgaben mit Intervall plus Batterien und Lebensdauer der Melder).
- Wochenbericht: eine Nachricht mit dem Wichtigsten der Woche aus allen Modulen.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (DOMAIN, MODE_ACTIONS, MODULE_GARDEN, MODULE_HEATING, MODULE_LIGHT, MODULE_POWER, MODULE_SECURITY, MODULE_SHUTTER,
                    SERVICES_STORAGE_KEY)
from .core import Haus
from .log import Protokoll, log_settings

MODES = {
    "night": {"name": "Gute Nacht", "icon": "mdi:weather-night", "default": ["lights_off", "covers_close", "eco_on", "mower_home", "check"]},
    "morning": {"name": "Guten Morgen", "icon": "mdi:weather-sunset-up", "default": ["covers_open", "eco_off"]},
    "leave": {"name": "Wir gehen", "icon": "mdi:exit-run", "default": ["away", "lights_off", "mower_home", "check"]},
    "home": {"name": "Wir sind da", "icon": "mdi:home-heart", "default": ["presence_auto", "eco_off"]},
}
# Vorlagen für Wartungsaufgaben
# days = Intervall in Tagen (0 = ohne), months = nur in diesen Monaten fällig (Saison), use = nach Nutzung
# (runs: Durchläufe eines Geräts der Fertigerkennung, on: Betriebsstunden einer Entität, counter: Zählerstand),
# pro = Fachbetrieb (Termin vereinbaren), unit = beim Erledigen einen Zählerstand bzw. Messwert abfragen.
TASK_TEMPLATES = [
    {"name": "Rauchmelder testen", "icon": "mdi:smoke-detector-variant", "days": 365},
    {"name": "Heizkörper entlüften", "icon": "mdi:radiator", "days": 365, "months": [9, 10]},
    {"name": "Filter Dunstabzug reinigen", "icon": "mdi:stove", "days": 90},
    {"name": "Wasserfilter wechseln", "icon": "mdi:water-check-outline", "days": 180},
    {"name": "Lüftungsfilter wechseln", "icon": "mdi:air-filter", "days": 180, "use": {"kind": "on", "every": 2000}},
    {"name": "Waschmaschine reinigen (Kochwäsche, Flusensieb)", "icon": "mdi:washing-machine", "days": 90, "use": {"kind": "runs", "every": 30}},
    {"name": "Geschirrspüler: Sieb reinigen", "icon": "mdi:dishwasher", "days": 60, "use": {"kind": "runs", "every": 25}},
    {"name": "Trockner: Flusensieb und Wärmetauscher", "icon": "mdi:tumble-dryer", "days": 60, "use": {"kind": "runs", "every": 10}},
    {"name": "Dachrinne reinigen", "icon": "mdi:home-roof", "days": 0, "months": [11]},
    {"name": "Heizungswartung (Therme)", "icon": "mdi:water-boiler", "days": 365, "pro": True, "unit": "bar"},
    {"name": "Schornsteinfeger", "icon": "mdi:home-roof", "days": 365, "pro": True},
    {"name": "Kühlschrank abtauen und reinigen", "icon": "mdi:fridge-outline", "days": 180},
    {"name": "Kaffeevollautomat entkalken", "icon": "mdi:coffee-maker-outline", "days": 60},
    {"name": "Gartenwasser abstellen (Frost)", "icon": "mdi:water-off-outline", "days": 0, "months": [10, 11]},
    {"name": "Gartenwasser und Bewässerung in Betrieb nehmen", "icon": "mdi:sprinkler-variant", "days": 0, "months": [4]},
    {"name": "Mähroboter einwintern (reinigen, laden, einlagern)", "icon": "mdi:robot-mower-outline", "days": 0, "months": [11]},
    {"name": "Mähroboter: Messer wechseln", "icon": "mdi:saw-blade", "days": 0, "use": {"kind": "counter", "every": 300}},
    {"name": "Regentonne entleeren", "icon": "mdi:barrel-outline", "days": 0, "months": [11]},
    {"name": "Klimagerät / Ventilator reinigen", "icon": "mdi:fan", "days": 0, "months": [5]},
    {"name": "Fenster und Türen ölen", "icon": "mdi:door", "days": 0, "months": [10]},
    {"name": "Feuerlöscher prüfen lassen", "icon": "mdi:fire-extinguisher", "days": 730, "pro": True},
    {"name": "Wasserzähler ablesen", "icon": "mdi:water-pump", "days": 365, "months": [12], "unit": "m³"},
    {"name": "Gaszähler ablesen", "icon": "mdi:meter-gas-outline", "days": 365, "months": [12], "unit": "m³"},
    {"name": "Stromzähler ablesen", "icon": "mdi:meter-electric-outline", "days": 365, "months": [12], "unit": "kWh"},
    {"name": "Anlagendruck Heizung prüfen", "icon": "mdi:gauge", "days": 90, "months": [9, 10, 11, 12, 1, 2, 3], "unit": "bar"},
]
USE_UNITS = {"runs": "Durchläufe", "on": "Std."}
WARRANTY_DAYS = 30            # so lange vor Ende der Garantie erinnern
BOOK_LEAD = 42                # Fachbetrieb: so viele Tage vor Fälligkeit „Termin vereinbaren“
PHOTO_KEEP = 40
SNOOZE_DAYS = (1, 7, 30)

_LOGGER = logging.getLogger(__name__)

AI_INSTRUCTIONS = """Du schreibst den Wochenbericht eines Smart Homes („Hauswerk“) für die Bewohner – als Text einer Push-Nachricht.
Regeln:
- Deutsch, Du-Form, freundlich und sachlich. Höchstens 5 kurze Sätze, höchstens 600 Zeichen. Keine Begrüßung, keine Überschrift, kein Markdown, keine Aufzählungszeichen.
- Nutze ausschließlich die Fakten unten. Erfinde keine Zahlen, Räume oder Geräte und rechne nichts Neues aus – Vergleiche nur, wenn sie in den Fakten stehen.
- Zuerst das Auffälligste der Woche (Abweichung zur Vorwoche, Warnung, Fehler, Fälliges), dann Zusammenhänge zwischen den Bereichen, wenn die Fakten sie hergeben (z. B. viel gelüftet und mehr geheizt).
- Zum Schluss genau ein konkreter, umsetzbarer Tipp – nur wenn die Fakten einen hergeben.
- War nichts besonders, sag das in einem Satz.
- Höchstens 3 dezente Emojis.

Fakten der letzten 7 Tage:
"""

HD_DEFAULTS: dict[str, Any] = {
    "hd_modes": {k: list(v["default"]) for k, v in MODES.items()},
    "hd_tasks": [],               # [{id, name, icon, days, last, months, use, person, pro, …}]
    "hd_calendar": None,          # Kalender, in den Termine beim Fachbetrieb eingetragen werden (calendar.…)
    "hd_modes_show": False,       # Knöpfe der Hausmodi auf der Startseite (Standard aus)
    "hd_weekly": True,
    "hd_weekly_day": 6,           # 0 = Montag … 6 = Sonntag
    "hd_weekly_time": "18:00",
    "hd_ai": False,               # Wochenbericht mit KI formulieren (Home Assistant „AI Task“)
    "hd_ai_entity": None,         # ai_task.… (leer = erste gefundene)
}
HD_KEYS = set(HD_DEFAULTS)


class Dienste:
    """Hausmodi, Wartung und Wochenbericht."""

    def __init__(self, hass: HomeAssistant, log: Protokoll, haus: Haus) -> None:
        self.hass = hass
        self.log = log
        self.haus = haus
        self._store: Store = Store(hass, 1, SERVICES_STORAGE_KEY)
        self.settings: dict[str, Any] = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v) for k, v in HD_DEFAULTS.items()}
        self._persist: dict[str, Any] = {}
        self._unsubs: list = []
        self._ctx = Context()
        self._listeners: set = set()
        self._derived_prev: set[str] = set()
        self._photo_store: Store = Store(hass, 1, f"{SERVICES_STORAGE_KEY}_fotos")
        self._photos: dict[str, str] = {}
        self._snap: str = ""
        haus.extra_status["dienste"] = self.status

    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        self.settings.update({k: v for k, v in (stored.get("settings") or {}).items() if k in HD_KEYS})
        self._persist = stored.get("persist") or {}
        self._photos = ((await self._photo_store.async_load()) or {}).get("photos") or {}

    async def async_start(self) -> None:
        self.haus.action_handlers["hd_done"] = lambda d, by: self.async_task_done(str(d.get("id")), by=by)
        self._unsubs.append(async_track_time_interval(self.hass, self._async_tick, timedelta(minutes=1)))

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self._store.async_save(self._data())
        await self._photo_store.async_save({"photos": self._photos})

    def _save(self) -> None:
        self._store.async_delay_save(self._data, 5)

    def _data(self) -> dict[str, Any]:
        return {"settings": self.settings, "persist": self._persist}

    async def async_save_settings(self, settings: dict[str, Any], by: str | None = None) -> None:
        settings = {k: v for k, v in settings.items() if k in HD_KEYS}
        if "hd_tasks" in settings:
            settings["hd_tasks"] = [{**t, "id": t.get("id") or uuid.uuid4().hex[:8]} for t in settings["hd_tasks"]]
        changed = [k for k, v in settings.items() if self.settings.get(k) != v]
        if not changed:
            return
        log_settings(self.log, settings, changed, by, module="haus", old=self.settings)
        if "hd_tasks" in settings:
            old = {t.get("id"): t for t in self.settings.get("hd_tasks") or []}
            for t in settings["hd_tasks"]:
                o = old.get(t["id"])
                if t.get("use") and (o is None or (o.get("use") or {}) != t["use"]):
                    self._reset_use(t)  # neue bzw. geänderte Nutzung zählt ab jetzt
        self.settings.update(settings)
        self._save()
        self._check_tasks()
        self._changed()
        if "hd_tasks" in settings or "hd_calendar" in settings:
            self.hass.async_create_task(self._async_export_appts())

    def _mod(self, key: str):
        return (self.hass.data.get(DOMAIN) or {}).get(key)

    async def _async_tick(self, _now=None) -> None:
        self._track_use()
        self._derive()
        self._check_tasks()
        snap = repr([(t["id"], t.get("left"), t.get("due")) for t in self.tasks()])
        if snap != self._snap:
            self._snap = snap
            self._changed()
        await self._async_weekly()

    # ------------------------------------------------------------ Hausmodi
    def mode_actions(self, mode: str) -> list[str]:
        acts = (self.settings.get("hd_modes") or {}).get(mode)
        return [a for a in (acts if acts is not None else MODES[mode]["default"]) if a in MODE_ACTIONS]

    async def async_mode(self, mode: str, by: str | None = None) -> dict[str, Any]:
        """Hausmodus ausführen: jede gewählte Aktion über das zuständige Modul. Antwort: was getan wurde, was offen ist."""
        if mode not in MODES:
            return {"done": [], "open": []}
        done: list[str] = []
        open_items: list[dict[str, str]] = []
        acts = self.mode_actions(mode)
        lw, rw, bw, ww = self._mod(MODULE_LIGHT), self._mod(MODULE_SHUTTER), self._mod(MODULE_GARDEN), self._mod(MODULE_SECURITY)
        for a in acts:
            try:
                if a == "lights_off" and lw:
                    on = [x for x in lw.settings.get("lw_lights") or [] if (st := self.hass.states.get(x)) is not None and st.state == "on"]
                    if on:
                        await lw.async_command(on, "off", by=by)
                        done.append(f"{len(on)} {'Licht' if len(on) == 1 else 'Lichter'} aus")
                elif a in ("covers_close", "covers_open") and rw:
                    covers = list(rw.settings.get("rw_covers") or [])
                    if covers:
                        await rw.async_command(covers, "close" if a == "covers_close" else "open", by=by)
                        done.append("Rollläden zu" if a == "covers_close" else "Rollläden auf")
                elif a in ("eco_on", "eco_off"):
                    want = a == "eco_on"
                    ctl = self._mod(MODULE_HEATING)
                    owner = self.haus if "eco_force" in self.haus.settings else ctl
                    if owner is not None:
                        if bool(owner.settings.get("eco_force")) != want:
                            await owner.async_save_settings({"eco_force": want}, by=by)
                        done.append("Heizung auf Eco" if want else "Heizung nach Plan")
                elif a in ("away", "presence_auto"):
                    want = "away" if a == "away" else None
                    if self.haus.settings.get("presence_force") != want:
                        await self.haus.async_save_settings({"presence_force": want}, by=by)
                    done.append("Anwesenheit: abwesend" if want else "Anwesenheit: automatisch")
                elif a == "mower_home" and bw:
                    mower = bw.mower()
                    st = self.hass.states.get(mower) if mower else None
                    if st is not None and st.state in ("mowing", "paused"):
                        await self.hass.services.async_call("lawn_mower", "dock", {"entity_id": mower}, blocking=False, context=self._ctx)
                        done.append("Mähroboter fährt heim")
                elif a.startswith("alarm_") and ww and ww.entities().get("alarm"):
                    await ww.async_alarm({"alarm_away": "away", "alarm_night": "night", "alarm_off": "off"}[a], by=by)
                    done.append(MODE_ACTIONS[a])
                elif a == "check" and ww:
                    # Lichter, die dieser Modus gerade ausschaltet, zählen nicht als „noch an“
                    open_items = [o for o in ww.leave_check() if not ("lights_off" in acts and o["what"] == "an")]
            except Exception as err:  # noqa: BLE001 - ein Modul darf den Modus nicht abbrechen
                done.append(f"{MODE_ACTIONS[a]}: fehlgeschlagen ({err})")
        name = MODES[mode]["name"]
        why = ", ".join(done) or "nichts zu tun"
        if open_items:
            why += " · noch offen bzw. an: " + ", ".join(f"{o['name']}" for o in open_items)
        self.log.add("command", f"Hausmodus „{name}“", why + (f" · {by}" if by else ""), module="haus")
        self._persist["last_mode"] = {"mode": mode, "at": dt_util.utcnow().isoformat()}
        self._save()
        return {"mode": mode, "name": name, "done": done, "open": open_items}

    # ------------------------------------------------------------ Wartung
    def subscribe(self, cb) -> Any:
        """Für die Entitäten (Aufgabenliste, Kalender): bei Änderungen benachrichtigen."""
        self._listeners.add(cb)
        return lambda: self._listeners.discard(cb)

    def _changed(self) -> None:
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Wartung: Listener fehlgeschlagen", exc_info=True)

    @staticmethod
    def _season(t: dict, today: date) -> tuple[date, date] | None:
        """Saison-Fenster (Beginn, Ende) – das aktuelle bzw. das nächste. None = keine Saison."""
        months = sorted({int(m) for m in t.get("months") or [] if 1 <= int(m) <= 12})
        if not months:
            return None
        last = date.fromisoformat(t["last"]) if t.get("last") else None
        # zusammenhängende Monate (auch über den Jahreswechsel) zu Fenstern zusammenfassen
        runs: list[list[int]] = []
        for m in months:
            if runs and m == runs[-1][-1] + 1:
                runs[-1].append(m)
            else:
                runs.append([m])
        if len(runs) > 1 and runs[0][0] == 1 and runs[-1][-1] == 12:
            runs[-1] += runs.pop(0)
        cands = []
        for year in (today.year - 1, today.year, today.year + 1):
            for r in runs:
                start = date(year, r[0], 1)
                ey = year + (1 if r[-1] < r[0] else 0)
                end = (date(ey + (r[-1] == 12), (r[-1] % 12) + 1, 1)) - timedelta(days=1)
                cands.append((start, end))
        for start, end in sorted(cands):
            if end < today:
                continue
            if last and start <= last <= end:
                continue  # in diesem Fenster schon erledigt
            return start, end
        return None

    def _use(self, t: dict) -> dict | None:
        """Nutzung seit dem letzten Erledigen: {used, every, unit, rate}."""
        use = t.get("use") or {}
        kind, src, every = use.get("kind"), use.get("src"), float(use.get("every") or 0)
        if kind not in ("runs", "on", "counter") or not src or every <= 0:
            return None
        u = (self._persist.get("use") or {}).get(t.get("id")) or {}
        used = None
        unit = USE_UNITS.get(kind)
        if kind == "runs":
            used = float(u.get("n") or 0)
        elif kind == "on":
            used = round(float(u.get("min") or 0) / 60, 1)
        else:
            st = self.hass.states.get(src)
            try:
                val = float(st.state) if st is not None else None
            except (TypeError, ValueError):
                val = None
            unit = (st.attributes.get("unit_of_measurement") if st is not None else None) or ""
            if val is not None and u.get("base") is not None:
                used = round(max(0.0, val - float(u["base"])), 1)
        if used is None:
            return {"used": None, "every": every, "unit": unit}
        since = u.get("since")
        days = (dt_util.utcnow() - dt_util.parse_datetime(since)).total_seconds() / 86400 if since else 0
        rate = used / days if days >= 1 and used > 0 else None
        return {"used": used, "every": every, "unit": unit, "rate": rate}

    def _due(self, t: dict, today: date) -> tuple[date | None, int | None]:
        """Fällig am, Tage bis dahin (negativ = überfällig) – nach Intervall, Saison und Nutzung (das Früheste)."""
        cands: list[date] = []
        days = int(t.get("days") or 0)
        last = date.fromisoformat(t["last"]) if t.get("last") else None
        season = self._season(t, today)
        if t.get("months"):
            if season is None:
                return None, None
            win = season
            if days and last:
                nxt = last + timedelta(days=days)
                while win and nxt > win[1]:  # Intervall noch nicht um – nächstes Saisonfenster
                    win = self._season({**t, "last": win[1].isoformat()}, win[1] + timedelta(days=1))
                if win:
                    cands.append(max(win[0], nxt))
            else:
                cands.append(win[0])
        elif days:
            cands.append(last + timedelta(days=days) if last else today)
        if t.get("once"):
            cands.append(date.fromisoformat(t["due_on"]) if t.get("due_on") else today)
        use = self._use(t)
        if use and use.get("used") is not None:
            left = use["every"] - use["used"]
            if left <= 0:
                cands.append(today)
            elif use.get("rate"):
                cands.append(today + timedelta(days=max(1, int(left / use["rate"] + 0.999))))
        if not cands:
            return None, None
        due = min(cands)
        return due, (due - today).days

    def tasks(self) -> list[dict[str, Any]]:
        """Eigene Aufgaben plus automatisch erkannte (Batterie, Melder, Mäher, aus Meldungen, Garantie)."""
        today = dt_util.now().date()
        out = []
        snoozes = self._persist.get("snooze") or {}
        for t in self.settings.get("hd_tasks") or []:
            due, left = self._due(t, today)
            snooze = snoozes.get(t.get("id"))
            if snooze and due is not None and snooze > due.isoformat():
                due = date.fromisoformat(snooze)
                left = (due - today).days
            rec = {**t, "auto": False, "due": due.isoformat() if due else None, "left": left,
                   "snoozed": bool(snooze and snooze > today.isoformat())}
            if t.get("use"):
                rec["usage"] = self._use(t)
            if t.get("months"):
                win = self._season(t, today)
                rec["season"] = [win[0].isoformat(), win[1].isoformat()] if win else None
            appt = t.get("appt")
            if appt and appt[:10] >= today.isoformat():
                rec["appt_next"] = appt
            if t.get("pro") and left is not None and 0 < left <= int(t.get("lead") or BOOK_LEAD) and not rec.get("appt_next"):
                rec["book"] = True
            if t.get("person"):
                st = self.hass.states.get(t["person"])
                rec["person_name"] = getattr(st, "name", None) if st is not None else None
            out.append(rec)
        # automatisch: Batterien (binary_sensor Geräteklasse battery an)
        ids = getattr(self.hass.states, "async_entity_ids", None)
        for eid in sorted(ids("binary_sensor")) if ids else []:
            st = self.hass.states.get(eid)
            if st is None or st.state != "on":
                continue
            dc = st.attributes.get("device_class")
            name = getattr(st, "name", eid) or eid
            if dc == "battery":
                out.append({"id": f"auto:{eid}", "name": f"Batterie wechseln: {name.replace(' Batterie', '').replace(' battery', '')}",
                            "icon": "mdi:battery-alert-variant-outline", "auto": True, "left": 0, "entity": eid})
            elif eid.endswith(("_is_life_end", "_life_end", "_end_of_life")):
                out.append({"id": f"auto:{eid}", "name": f"Melder tauschen (Lebensdauer erreicht): {name}", "icon": "mdi:smoke-detector-alert",
                            "auto": True, "left": 0, "entity": eid})
        bw = self._mod(MODULE_GARDEN)
        if bw is not None:
            try:
                ent = bw.entities()
                st = self.hass.states.get(ent.get("blades_days") or "")
                lim = float(bw.settings.get("bw_blades_days") or 0)
                if st is not None and lim and float(st.state) >= lim:
                    out.append({"id": "auto:blades", "name": "Mähroboter: Messer wechseln", "icon": "mdi:saw-blade", "auto": True, "left": 0})
            except (TypeError, ValueError):
                pass
            # Verschleiß aus Beetwerk (Messer stumpf, Akku altert, Draht/WLAN, Feuchte)
            try:
                icons = {"blades": "mdi:saw-blade", "battery": "mdi:battery-heart-variant", "wire": "mdi:vector-polyline", "wlan": "mdi:wifi-strength-1-alert", "humid": "mdi:water-alert-outline"}
                for k, txt in (bw.wear(bw.entities()) or {}).items():
                    if txt and not (k == "blades" and any(x["id"] == "auto:blades" for x in out)):
                        out.append({"id": f"auto:bw_{k}", "name": f"Mähroboter: {txt.split(' – ')[-1] if ' – ' in txt else txt}", "note": txt,
                                    "icon": icons.get(k, "mdi:robot-mower-outline"), "auto": True, "left": 0, "room": "Garten"})
            except Exception:  # noqa: BLE001 - Beetwerk ohne Mäher
                pass
        # Batterien unter der Grenze (Heizwerk: Thermostate, Fensterkontakte, Raumsensoren) – mit Raum
        ctl = self._mod(MODULE_HEATING)
        if ctl is not None:
            seen = {t.get("entity") for t in out}
            for room_id, room in (getattr(ctl, "rooms", None) or {}).items():
                try:
                    low = ctl._battery_low(room_id)
                except Exception:  # noqa: BLE001
                    low = []
                for b in low:
                    if b["id"] in seen:
                        continue
                    seen.add(b["id"])
                    out.append({"id": f"auto:{b['id']}", "name": f"Batterie wechseln: {b['name']}", "note": f"noch {round(b['level'])} %",
                                "icon": "mdi:battery-alert-variant-outline", "auto": True, "left": 0, "entity": b["id"], "room": room.get("name")})
        # aus Meldungen abgeleitet (z. B. Heizkörper blieb kalt → entlüften) – bis quittiert
        for key, d in (self._persist.get("derived") or {}).items():
            out.append({"id": f"auto:{key}", "name": d["name"], "icon": d.get("icon") or "mdi:wrench-outline", "auto": True, "left": 0,
                        "room": d.get("room"), "note": d.get("note"), "derived": True})
        # Garantie endet bald
        for t in self.settings.get("hd_tasks") or []:
            w = t.get("warranty")
            if w:
                try:
                    left = (date.fromisoformat(w) - today).days
                except ValueError:
                    continue
                if 0 <= left <= WARRANTY_DAYS:
                    out.append({"id": f"auto:warranty:{t.get('id')}", "name": f"Garantie endet: {t.get('device') or t.get('name')}",
                                "icon": "mdi:shield-alert-outline", "auto": True, "left": 0, "room": t.get("room"),
                                "note": f"am {date.fromisoformat(w).strftime('%d.%m.%Y')} – Mängel jetzt noch melden"})
        # quittierte automatische Aufgaben 3 Tage ausblenden (z. B. Batterie gerade gewechselt, Wert noch nicht neu gemeldet);
        # Garantie-Hinweise bleiben nach dem Quittieren weg
        acks = self._persist.get("acks") or {}
        out = [t for t in out if not (t.get("auto") and acks.get(t["id"])
                                      and (t["id"].startswith("auto:warranty:") or acks[t["id"]] > (today - timedelta(days=3)).isoformat()))]
        return sorted(out, key=lambda t: (t["left"] is None, t["left"] if t["left"] is not None else 0, t["name"]))

    def _hist(self, name: str, icon: str | None, by: str | None, what: str = "erledigt", **extra) -> None:
        h = self._persist.setdefault("history", [])
        h.insert(0, {"name": name, "icon": icon, "at": dt_util.utcnow().isoformat(), "by": by or "", "what": what,
                     **{k: v for k, v in extra.items() if v is not None}})
        del h[200:]

    async def async_task_snooze(self, task_id: str, days: int, by: str | None = None) -> None:
        """Aufgabe verschieben (später erinnern)."""
        until = (dt_util.now().date() + timedelta(days=int(days))).isoformat()
        self._persist.setdefault("snooze", {})[task_id] = until
        t = next((x for x in self.settings.get("hd_tasks") or [] if x.get("id") == task_id), None)
        self.log.add("settings", f"Wartung verschoben: {t.get('name') if t else task_id}", f"bis {until} · {by or ''}".strip(" ·"), module="haus")
        self.haus.clear(f"maint:{task_id}")
        self._save()

    def _track_use(self) -> None:
        """Nutzung je Aufgabe mitzählen: Durchläufe der Fertigerkennung, Betriebsminuten, Zählerstand beim Erledigen."""
        store = self._persist.setdefault("use", {})
        kw = self._mod(MODULE_POWER)
        now = dt_util.utcnow()
        for t in self.settings.get("hd_tasks") or []:
            use = t.get("use") or {}
            kind, src = use.get("kind"), use.get("src")
            if not kind or not src:
                store.pop(t.get("id"), None)
                continue
            u = store.get(t["id"])
            if u is None or u.get("src") != src or u.get("kind") != kind:
                u = store[t["id"]] = {"src": src, "kind": kind, "since": now.isoformat(), "n": 0, "min": 0, "seen": []}
            if kind == "runs":
                det = (getattr(getattr(kw, "appliances", None), "det", None) or {}).get(src) if kw else None
                since = dt_util.parse_datetime(u["since"]).timestamp()
                for r in getattr(det, "runs", None) or []:
                    rid = str(r.get("id"))
                    if (r.get("start") or 0) >= since and rid not in u["seen"]:
                        u["seen"] = [*u["seen"], rid][-60:]
                        u["n"] = int(u.get("n") or 0) + 1
            elif kind == "on":
                st = self.hass.states.get(src)
                if st is not None and st.state not in ("off", "unavailable", "unknown", "idle", "standby", "0", "closed", "docked"):
                    u["min"] = float(u.get("min") or 0) + 1
            elif kind == "counter" and u.get("base") is None:
                st = self.hass.states.get(src)
                try:
                    u["base"] = float(st.state) if st is not None else None
                except (TypeError, ValueError):
                    pass

    def _reset_use(self, t: dict) -> None:
        use = t.get("use") or {}
        if not use.get("kind"):
            return
        u = {"src": use.get("src"), "kind": use.get("kind"), "since": dt_util.utcnow().isoformat(), "n": 0, "min": 0, "seen": []}
        if use.get("kind") == "runs":
            det = (getattr(getattr(self._mod(MODULE_POWER), "appliances", None), "det", None) or {}).get(use.get("src"))
            u["seen"] = [str(r.get("id")) for r in getattr(det, "runs", None) or []][-60:]
        elif use.get("kind") == "counter":
            st = self.hass.states.get(use.get("src") or "")
            try:
                u["base"] = float(st.state) if st is not None else None
            except (TypeError, ValueError):
                u["base"] = None
        self._persist.setdefault("use", {})[t["id"]] = u

    def _derive(self) -> None:
        """Aus Meldungen der Module Aufgaben ableiten – neu, sobald eine Meldung auftaucht; bleiben bis quittiert."""
        active: dict[str, dict] = {}
        ctl = self._mod(MODULE_HEATING)
        for key in list(getattr(ctl, "_flags", None) or {}):
            if key.startswith("cold:"):
                rid = key[5:]
                room = (getattr(ctl, "rooms", None) or {}).get(rid) or {}
                active[f"bleed:{rid}"] = {"name": f"Heizkörper entlüften: {room.get('name') or rid}", "icon": "mdi:radiator",
                                          "room": room.get("name"), "note": "Heizkörper blieb trotz offenem Ventil kalt – erst entlüften, dann Ventilstift prüfen"}
        kw = self._mod(MODULE_POWER)
        try:
            findings = (kw.watch.status() or {}).get("findings") or [] if kw is not None else []
        except Exception:  # noqa: BLE001
            findings = []
        for f in findings:
            key = str(f.get("key") or "")
            title = str(f.get("title") or "")
            if key.startswith("kw_dev:") and any(w in title.lower() for w in ("kühl", "gefrier", "kuehl", "frost")):
                name = title.replace(" braucht mehr Strom", "")
                active[f"fridge:{key[7:]}"] = {"name": f"{name}: abtauen, Dichtung und Lüftungsgitter prüfen", "icon": "mdi:fridge-alert-outline",
                                               "note": f.get("text")}
        derived = self._persist.setdefault("derived", {})
        prev = self._derived_prev
        changed = False
        for k, d in active.items():
            if k not in prev and k not in derived:
                derived[k] = {**d, "since": dt_util.utcnow().isoformat()}
                self.log.add("settings", f"Wartung: {d['name']}", "aus einer Meldung abgeleitet", module="haus")
                changed = True
        self._derived_prev = set(active)
        if changed:
            self._save()

    def _check_tasks(self) -> None:
        """Fällige eigene Aufgaben melden (Benachrichtigungen › Hauswerk › Wartung) – an die zuständige Person, wenn gewählt."""
        today = dt_util.now().date()
        local = dt_util.now()
        for t in self.tasks():
            if t.get("auto"):
                continue
            tid = t.get("id")
            key = f"maint:{tid}"
            chans = self.haus.person_channels(t["person"]) if t.get("person") and hasattr(self.haus, "person_channels") else None
            left = t.get("left")
            who = f" ({t['person_name']})" if t.get("person_name") else ""
            if left is not None and left <= 0 and not t.get("appt_next"):
                text = (t.get("name") or "Aufgabe") + (f" · {t['room']}" if t.get("room") else "") + who
                self.haus.notify(key, "maint", "Wartung fällig", text, channels=chans,
                                 actions=[{"title": "Erledigt", "do": "hd_done", "data": {"id": tid}},
                                          {"title": "In 1 Woche", "do": "snooze", "minutes": 7 * 1440}])
            else:
                self.haus.clear(key)
            bkey = f"maint_book:{tid}"
            if t.get("book"):
                due = date.fromisoformat(t["due"]).strftime("%d.%m.") if t.get("due") else ""
                pro = " · ".join(x for x in (t.get("pro_name"), t.get("phone")) if x)
                self.haus.notify(bkey, "maint", "Termin vereinbaren", f"{t.get('name')} – fällig am {due}{' · ' + pro if pro else ''}{who}",
                                 channels=chans, actions=[{"title": "Gesehen", "do": "ack"}])
            else:
                self.haus.clear(bkey)
            appt = t.get("appt_next")
            if appt and appt[:10] == today.isoformat() and local.hour >= 7:
                at = appt[11:16] if len(appt) > 10 else ""
                self.haus.notify(f"maint_appt:{tid}:{appt[:10]}", "maint", "Heute Wartungstermin",
                                 f"{t.get('name')}{' um ' + at + ' Uhr' if at else ''}{' · ' + t['pro_name'] if t.get('pro_name') else ''}{who}",
                                 channels=chans)

    async def async_task_done(self, task_id: str, by: str | None = None, note: str | None = None, cost: float | None = None,
                              reading: float | None = None, photo: str | None = None) -> None:
        pid = None
        if photo:
            pid = uuid.uuid4().hex[:10]
            self._photos[pid] = photo
            for old in list(self._photos)[:-PHOTO_KEEP]:
                self._photos.pop(old, None)
            self._photo_store.async_delay_save(lambda: {"photos": self._photos}, 5)
        if task_id.startswith("auto:"):
            item = next((t for t in self.tasks() if t["id"] == task_id), None)
            self._persist.setdefault("acks", {})[task_id] = dt_util.now().date().isoformat()
            (self._persist.get("derived") or {}).pop(task_id[5:], None)
            if item:
                self._hist(item["name"], item.get("icon"), by, "quittiert" + (f" – {note}" if note else ""), task=task_id,
                           cost=cost, photo=pid, room=item.get("room"))
                self.log.add("settings", f"Wartung quittiert: {item['name']}", by or "", module="haus")
            self._save()
            self._changed()
            return
        tasks = self.settings.get("hd_tasks") or []
        for t in list(tasks):
            if t.get("id") == task_id:
                t["last"] = dt_util.now().date().isoformat()
                (self._persist.get("snooze") or {}).pop(task_id, None)
                if t.get("appt") and t["appt"][:10] <= t["last"]:
                    t.pop("appt", None)  # Termin war – erledigt
                self._reset_use(t)
                extra = []
                if reading is not None:
                    extra.append(f"{str(reading).replace('.', ',')} {t.get('unit') or ''}".strip())
                if cost:
                    extra.append(f"{cost:.2f} €".replace(".", ","))
                if note:
                    extra.append(note)
                self._hist(t.get("name") or "Aufgabe", t.get("icon"), by, "erledigt" + (f" – {' · '.join(extra)}" if extra else ""),
                           task=task_id, cost=cost, reading=reading, unit=t.get("unit"), photo=pid, room=t.get("room"))
                self.log.add("settings", f"Wartung erledigt: {t.get('name')}", (by or "") + (f" – {' · '.join(extra)}" if extra else ""), module="haus")
                if t.get("once"):
                    tasks.remove(t)
        self.settings["hd_tasks"] = tasks
        self._save()
        self._check_tasks()
        self._changed()

    async def async_add_task(self, name: str, by: str | None = None, due: str | None = None, note: str | None = None) -> dict:
        """Einmalige Aufgabe anlegen (z. B. über die Aufgabenliste in Home Assistant bzw. Assist)."""
        t = {"id": uuid.uuid4().hex[:8], "name": name[:80], "icon": "mdi:wrench-outline", "days": 0, "once": True,
             "due_on": due or dt_util.now().date().isoformat(), **({"note": note[:200]} if note else {})}
        await self.async_save_settings({"hd_tasks": [*(self.settings.get("hd_tasks") or []), t]}, by=by)
        return t

    async def async_delete_task(self, task_id: str, by: str | None = None) -> None:
        await self.async_save_settings({"hd_tasks": [t for t in self.settings.get("hd_tasks") or [] if t.get("id") != task_id]}, by=by)

    def photo(self, pid: str) -> str | None:
        return self._photos.get(pid)

    def costs(self) -> dict[str, Any]:
        """Kosten je Jahr (aus den Erledigungen) und je Aufgabe im laufenden Jahr."""
        years: dict[str, float] = {}
        per: dict[str, float] = {}
        this = str(dt_util.now().year)
        for h in self._persist.get("history") or []:
            c = h.get("cost")
            if not c:
                continue
            y = h["at"][:4]
            years[y] = round(years.get(y, 0) + float(c), 2)
            if y == this:
                per[h["name"]] = round(per.get(h["name"], 0) + float(c), 2)
        return {"years": years, "tasks": dict(sorted(per.items(), key=lambda x: -x[1]))}

    def calendar_events(self, start: date, end: date) -> list[dict[str, Any]]:
        """Fälligkeiten und Termine im Zeitraum – für den Kalender „Hauswerk Wartung“."""
        out = []
        today = dt_util.now().date()
        for t in self.tasks():
            if t.get("auto"):
                continue
            if t.get("appt_next"):
                out.append({"summary": f"Wartung: {t['name']}", "start": t["appt_next"], "timed": len(t["appt_next"]) > 10,
                            "description": " · ".join(x for x in (t.get("pro_name"), t.get("phone"), t.get("room"), t.get("note")) if x), "uid": f"{t['id']}-appt"})
            due = date.fromisoformat(t["due"]) if t.get("due") else None
            if due is None:
                continue
            due = max(due, today)
            days = int(t.get("days") or 0)
            n = 0
            while due <= end and n < 60:
                if due >= start:
                    out.append({"summary": f"Fällig: {t['name']}", "start": due.isoformat(), "timed": False,
                                "description": " · ".join(x for x in (t.get("room"), t.get("person_name"), t.get("note")) if x), "uid": f"{t['id']}-{due}"})
                n += 1
                if t.get("months"):
                    nxt = self._season({**t, "last": due.isoformat()}, due + timedelta(days=1))
                    if days:
                        cand = due + timedelta(days=days)
                        nxt2 = self._season({**t, "last": due.isoformat()}, cand)
                        nxt = nxt2 if nxt2 else nxt
                    due = nxt[0] if nxt else end + timedelta(days=1)
                elif days and not t.get("once"):
                    due = due + timedelta(days=days)
                else:
                    break
        return out

    async def _async_export_appts(self) -> None:
        """Termine beim Fachbetrieb in den gewählten Kalender eintragen (je Termin einmal)."""
        cal = self.settings.get("hd_calendar")
        if not cal:
            return
        done = self._persist.setdefault("cal", {})
        for t in self.settings.get("hd_tasks") or []:
            appt = t.get("appt")
            if not appt or done.get(t["id"]) == appt:
                continue
            done[t["id"]] = appt
            desc = " · ".join(x for x in (t.get("pro_name"), t.get("phone"), t.get("room"), t.get("note")) if x)
            data: dict[str, Any] = {"entity_id": cal, "summary": f"Wartung: {t.get('name')}", "description": desc}
            if len(appt) > 10:
                st = datetime.fromisoformat(appt)
                data.update(start_date_time=st.strftime("%Y-%m-%d %H:%M:%S"), end_date_time=(st + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"))
            else:
                d = date.fromisoformat(appt[:10])
                data.update(start_date=d.isoformat(), end_date=(d + timedelta(days=1)).isoformat())
            try:
                await self.hass.services.async_call("calendar", "create_event", data, blocking=True, context=self._ctx)
                self.log.add("settings", f"Termin im Kalender: {t.get('name')}", f"{appt.replace('T', ' ')} · {cal}", module="haus")
            except Exception as err:  # noqa: BLE001
                self.log.add("settings", f"Termin nicht im Kalender: {t.get('name')}", str(err), module="haus")
        self._save()

    # ------------------------------------------------------------ Wochenbericht
    async def _async_weekly(self) -> None:
        if not self.settings.get("hd_weekly", True):
            return
        local = dt_util.now()
        try:
            h, m = (int(x) for x in str(self.settings.get("hd_weekly_time") or "18:00").split(":")[:2])
        except ValueError:
            h, m = 18, 0
        if local.weekday() != int(self.settings.get("hd_weekly_day") or 6) or local.hour * 60 + local.minute < h * 60 + m:
            return
        week = f"{local.isocalendar()[0]}-{local.isocalendar()[1]}"
        if self._persist.get("weekly_sent") == week:
            return
        self._persist["weekly_sent"] = week
        self._save()
        rep = await self.async_weekly_report()
        self.haus.notify(f"weekly:{week}", "weekly", rep["title"], rep["text"], actions=[{"title": "Hauswerk öffnen", "uri": "/hauswerk"}])
        if rep.get("ai_error"):
            self.log.add("notify", "Wochenbericht ohne KI", rep["ai_error"], module="haus")

    def ai_entity(self) -> str | None:
        """Gewählte bzw. erste gefundene AI-Task-Entität (z. B. ai_task.openai_ai_task)."""
        want = self.settings.get("hd_ai_entity")
        if want and self.hass.states.get(want) is not None:
            return want
        ids = getattr(self.hass.states, "async_entity_ids", None)
        found = sorted(ids("ai_task")) if ids else []
        return next((e for e in found if "ai_task" in e.split(".", 1)[1]), found[0] if found else None)

    def _facts(self) -> list[str]:
        """Fakten für die KI: genauer als die Zeilen, mit Vergleich zur Vorwoche – ohne Personennamen."""
        out: list[str] = []
        ctl = self._mod(MODULE_HEATING)
        if ctl is not None:
            try:
                rep = ctl.report(14)
                ana = rep.pop("_analysis", {})
                VERD = {"good": "passt", "tight": "knapp", "weak": "zu schwach", "reserve": "passt mit Reserve", "sensor": "Thermostat regelt zu früh ab", "nodata": "zu wenig Daten"}
                for rid, rows in rep.items():
                    room = ctl.rooms.get(rid) or {}
                    now_, prev = rows[7:], rows[:7]
                    h, hp = sum(r.get("heat_min", 0) for r in now_) / 60, sum(r.get("heat_min", 0) for r in prev) / 60
                    o, op = sum(r.get("openings", 0) for r in now_), sum(r.get("openings", 0) for r in prev)
                    pause = sum(r.get("pause_min", 0) for r in now_) / 60
                    temps = [r["avg_temp"] for r in now_ if r.get("avg_temp") is not None]
                    line = f"Heizen {room.get('name') or rid}: {h:.1f} Std. geheizt (Vorwoche {hp:.1f}), {o}× Fenster geöffnet (Vorwoche {op}), {pause:.1f} Std. Fensterpause"
                    if temps:
                        line += f", Ø {sum(temps) / len(temps):.1f} °C"
                    a = ana.get(rid) or {}
                    if a.get("verdict") and a["verdict"] != "nodata":
                        line += f", Heizleistung {VERD.get(a['verdict'], a['verdict'])}"
                    warn = [x["title"] for x in a.get("findings") or [] if x.get("level") == "warn"]
                    if warn:
                        line += f" – Auffällig: {', '.join(warn[:2])}"
                    out.append(line)
                outs = [r["outside_avg"] for rows in rep.values() for r in rows[7:] if r.get("outside_avg") is not None]
                outp = [r["outside_avg"] for rows in rep.values() for r in rows[:7] if r.get("outside_avg") is not None]
                if outs:
                    out.append(f"Außentemperatur Ø {sum(outs) / len(outs):.1f} °C" + (f" (Vorwoche {sum(outp) / len(outp):.1f} °C)" if outp else ""))
            except Exception:  # noqa: BLE001
                pass
        lw = self._mod(MODULE_LIGHT)
        if lw is not None:
            try:
                rep = lw.report()
                ls = sorted(rep.get("lights", {}).items(), key=lambda kv: -kv[1]["week_h"])
                if ls:
                    out.append("Licht: " + ", ".join(f"{lw._name(e)} {x['week_h']:.0f} Std." + (f" ({x['manual']}× von Hand)" if x.get("manual") else "") for e, x in ls[:4]))
                for x in (rep.get("suggestions") or [])[:2]:
                    out.append(f"Licht-Vorschlag: {x.get('text')}")
            except Exception:  # noqa: BLE001
                pass
        return out

    async def async_ai_text(self, lines: list[str]) -> tuple[str | None, str | None]:
        """Bericht von der KI formulieren lassen (Home Assistant „AI Task“). Antwort: (Text, Fehler)."""
        ent = self.ai_entity()
        if not ent:
            return None, "keine KI eingerichtet (AI Task)"
        facts = "\n".join(f"- {x}" for x in [*self._facts(), *lines])
        try:
            res = await asyncio.wait_for(self.hass.services.async_call(
                "ai_task", "generate_data", {"task_name": "Hauswerk Wochenbericht", "entity_id": ent, "instructions": AI_INSTRUCTIONS + facts},
                blocking=True, return_response=True, context=self._ctx), timeout=90)
        except Exception as err:  # noqa: BLE001 - Netz, Kontingent, Zeitüberschreitung
            _LOGGER.warning("Wochenbericht mit KI fehlgeschlagen: %s", err)
            return None, f"KI nicht erreichbar ({err.__class__.__name__}: {err})"[:200]
        text = str((res or {}).get("data") or "").strip()
        return (text[:900], None) if text else (None, "KI hat nichts geliefert")

    async def async_weekly_report(self, ai: bool | None = None) -> dict[str, Any]:
        """Das Wichtigste der letzten 7 Tage aus allen Modulen – kurz, je Modul eine Zeile; auf Wunsch von der KI formuliert."""
        rep = await self._async_weekly_lines()
        if ai if ai is not None else self.settings.get("hd_ai"):
            rep["ai_text"], rep["ai_error"] = await self.async_ai_text(rep["lines"])
            if rep["ai_text"]:
                rep["text"] = rep["ai_text"]
        return rep

    async def _async_weekly_lines(self) -> dict[str, Any]:
        lines: list[str] = []
        ctl = self._mod(MODULE_HEATING)
        if ctl is not None:
            try:
                rep = ctl.report(7)
                heat = sum(r.get("heat_min", 0) for rows in rep.values() for r in rows) / 60
                opens = sum(r.get("openings", 0) for rows in rep.values() for r in rows)
                temps = [r["avg_temp"] for rows in rep.values() for r in rows if r.get("avg_temp") is not None]
                lines.append(f"🔥 Heizwerk: {heat:.0f} Std. geheizt (alle Räume), Ø {sum(temps) / len(temps):.1f} °C, {opens}× Fenster geöffnet"
                             if temps else f"🔥 Heizwerk: {heat:.0f} Std. geheizt, {opens}× Fenster geöffnet")
            except Exception:  # noqa: BLE001
                pass
        energy = await self._async_energy_week()
        if energy:
            lines.append(energy)
        lw = self._mod(MODULE_LIGHT)
        if lw is not None:
            try:
                rep = lw.report()
                hours = sum(x["week_h"] for x in rep.get("lights", {}).values())
                kwh = sum(x["kwh"] or 0 for x in rep.get("lights", {}).values())
                lines.append(f"💡 Lichtwerk: {hours:.0f} Std. Licht" + (f", {kwh:.1f} kWh" if kwh else ""))
            except Exception:  # noqa: BLE001
                pass
        bw = self._mod(MODULE_GARDEN)
        if bw is not None and bw.mower():
            try:
                st = bw.stats()
                if st["week_hours"] or st["week_errors"]:
                    lines.append(f"🤖 Beetwerk: {st['week_hours']:.1f} Std. gemäht" + (f", {st['week_errors']} Fehler" if st["week_errors"] else ""))
            except Exception:  # noqa: BLE001
                pass
        ww = self._mod(MODULE_SECURITY)
        if ww is not None:
            try:
                st = ww.status()
                bits = []
                if st.get("bell") and st["bell"]["week"]:
                    bits.append(f"{st['bell']['week']}× geklingelt")
                if st.get("warnings"):
                    bits.append(f"{len(st['warnings'])} Warnung(en) aktiv")
                if bits:
                    lines.append("🛡️ Wachwerk: " + ", ".join(bits))
            except Exception:  # noqa: BLE001
                pass
        due = [t for t in self.tasks() if t.get("left") is not None and t["left"] <= 7]
        if due:
            lines.append("🔧 Wartung: " + ", ".join(t["name"] for t in due[:4]) + (f" und {len(due) - 4} weitere" if len(due) > 4 else ""))
        return {"title": "Wochenbericht", "text": "\n".join(lines) or "Eine ruhige Woche – nichts Besonderes.", "lines": lines}

    async def _async_energy_week(self) -> str | None:
        """Energie der letzten 7 Tage aus dem Energie-Dashboard: Solar, Netzbezug, Einspeisung."""
        try:
            from homeassistant.components.energy.data import async_get_manager  # noqa: PLC0415
            from homeassistant.components.recorder import get_instance  # noqa: PLC0415
            from homeassistant.components.recorder.statistics import statistics_during_period  # noqa: PLC0415
        except ImportError:
            return None
        try:
            prefs = (await async_get_manager(self.hass)).data or {}
            src = prefs.get("energy_sources") or []
            solar = [s["stat_energy_from"] for s in src if s.get("type") == "solar" and s.get("stat_energy_from")]
            grid_in = [f["stat_energy_from"] for s in src if s.get("type") == "grid" for f in s.get("flow_from") or [] if f.get("stat_energy_from")]
            grid_out = [f["stat_energy_to"] for s in src if s.get("type") == "grid" for f in s.get("flow_to") or [] if f.get("stat_energy_to")]
            ids = solar + grid_in + grid_out
            if not ids:
                return None
            end = dt_util.start_of_local_day()
            start = end - timedelta(days=7)
            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period, self.hass, start, end, set(ids), "day", None, {"change"})

            def total(group: list[str]) -> float:
                return sum((r.get("change") or 0) for sid in group for r in stats.get(sid) or [])

            sol, imp, exp = total(solar), total(grid_in), total(grid_out)
            parts = []
            if solar:
                parts.append(f"{sol:.0f} kWh Solar")
            parts.append(f"{imp:.0f} kWh Netzbezug")
            if grid_out:
                parts.append(f"{exp:.0f} kWh eingespeist")
            return "⚡ Kraftwerk: " + ", ".join(parts)
        except Exception:  # noqa: BLE001 - Energie-Dashboard nicht eingerichtet
            return None

    # ------------------------------------------------------------ Status
    def status(self) -> dict[str, Any]:
        return {
            "modes": {k: {"name": v["name"], "icon": v["icon"], "actions": self.mode_actions(k)} for k, v in MODES.items()},
            "actions": MODE_ACTIONS,
            "last_mode": self._persist.get("last_mode"),
            "tasks": self.tasks(),
            "history": (self._persist.get("history") or [])[:60],
            "costs": self.costs(),
            "templates": TASK_TEMPLATES,
            "weekly_sent": self._persist.get("weekly_sent"),
            "ai_entity": self.ai_entity(),
        }
