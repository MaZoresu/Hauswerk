"""Kraftwerk: lernende Fertigerkennung für Waschmaschine, Trockner, Geschirrspüler & Co.

Aufbau
- ``Detector``: reine Logik ohne Home Assistant (testbar). Bekommt Messwerte (Watt oder None = fehlt)
  und Zeitpunkte, führt den Zustand (Bereit → Läuft → Ende wird geprüft → Fertig) und lernt aus
  abgeschlossenen Durchläufen.
- ``Appliances``: verbindet die Detektoren mit Home Assistant (Sensoren, Speicher, Nachrichten).

Wie gelernt wird (nachvollziehbar, nur aus beobachteten Durchläufen)
- Jeder Durchlauf speichert Dauer, Energie, Spitzenleistung, alle Ruhephasen mitten im Programm
  (Einweichen, Pumpenpausen …) und den Nachlauf danach (Knitterschutz, Anzeige, Standby).
- Daraus: typische Dauer, längste Pause (90-%-Wert), Leistung „aktiv“ gegenüber „ruhig“,
  Spitzen im Nachlauf. Die Wartezeit bis „Fertig“ = längste gelernte Pause × 1,3 + 2 Min.
- Korrekturen fließen ein: „Läuft noch“ macht die verwechselte Ruhe zur Pause (längeres Warten),
  „Ist schon fertig“ merkt sich, nach wie viel Ruhe es wirklich fertig war (kürzeres Warten),
  „Kein Durchlauf“ hebt die Mindestenergie für einen Start an.
- Vor dem ersten Durchlauf gelten vorsichtige Werte je Gerätetyp („Lernphase“ bis 3 Durchläufe).

Messwerte
- Viele Steckdosen melden nur bei Änderung: Ein Wert gilt, bis ein neuer kommt.
- Fehlt ein Wert (unavailable/unknown, Neustart), zählt diese Zeit weder als Ruhe noch als Betrieb –
  fehlende Messwerte werden nie als Programmende gewertet.
"""
from __future__ import annotations

import statistics
from typing import Any

# Startwerte je Gerätetyp (vorsichtig, bis gelernt): Start ab, aktiv ab, Wartezeit bis fertig,
# kurze Spitzen (Knitterschutz, Pumpe) bis, Mindestdauer, Mindestenergie eines Durchlaufs
TYPES: dict[str, dict[str, Any]] = {
    "waschmaschine": {"label": "Waschmaschine", "icon": "mdi:washing-machine", "start_w": 10, "active_w": 8,
                      "end_wait": 30 * 60, "spike_s": 120, "min_run": 10 * 60, "min_wh": 20},
    "trockner": {"label": "Trockner", "icon": "mdi:tumble-dryer", "start_w": 20, "active_w": 20,
                 "end_wait": 8 * 60, "spike_s": 180, "min_run": 10 * 60, "min_wh": 50},
    "geschirrspueler": {"label": "Geschirrspüler", "icon": "mdi:dishwasher", "start_w": 10, "active_w": 8,
                        "end_wait": 40 * 60, "spike_s": 120, "min_run": 15 * 60, "min_wh": 50},
    "sonstiges": {"label": "Gerät", "icon": "mdi:power-plug-outline", "start_w": 10, "active_w": 8,
                  "end_wait": 15 * 60, "spike_s": 120, "min_run": 5 * 60, "min_wh": 10},
}
LEARNED = 3            # ab so vielen Durchläufen gilt das Gerät als gelernt
KEEP_RUNS = 20         # gespeicherte Durchläufe je Gerät
TAIL_MAX = 3 * 3600    # Nachlauf höchstens so lange beobachten
DONE_SHOW = 6 * 3600   # „Fertig“ so lange anzeigen (oder bis zum nächsten Start / „Gesehen“)
CHECK_AFTER = 120      # ab so viel Ruhe heißt es „Ende wird geprüft“

STATE_LABELS = {"idle": "Bereit", "running": "Läuft", "ending": "Ende wird geprüft", "done": "Fertig"}


def to_watt(value: Any, unit: str | None) -> float | None:
    """Messwert in Watt (W, kW, mW); None, wenn nicht lesbar."""
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None
    unit = (unit or "W").strip()
    if unit == "kW":
        return val * 1000
    if unit == "mW":
        return val / 1000
    if unit == "MW":
        return val * 1_000_000
    return val


def _q(values: list[float], q: float) -> float:
    """Quantil ohne numpy (linear)."""
    vals = sorted(values)
    if not vals:
        return 0.0
    pos = (len(vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


class Detector:
    """Zustand und Lernen eines Geräts – ohne Home Assistant."""

    def __init__(self, kind: str = "sonstiges", data: dict | None = None) -> None:
        self.kind = kind if kind in TYPES else "sonstiges"
        data = data or {}
        self.runs: list[dict] = data.get("runs") or []          # abgeschlossene Durchläufe
        self.false: list[dict] = data.get("false") or []        # „Kein Durchlauf“
        self.confirm: list[float] = data.get("confirm") or []   # Ruhe bis „Ist schon fertig“ (s)
        self.quiet_levels: list[float] = data.get("quiet_levels") or []  # Leistung in Ruhe/Standby (W)
        self.intervals: list[float] = data.get("intervals") or []        # Abstände der Messwerte (s)
        st = data.get("state") or {}
        self.state: str = st.get("state", "idle")
        self.run: dict | None = st.get("run")
        self.last: dict | None = st.get("last")                 # zuletzt fertiger Durchlauf (für Korrektur/Nachlauf)
        self.done_at: float | None = st.get("done_at")
        self.last_t: float | None = st.get("last_t")
        self.last_w: float | None = None                        # nach Neustart unbekannt: zählt als Lücke
        self.cand: float = 0.0                                  # Sekunden über der Startschwelle (Bereit)
        self.active_acc: float = 0.0                            # Sekunden am Stück aktiv (Läuft/Prüfen)
        self.events: list[tuple[str, dict]] = []
        self.model: dict = {}
        self._learn()

    # ------------------------------------------------------------ Speicher
    def dump(self) -> dict:
        return {"runs": self.runs[-KEEP_RUNS:], "false": self.false[-10:], "confirm": self.confirm[-10:],
                "quiet_levels": self.quiet_levels[-50:], "intervals": self.intervals[-100:],
                "state": {"state": self.state, "run": self.run, "last": self.last, "done_at": self.done_at,
                          "last_t": self.last_t}}

    # ------------------------------------------------------------ Lernen
    def _learn(self) -> None:
        """Werte aus den beobachteten Durchläufen ableiten (mit Begründung für die Anzeige)."""
        d = TYPES[self.kind]
        runs = [r for r in self.runs if r.get("dur")][-15:]
        n = len(runs)
        m: dict[str, Any] = {"n": n, "learning": n < LEARNED}
        # Ruhe-Leistung (Pausen, Anzeige, Standby): „aktiv“ liegt deutlich darüber
        quiet = _q(self.quiet_levels, 0.9) if self.quiet_levels else None
        active_w = float(d["active_w"])
        if quiet is not None:
            active_w = max(active_w, round(quiet * 2.5, 1))
        m["quiet_w"] = round(quiet, 2) if quiet is not None else None
        m["active_w"] = active_w
        m["start_w"] = max(float(d["start_w"]), active_w)
        # längste Pause mitten im Programm
        pauses = [r.get("max_pause", 0) for r in runs]
        pause_max = (_q(pauses, 0.9) if n >= 5 else max(pauses)) if pauses else 0.0
        m["pause_max"] = round(pause_max)
        if n:
            end_wait = max(pause_max * 1.3 + 120, 180.0)
            # „Ist schon fertig“: so viel Ruhe reichte wirklich – aber nie kürzer als die längste Pause
            if self.confirm:
                ok = statistics.median(self.confirm)
                if pause_max + 60 < ok < end_wait:
                    end_wait = max(ok, pause_max + 60)
            if n < LEARNED:
                end_wait = max(end_wait, float(d["end_wait"]) * (LEARNED - n) / LEARNED)  # vorsichtig, solange wenige
            m["end_wait"] = round(min(end_wait, 3 * 3600))
        else:
            m["end_wait"] = float(d["end_wait"])
        # Messabstand: Wartezeit nie kürzer als drei Messungen
        if self.intervals:
            iv = statistics.median(self.intervals)
            m["interval"] = round(iv)
            m["end_wait"] = max(m["end_wait"], min(3 * iv, 1800))
        else:
            m["interval"] = None
        # Dauer
        durs = [r["dur"] for r in runs]
        m["dur_med"] = round(statistics.median(durs)) if durs else None
        m["dur_lo"] = round(_q(durs, 0.1)) if durs else None
        m["dur_hi"] = round(_q(durs, 0.9)) if durs else None
        m["kwh_med"] = round(statistics.median([r.get("wh", 0) for r in runs]) / 1000, 2) if runs else None
        # Mindestdauer und -energie: aus den Durchläufen und „Kein Durchlauf“-Korrekturen
        m["min_run"] = max(float(d["min_run"]) if not durs else min(float(d["min_run"]), 0.5 * min(durs)), 120.0)
        min_wh = float(d["min_wh"])
        if self.false:
            min_wh = max(min_wh, max(f.get("wh", 0) for f in self.false) * 1.2)
        if runs:
            min_wh = min(min_wh, 0.5 * min(r.get("wh", 0) for r in runs) or min_wh)
        m["min_wh"] = round(min_wh, 1)
        # Nachlauf: kurze Spitzen (Knitterschutz) nicht als neuen Start werten
        tails = [r.get("tail") or {} for r in runs]
        spike = max([t.get("spike_s", 0) for t in tails] + [0])
        m["spike_s"] = max(float(d["spike_s"]), spike * 1.5)
        m["tail_w"] = max([t.get("spike_w", 0) for t in tails] + [0]) or None
        m["tail_s"] = max([t.get("dur", 0) for t in tails] + [0]) or None
        self.model = m

    # ------------------------------------------------------------ Messwerte
    def feed(self, t: float, watt: float | None) -> None:
        """Neuer Messwert (oder None = fehlt). Erst die Zeit bis jetzt mit dem alten Wert auswerten."""
        if self.last_t is not None and watt is not None and self.last_w is not None and t > self.last_t:
            gap = t - self.last_t
            if 1 <= gap <= 3600:
                self.intervals.append(round(gap))
        self._advance(t)
        self.last_w = watt
        self._check(t)

    def tick(self, t: float) -> None:
        """Zeit vergeht ohne neuen Wert: der letzte Wert gilt weiter."""
        self._advance(t)
        self._check(t)

    def _advance(self, t: float) -> None:
        if self.last_t is None:
            self.last_t = t
            return
        dt = t - self.last_t
        self.last_t = t
        if dt <= 0:
            return
        w = self.last_w
        if w is None:
            return  # Lücke: weder Ruhe noch Betrieb
        m = self.model
        active = w >= m["active_w"]
        if self.state == "idle" or self.state == "done":
            if self.state == "done" and self.last is not None:
                self._tail(dt, w, active)
            if w >= m["start_w"]:
                self.cand += dt
            else:
                self.cand = 0.0
                if self.state == "idle" and w < m["active_w"]:
                    self._note_quiet(w)
            return
        run = self.run
        assert run is not None
        run["wh"] = run.get("wh", 0.0) + w * dt / 3600
        run["peak"] = max(run.get("peak", 0.0), w)
        if active:
            self.active_acc += dt
            if self.state == "ending" and (self.active_acc >= m["spike_s"] or w >= 10 * m["active_w"]):
                # echte Aktivität nach Ruhe: es war eine Pause
                run.setdefault("pauses", []).append(round(run.get("quiet", 0)))
                run["quiet"] = 0.0
                self.state = "running"
            if self.state == "running":
                run["quiet"] = 0.0
                run["last_active"] = self.last_t
        else:
            self.active_acc = 0.0
            run["quiet"] = run.get("quiet", 0.0) + dt
            run["quiet_w"] = max(run.get("quiet_w", 0.0), w)
            self._note_quiet(w)

    def _note_quiet(self, w: float) -> None:
        if not self.quiet_levels or abs(self.quiet_levels[-1] - w) > 0.05:
            self.quiet_levels.append(round(w, 2))
            self.quiet_levels = self.quiet_levels[-50:]

    def _tail(self, dt: float, w: float, active: bool) -> None:
        """Nachlauf nach dem Ende beobachten (Knitterschutz-Spitzen, Anzeige)."""
        tail = self.last.setdefault("tail", {"spike_s": 0, "spike_w": 0, "dur": 0, "cur": 0})
        since_end = (self.last_t or 0) - (self.last.get("end") or 0)
        if since_end > TAIL_MAX:
            return
        if w >= 1.0:  # mehr als reines Standby: gehört zum Nachlauf
            tail["dur"] = round(since_end)
        if active:
            tail["cur"] = tail.get("cur", 0) + dt
            tail["spike_w"] = max(tail.get("spike_w", 0), round(w, 1))
            tail["spike_s"] = max(tail.get("spike_s", 0), round(tail["cur"]))
        else:
            tail["cur"] = 0

    def _check(self, t: float) -> None:
        m = self.model
        # Start
        if self.state in ("idle", "done") and self.last_w is not None and (
                self.cand >= 60 or self.last_w >= 10 * m["start_w"]):
            if self.state == "done" and self.last is not None and self._is_tail_spike():
                return
            self._start(t)
            return
        if self.state not in ("running", "ending"):
            if self.state == "done" and self.done_at and t - self.done_at > DONE_SHOW:
                self.state = "idle"
            return
        run = self.run
        quiet = run.get("quiet", 0.0)
        if self.state == "running" and quiet >= CHECK_AFTER:
            self.state = "ending"
            self.events.append(("checking", {"quiet": quiet}))
        if self.state == "ending":
            elapsed = (run.get("last_active") or t) - run["start"]
            wait = float(m["end_wait"])
            if m.get("dur_lo") and elapsed < 0.6 * m["dur_lo"]:
                wait *= 1.5  # deutlich vor der üblichen Dauer: länger prüfen
            run["wait"] = round(wait)
            if quiet >= wait:
                self._finish(t, "Ruhe")

    def _is_tail_spike(self) -> bool:
        """Kurze Spitze im Nachlauf (Knitterschutz) statt neuem Start?"""
        m = self.model
        since = (self.last_t or 0) - (self.last.get("end") or 0)
        return since < max(m.get("tail_s") or 0, 3600) * 1.2 and (self.last_w or 0) < 10 * m["start_w"] \
            and self.cand < m["spike_s"]

    def _start(self, t: float) -> None:
        self.run = {"id": f"{int(t)}", "start": t - self.cand, "last_active": t, "wh": 0.0, "peak": self.last_w or 0,
                    "pauses": [], "quiet": 0.0, "quiet_w": 0.0}
        self.state = "running"
        self.cand = 0.0
        self.active_acc = 0.0
        self.done_at = None
        self.events.append(("start", {"id": self.run["id"]}))

    def _finish(self, t: float, why: str) -> None:
        """Durchlauf beendet: plausibel? Dann merken und lernen."""
        run = self.run
        m = self.model
        end = run.get("last_active") or t
        dur = end - run["start"]
        self.run = None
        self.active_acc = 0.0
        if dur < m["min_run"] or run.get("wh", 0) < m["min_wh"]:
            self.state = "idle"
            self.events.append(("discard", {"id": run["id"], "dur": dur, "wh": run.get("wh", 0)}))
            return
        rec = {"id": run["id"], "start": run["start"], "end": end, "dur": round(dur), "wh": round(run.get("wh", 0), 1),
               "peak": round(run.get("peak", 0)), "pauses": run.get("pauses", []),
               "max_pause": max(run.get("pauses", []) + [0]), "quiet_w": round(run.get("quiet_w", 0), 2),
               "why": why, "detected": t}
        self.runs.append(rec)
        self.runs = self.runs[-KEEP_RUNS:]
        self.last = rec
        self.state = "done"
        self.done_at = t
        self._learn()
        self.events.append(("done", dict(rec)))

    # ------------------------------------------------------------ von außen
    def door_open(self, t: float) -> None:
        """Tür geöffnet (Zusatzsensor): in der Prüfung = fertig; „Fertig“ wird damit gesehen."""
        if self.state == "ending":
            self.confirm.append(round((self.run or {}).get("quiet", 0)))
            self._finish(t, "Tür geöffnet")
        elif self.state == "done":
            self.state = "idle"

    def status_done(self, t: float) -> None:
        """Gerät meldet selbst „fertig“ (Zusatzsensor)."""
        if self.state in ("running", "ending"):
            if self.state == "ending":
                self.confirm.append(round((self.run or {}).get("quiet", 0)))
            self._finish(t, "Gerät meldet fertig")

    def correct(self, action: str, t: float) -> str | None:
        """Korrektur aus dem Panel; Rückgabe: Text fürs Protokoll."""
        if action == "still_running" and self.state in ("done", "idle") and self.last and self.runs \
                and self.runs[-1]["id"] == self.last["id"] and t - (self.last.get("detected") or t) < 6 * 3600:
            # die Ruhe war eine Pause: zurück zu „Läuft“, Pause merken
            rec = self.runs.pop()
            pause = (t - rec["end"]) if self.last_w is not None and self.last_w < self.model["active_w"] else (rec["detected"] - rec["end"])
            # neue ID: die echte Fertigmeldung darf nach der Korrektur noch einmal kommen
            self.run = {"id": rec["id"].split("-")[0] + "-k", "start": rec["start"], "last_active": rec["end"], "wh": rec["wh"],
                        "peak": rec["peak"], "pauses": rec["pauses"] + [round(max(pause, rec["detected"] - rec["end"]))],
                        "quiet": 0.0, "quiet_w": rec["quiet_w"], "corrected": True}
            self.last = None
            self.state = "running"
            self.done_at = None
            self._learn_pause_hint(round(rec["detected"] - rec["end"]))
            return f"Läuft noch – die Ruhe von {round((rec['detected'] - rec['end']) / 60)} Min. war eine Pause, künftig wird länger geprüft"
        if action == "finished" and self.state in ("running", "ending") and self.run:
            quiet = round(self.run.get("quiet", 0))
            if quiet >= 60:
                self.confirm.append(quiet)
            self._finish(t, "von Hand bestätigt")
            if self.state == "idle":  # zu kurz/zu wenig: trotzdem als fertig zeigen
                self.state = "done"
                self.done_at = t
            return f"Ist schon fertig – nach {round(quiet / 60)} Min. Ruhe" if quiet >= 60 else "Ist schon fertig"
        if action == "no_run":
            if self.state in ("running", "ending") and self.run:
                self.false.append({"wh": round(self.run.get("wh", 0), 1), "dur": round(t - self.run["start"])})
                self.run = None
            elif self.state == "done" and self.last and self.runs and self.runs[-1]["id"] == self.last["id"]:
                rec = self.runs.pop()
                self.false.append({"wh": rec["wh"], "dur": rec["dur"]})
                self.last = None
            else:
                return None
            self.state = "idle"
            self.done_at = None
            self._learn()
            return f"Kein Durchlauf – Start erst ab {self.model['min_wh']:.0f} Wh"
        if action == "ack" and self.state == "done":
            self.state = "idle"
            return "Gesehen"
        if action == "reset":
            self.runs, self.false, self.confirm, self.quiet_levels = [], [], [], []
            self.last = None
            self._learn()
            return "Gelerntes gelöscht – Lernphase beginnt neu"
        return None

    def _learn_pause_hint(self, pause: int) -> None:
        """„Läuft noch“: die verwechselte Ruhe als Pause in den letzten Durchläufen berücksichtigen."""
        if self.runs:
            self.runs[-1]["max_pause"] = max(self.runs[-1].get("max_pause", 0), pause)
        self.confirm = [c for c in self.confirm if c > pause]
        self._learn()
        self.model["end_wait"] = max(self.model["end_wait"], pause * 1.3 + 120)

    # ------------------------------------------------------------ Anzeige
    def status(self, t: float) -> dict:
        m = self.model
        out: dict[str, Any] = {"state": self.state, "label": STATE_LABELS[self.state], "learning": m["learning"],
                               "n": m["n"], "model": m, "watt": self.last_w, "gap": self.last_w is None}
        if self.run:
            run = self.run
            out["run"] = {"id": run["id"], "start": run["start"], "elapsed": round(t - run["start"]),
                          "wh": round(run.get("wh", 0), 1), "quiet": round(run.get("quiet", 0)),
                          "wait": run.get("wait") or m["end_wait"], "pauses": len(run.get("pauses", []))}
            if m.get("dur_med"):
                out["run"]["eta"] = run["start"] + m["dur_med"]
        if self.last:
            out["last"] = {k: self.last.get(k) for k in ("id", "start", "end", "dur", "wh", "why", "detected")}
        out["history"] = [{k: r.get(k) for k in ("start", "dur", "wh", "max_pause", "why")} for r in self.runs[-8:]][::-1]
        return out
