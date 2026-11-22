"""Hausdienste – gehören zum Hauswerk-Kern und wirken über alle Module:

- Hausmodi: „Gute Nacht“, „Guten Morgen“, „Wir gehen“, „Wir sind da“ – ein Tipp, alle Module.
- Wartung: was im Haus fällig ist (eigene Aufgaben mit Intervall plus Batterien und Lebensdauer der Melder).
- Wochenbericht: eine Nachricht mit dem Wichtigsten der Woche aus allen Modulen.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, timedelta
from typing import Any

from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (DOMAIN, MODE_ACTIONS, MODULE_GARDEN, MODULE_HEATING, MODULE_LIGHT, MODULE_SECURITY, MODULE_SHUTTER,
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
TASK_TEMPLATES = [
    {"name": "Rauchmelder testen", "icon": "mdi:smoke-detector-variant", "days": 365},
    {"name": "Heizkörper entlüften", "icon": "mdi:radiator", "days": 365},
    {"name": "Filter Dunstabzug reinigen", "icon": "mdi:stove", "days": 90},
    {"name": "Wasserfilter wechseln", "icon": "mdi:water-check-outline", "days": 180},
    {"name": "Lüftungsfilter wechseln", "icon": "mdi:air-filter", "days": 180},
    {"name": "Waschmaschine reinigen (Kochwäsche, Flusensieb)", "icon": "mdi:washing-machine", "days": 60},
    {"name": "Geschirrspüler: Sieb reinigen", "icon": "mdi:dishwasher", "days": 30},
    {"name": "Dachrinne reinigen", "icon": "mdi:home-roof", "days": 365},
]

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
    "hd_tasks": [],               # [{id, name, icon, days, last}]
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
        haus.extra_status["dienste"] = self.status

    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        self.settings.update({k: v for k, v in (stored.get("settings") or {}).items() if k in HD_KEYS})
        self._persist = stored.get("persist") or {}

    async def async_start(self) -> None:
        self._unsubs.append(async_track_time_interval(self.hass, self._async_tick, timedelta(minutes=1)))

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self._store.async_save(self._data())

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
        self.settings.update(settings)
        self._save()
        self._check_tasks()

    def _mod(self, key: str):
        return (self.hass.data.get(DOMAIN) or {}).get(key)

    async def _async_tick(self, _now=None) -> None:
        self._check_tasks()
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
    def _due(self, t: dict, today: date) -> tuple[date | None, int | None]:
        """Fällig am, Tage bis dahin (negativ = überfällig)."""
        days = int(t.get("days") or 0)
        if not days:
            return None, None
        last = date.fromisoformat(t["last"]) if t.get("last") else None
        if last is None:
            return today, 0
        due = last + timedelta(days=days)
        return due, (due - today).days

    def tasks(self) -> list[dict[str, Any]]:
        """Eigene Aufgaben plus automatisch erkannte (Batterie schwach, Melder am Lebensende, Mähermesser)."""
        today = dt_util.now().date()
        out = []
        for t in self.settings.get("hd_tasks") or []:
            due, left = self._due(t, today)
            out.append({**t, "auto": False, "due": due.isoformat() if due else None, "left": left})
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
        return sorted(out, key=lambda t: (t["left"] is None, t["left"] if t["left"] is not None else 0, t["name"]))

    def _check_tasks(self) -> None:
        """Fällige eigene Aufgaben melden (Benachrichtigungen › Hauswerk › Wartung)."""
        today = dt_util.now().date()
        for t in self.settings.get("hd_tasks") or []:
            _due, left = self._due(t, today)
            key = f"maint:{t.get('id')}"
            if left is not None and left <= 0:
                self.haus.notify(key, "maint", "Wartung fällig", t.get("name") or "Aufgabe")
            else:
                self.haus.clear(key)

    async def async_task_done(self, task_id: str, by: str | None = None) -> None:
        tasks = self.settings.get("hd_tasks") or []
        for t in tasks:
            if t.get("id") == task_id:
                t["last"] = dt_util.now().date().isoformat()
                self.log.add("settings", f"Wartung erledigt: {t.get('name')}", by or "", module="haus")
        self.settings["hd_tasks"] = tasks
        self._save()
        self._check_tasks()

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
        self.haus.notify(f"weekly:{week}", "weekly", rep["title"], rep["text"])
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
            "templates": TASK_TEMPLATES,
            "weekly_sent": self._persist.get("weekly_sent"),
            "ai_entity": self.ai_entity(),
        }
