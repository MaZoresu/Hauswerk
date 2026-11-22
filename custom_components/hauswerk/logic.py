"""Regel-Logik des Hauswerk-Moduls Heizen (ohne Home-Assistant-Abhängigkeit, testbar)."""
from __future__ import annotations

from datetime import datetime
import math
import re
from typing import Any, Callable

DAY_MIN = 1440
WEEK_MIN = 7 * DAY_MIN

TYPE_RADIATOR = "heizkoerper"
TYPE_FLOOR = "flaeche"

# Voreinstellungen je Heizungsart. Flächenheizungen sind träge: lange
# Fensterverzögerung, frühes Vorheizen und nur geringe Absenkung lohnen sich.
TYPE_DEFAULTS: dict[str, dict[str, Any]] = {
    TYPE_RADIATOR: {
        "window_delay": 60,        # Sekunden bis zur Fensterpause
        "resume_delay": 0,         # Sekunden nach dem Schließen
        "pause_mode": "frost",     # frost | off
        "lead_min": 15,            # Vorheizen vor Komfortbeginn
        "max_setback": 0,          # 0 = unbegrenzt
        "compensation": False,     # Thermostat auf Raumsensor nachführen
        "presence_on": 2,          # Minuten Bewegung, bis der Raum als belegt gilt
        "presence_off": 20,        # Minuten ohne Bewegung, bis der Raum als leer gilt
        "off_above": 0,            # K über Soll, ab denen abgeschaltet wird (0 = nie)
        "aggressive_range": 0,     # K Abweichung, ab der übersteuert wird (0 = aus)
        "aggressive_offset": 1.5,  # K Übersteuerung
        "valve_diff": 1.5,         # K unter Soll, ab denen das Ventil ganz offen ist
        "valve_max": 100,          # % maximale Ventilöffnung
        "preheat_mode": "fixed",   # fixed = feste Vorlaufzeit | smart = lernt die Aufheizgeschwindigkeit
        "preheat_max": 90,         # Minuten, höchstens so früh wird lernend vorgeheizt
        "heat_rate": 2.0,          # K pro Stunde, Startwert bis Hauswerk den Raum kennt
    },
    TYPE_FLOOR: {
        "window_delay": 900,
        "resume_delay": 0,
        "pause_mode": "frost",
        "lead_min": 120,
        "max_setback": 2.0,
        "compensation": False,
        "presence_on": 5,
        "presence_off": 60,
        "off_above": 0,
        "aggressive_range": 0,
        "aggressive_offset": 0.5,
        "valve_diff": 1.0,
        "valve_max": 100,
        "preheat_mode": "fixed",
        "preheat_max": 240,
        "heat_rate": 0.5,
    },
}

MODES = {
    "aus": "Automatik aus",
    "fenster": "Fenster offen",
    "entkalken": "Entkalken",
    "sommer": "Sommerpause",
    "boost": "Boost",
    "manuell": "Manuell",
    "party": "Party",
    "urlaub": "Urlaub",
    "abwesend": "Abwesend",
    "leer": "Raum leer",
    "belegt": "Jemand da",
    "warm": "Warm genug",
    "vorheizen": "Vorheizen",
    "komfort": "Komfort",
    "eco": "Eco",
    "eco_fix": "Eco erzwungen",
    "frost": "Frostschutz",
}

MIN_TEMP = 5.0
MAX_TEMP = 30.0
MAX_COMPENSATION = 4.0


def parse_hm(value: str) -> int:
    """'HH:MM' oder 'HH:MM:SS' -> Minuten seit Mitternacht (24:00 erlaubt, Sekunden zählen nicht)."""
    parts = str(value).strip().split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"Ungültige Uhrzeit: {value}")
    hours, minutes = parts[0], parts[1]
    total = int(hours) * 60 + int(minutes)
    if not 0 <= total <= DAY_MIN:
        raise ValueError(f"Ungültige Uhrzeit: {value}")
    return total


def week_minute(weekday: int, hour: int, minute: int) -> int:
    """Montag 00:00 = 0."""
    return weekday * DAY_MIN + hour * 60 + minute


def room_setting(room: dict, key: str) -> Any:
    """Raumwert oder Voreinstellung der Heizungsart."""
    value = room.get(key)
    if value is None:
        value = TYPE_DEFAULTS.get(room.get("type", TYPE_RADIATOR), TYPE_DEFAULTS[TYPE_RADIATOR])[key]
    return value


# ---------------------------------------------------------------- Heizplan
# Ein Heizplan ist eine Liste von Zeitfenstern {start, end, days, kind, temp}:
#   kind "comfort" (Standard): Sollwert = eigene Temperatur des Fensters, sonst der Komfortwert des Raums
#   kind "eco": ausdrücklich Eco (Eco-Wert des Raums)
# Außerhalb aller Fenster gilt immer Eco. end <= start heißt: bis zum Folgetag (über Mitternacht); "24:00" = Mitternacht.
# Fenster dürfen sich nicht überschneiden (block_conflicts); alte Pläne werden mit resolve_overlaps bereinigt.

def _block_span(block: dict) -> tuple[int, int]:
    start, end = parse_hm(block["start"]), parse_hm(block["end"])
    if end <= start:
        end += DAY_MIN
    return start, end


def _week_blocks(blocks: list[dict]) -> list[tuple[int, int, float | None, int, str]]:
    """Wochen-Intervalle (Beginn, Ende, Temperatur, Index des Fensters, Art); Ende kann über die Woche hinausgehen."""
    out: list[tuple[int, int, float | None, int, str]] = []
    for i, block in enumerate(blocks or []):
        start, end = _block_span(block)
        days = block.get("days")
        if days is None:
            days = list(range(7))
        kind = "eco" if block.get("kind") == "eco" else "comfort"
        temp = block.get("temp") if kind == "comfort" else None
        for day in sorted(set(int(d) for d in days)):
            out.append((day * DAY_MIN + start, day * DAY_MIN + end, temp, i, kind))
    return out


def _covers(start: int, end: int, week_min: int) -> bool:
    return start <= week_min < end or start <= week_min + WEEK_MIN < end


def block_value(kind: str, temp: float | None, comfort: float, eco: float) -> float:
    if kind == "eco":
        return float(eco)
    return float(temp) if temp is not None else float(comfort)


def plan_state(blocks: list[dict], week_min: int, comfort: float, eco: float) -> dict:
    """Wirksamer Sollwert laut Heizplan mit Ursache.

    kind: "komfort" (Komfort-Fenster), "eco_window" (ausdrückliches Eco-Fenster) oder "eco" (kein Fenster = Eco).
    custom: das Fenster hat eine eigene Temperatur. start/end: Wochenminuten des Fensters.
    Überschneiden sich doch einmal Fenster (alte Daten), gewinnt Komfort vor Eco und der höhere Wert.
    """
    week_min %= WEEK_MIN
    hits = [(s, e, t, i, k) for s, e, t, i, k in _week_blocks(blocks) if _covers(s, e, week_min)]
    if not hits:
        return {"target": float(eco), "kind": "eco", "custom": False, "index": None, "start": None, "end": None}
    s, e, t, i, k = max(hits, key=lambda h: (h[4] == "comfort", block_value(h[4], h[2], comfort, eco), -h[3]))
    return {"target": block_value(k, t, comfort, eco), "kind": "komfort" if k == "comfort" else "eco_window",
            "custom": k == "comfort" and t is not None, "index": i, "start": s % WEEK_MIN, "end": e % WEEK_MIN}


def schedule_at(blocks: list[dict], week_min: int, comfort: float, eco: float) -> tuple[float, bool]:
    """Solltemperatur laut Heizplan und ob gerade ein Komfort-Fenster aktiv ist."""
    st = plan_state(blocks, week_min, comfort, eco)
    return st["target"], st["kind"] == "komfort"


def _hm_txt(m: int) -> str:
    m %= DAY_MIN
    return f"{m // 60:02d}:{m % 60:02d}"


DAY_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def block_conflicts(blocks: list[dict]) -> list[dict]:
    """Ungültige oder sich überschneidende Zeitfenster: [{i, j, day, text}] (j None = Fenster i selbst ungültig).
    Beginn = Ende ist nur als 00:00–00:00 bzw. 00:00–24:00 (ganzer Tag) erlaubt."""
    out: list[dict] = []
    for i, b in enumerate(blocks or []):
        try:
            start, end = parse_hm(b["start"]), parse_hm(b["end"])
        except (KeyError, TypeError, ValueError):
            out.append({"i": i, "j": None, "day": None, "text": f"Zeitfenster {i + 1}: ungültige Uhrzeit"})
            continue
        if start % DAY_MIN == end % DAY_MIN and not (start == 0 and end in (0, DAY_MIN)):
            out.append({"i": i, "j": None, "day": None, "text": f"Zeitfenster {i + 1}: Beginn und Ende sind gleich ({b['start']})"})
        if not b.get("days") and b.get("days") is not None:
            out.append({"i": i, "j": None, "day": None, "text": f"Zeitfenster {i + 1}: kein Wochentag gewählt"})
    if out:
        return out
    week = _week_blocks(blocks)
    seen: set[tuple[int, int]] = set()
    for a in range(len(week)):
        s1, e1, _, i, _ = week[a]
        for b in range(a + 1, len(week)):
            s2, e2, _, j, _ = week[b]
            if i == j:
                continue
            for shift in (0, WEEK_MIN, -WEEK_MIN):
                lo, hi = max(s1, s2 + shift), min(e1, e2 + shift)
                if lo < hi and (min(i, j), max(i, j)) not in seen:
                    seen.add((min(i, j), max(i, j)))
                    day = (lo // DAY_MIN) % 7
                    out.append({"i": min(i, j), "j": max(i, j), "day": day,
                                "text": f"Zeitfenster {min(i, j) + 1} und {max(i, j) + 1} überschneiden sich am {DAY_SHORT[day]} "
                                        f"{_hm_txt(lo)}–{_hm_txt(hi) if hi % DAY_MIN else '24:00'}"})
    return out


def resolve_overlaps(blocks: list[dict], winner: Callable[[int], tuple] | None = None) -> list[dict]:
    """Überschneidungen auflösen: Wo sich Fenster überlagern, behält das Fenster mit Vorrang (winner(i) größer)
    die Zeit, die anderen werden dort gekürzt bzw. geteilt. Fenster ohne Überschneidung bleiben unverändert.
    Ergebnis: neue, überschneidungsfreie Liste (gleiche Tage werden wieder zusammengefasst)."""
    if not blocks or not block_conflicts(blocks) or any(c["j"] is None for c in block_conflicts(blocks)):
        return [dict(b) for b in blocks or []]
    winner = winner or (lambda i: (0, -i))
    week = _week_blocks(blocks)
    order = sorted({i for *_, i, _ in week}, key=winner, reverse=True)
    taken: list[tuple[int, int]] = []  # vergebene Wochenminuten [s, e) im Bereich 0 … 2·WEEK_MIN
    pieces: dict[int, list[tuple[int, int]]] = {}

    def free(s: int, e: int) -> list[tuple[int, int]]:
        parts = [(s, e)]
        for ts, te in taken:
            for shift in (0, WEEK_MIN, -WEEK_MIN):
                a, b = ts + shift, te + shift
                nxt = []
                for ps, pe in parts:
                    if b <= ps or a >= pe:
                        nxt.append((ps, pe))
                        continue
                    if ps < a:
                        nxt.append((ps, a))
                    if b < pe:
                        nxt.append((b, pe))
                parts = nxt
        return parts

    for i in order:
        for s, e, _, j, _ in week:
            if j != i:
                continue
            got = free(s, e)
            pieces.setdefault(i, []).extend(got)
            taken.extend(got)
    out: list[dict] = []
    for i, b in enumerate(blocks):
        clean = {k: v for k, v in b.items() if k not in ("start", "end", "days")}
        groups: dict[tuple[int, int], list[int]] = {}
        for s, e in pieces.get(i, []):
            day, start = (s // DAY_MIN) % 7, s % DAY_MIN
            groups.setdefault((start, start + (e - s)), []).append(day)
        for (start, end), days in sorted(groups.items(), key=lambda g: (min(g[1]), g[0])):
            out.append({**clean, "start": _hm_txt(start), "end": "24:00" if end == DAY_MIN else _hm_txt(end), "days": sorted(set(days))})
    return out


def day_segments(blocks: list[dict], day: int, comfort: float, eco: float) -> list[dict]:
    """Tagesablauf (0 = Mo) wie in Kachel und Zeitleiste: [{start, end, target, kind, custom, index}] in Minuten 0–1440."""
    cuts = {0, DAY_MIN}
    base = day * DAY_MIN
    for s, e, *_ in _week_blocks(blocks):
        for shift in (0, WEEK_MIN, -WEEK_MIN):
            for m in (s + shift - base, e + shift - base):
                if 0 < m < DAY_MIN:
                    cuts.add(m)
    pts = sorted(cuts)
    segs: list[dict] = []
    for a, b in zip(pts, pts[1:]):
        st = plan_state(blocks, base + a, comfort, eco)
        seg = {"start": a, "end": b, "target": st["target"], "kind": st["kind"], "custom": st["custom"], "index": st["index"]}
        last = segs[-1] if segs else None
        if last and all(last[k] == seg[k] for k in ("target", "kind", "custom", "index")):
            last["end"] = b
        else:
            segs.append(seg)
    return segs


def plan_label(st: dict, comfort: float) -> str:
    """Ursache laut Heizplan in Worten, z. B. „Komfort 06:00–08:00“ oder „Eco (kein Zeitfenster)“."""
    span = f" {_hm_txt(st['start'])}–{_hm_txt(st['end']) if st['end'] % DAY_MIN or st['end'] == st['start'] else '24:00'}" if st.get("start") is not None else ""
    if st["kind"] == "komfort":
        return f"Komfort{span}" + (f" (eigene {_de(st['target'])} °C)" if st["custom"] else "")
    if st["kind"] == "eco_window":
        return f"Eco-Zeitfenster{span}"
    return "Eco (kein Zeitfenster)"


def _de(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def minutes_to_next_change(blocks: list[dict], week_min: int) -> int | None:
    """Minuten bis zur nächsten Blockgrenze im Heizplan."""
    points = set()
    for start, end, *_ in _week_blocks(blocks):
        points.add(start % WEEK_MIN)
        points.add(end % WEEK_MIN)
    if not points:
        return None
    week_min %= WEEK_MIN
    return min(((p - week_min) % WEEK_MIN) or WEEK_MIN for p in points)


def compute_target(
    room: dict,
    settings: dict,
    week_min: int,
    *,
    window_paused: bool,
    away: bool,
    vacation: bool,
    override: float | None,
    boost: bool = False,
    party: bool = False,
    summer: bool = False,
    liming: bool = False,
    occupied: bool | None = None,
    room_temp: float | None = None,
    was_warm: bool = False,
    lead: int | None = None,
    force_eco: bool = False,
    long_away: bool = False,
    schedule_on: bool | None = None,
    schedule_next_on: int | None = None,
) -> dict[str, Any]:
    """Ermittelt Solltemperatur und Betriebsart eines Raums – die eine, zentrale Vorrang-Logik.

    Vorrang (oben gewinnt):
      1. Automatik aus            – Heizwerk stellt nichts ein
      2. Fenster offen            – Fenster-Temperatur bzw. Frostschutz
      3. Entkalken, Sommerpause   – Schutzfunktionen
      4. Boost / von Hand         – bis zur angegebenen Zeit
      5. Eco erzwungen, Party, Urlaub, lange abwesend (Frostschutz), abwesend, Präsenzmelder
      6. Heizplan                 – Komfort-Fenster (Komfortwert oder eigene Temperatur), Eco-Fenster, sonst Eco;
                                    Vorheizen vor einem Komfort-Fenster
    Danach: höchstens x °C absenken (max_setback) und „warm genug“ (Thermostat aus).
    Ergebnis enthält neben Sollwert und Betriebsart die Ursache (cause) und den Planwert (plan_target, plan_label),
    damit Kachel, Zeitleiste und Steuerung dasselbe anzeigen.

    schedule_on/schedule_next_on: Zustand eines Home-Assistant-Zeitplans (schedule.*),
    falls der Raum statt des eigenen Heizplans einen solchen nutzt.
    """
    comfort = float(room.get("comfort", 21))
    eco = float(room.get("eco", 18))
    frost = float(settings.get("frost_temp", 7))
    blocks = room.get("schedule") or []
    use_entity = schedule_on is not None
    next_change = schedule_next_on if use_entity else minutes_to_next_change(blocks, week_min)
    window_temp = room.get("window_temp")

    plan: dict[str, Any] = {"plan_target": None, "plan_label": None, "plan_kind": None}

    def result(mode: str, target: float | None, hvac_off: bool = False, cause: str | None = None) -> dict[str, Any]:
        if target is not None:
            target = round(min(MAX_TEMP, max(MIN_TEMP, target)), 1)
        return {"mode": mode, "target": target, "hvac_off": hvac_off, "next_change": next_change, "cause": cause, **plan}

    if not room.get("enabled", True):
        return result("aus", None, cause="Automatik aus – Heizwerk stellt nichts ein")

    if window_paused:
        # Eigene Fenster-Temperatur des Raums, sonst der allgemeine Frostschutz
        off = room_setting(room, "pause_mode") == "off"
        return result("fenster", float(window_temp) if window_temp is not None else frost, off,
                      "Fenster offen – " + ("Thermostate aus" if off else "Fensterpause"))

    if liming:
        return result("entkalken", MAX_TEMP, cause="Entkalkungsschutz – Ventile kurz ganz auf")

    if summer:
        off = settings.get("summer_action", "off") == "off"
        return result("sommer", frost, off, "Sommerpause" + (" – Thermostate aus" if off else " – Frostschutz"))

    lead = int(lead if lead is not None else (room_setting(room, "lead_min") or 0))
    if use_entity:
        in_comfort = bool(schedule_on)
        target = comfort if in_comfort else eco
        mode = "komfort" if in_comfort else "eco"
        label = "Zeitplan an – Komfort" if in_comfort else "Zeitplan aus – Eco"
        plan.update(plan_target=target, plan_label=label, plan_kind="komfort" if in_comfort else "eco")
        cause = f"Heizplan: {label}"
        if not in_comfort and lead > 0 and schedule_next_on is not None and schedule_next_on <= lead:
            target, mode, cause = comfort, "vorheizen", f"Vorheizen – Komfort in {schedule_next_on} Min."
    else:
        st = plan_state(blocks, week_min, comfort, eco)
        target, in_comfort = st["target"], st["kind"] == "komfort"
        label = plan_label(st, comfort)
        plan.update(plan_target=target, plan_label=label, plan_kind=st["kind"])
        mode = "komfort" if in_comfort else "eco"
        cause = f"Heizplan: {label}"
        if not in_comfort and lead > 0:
            ahead = plan_state(blocks, week_min + lead, comfort, eco)
            if ahead["kind"] == "komfort" and ahead["target"] > target:
                target, mode = ahead["target"], "vorheizen"
                cause = f"Vorheizen für {plan_label(ahead, comfort)}"
    plan_text = f"Plan: {_de(plan['plan_target'])} °C" if plan["plan_target"] is not None else ""

    if override is not None:
        target, mode = float(override), ("boost" if boost else "manuell")
        cause = "Boost" if boost else "Von Hand"
    elif force_eco:
        target, mode, cause = eco, "eco_fix", "Eco erzwungen"
    elif party:
        target, mode, cause = max(target, comfort), "party", "Party – mindestens Komfort"
    elif vacation:
        target, mode, cause = float(settings.get("vacation_temp", 16)), "urlaub", f"Urlaub ({plan_text})"
    elif away and long_away:
        # Lange niemand da: auf Frostschutz
        return result("frost", frost, cause="Lange niemand zu Hause – Frostschutz")
    elif away:
        if settings.get("away_action") == "off":
            return result("abwesend", target, True, "Niemand zu Hause – Thermostate aus")
        if settings.get("away_mode") == "offset":
            away_temp = target - float(settings.get("away_offset", 2) or 0)
        else:
            away_temp = float(settings.get("away_temp", 17))
        # Niemand da: immer „abwesend“ – höchstens die Abwesend-Temperatur, nie wärmer als der Plan
        target, mode = min(away_temp, target), "abwesend"
        cause = f"Niemand zu Hause – höchstens {_de(away_temp)} °C ({plan_text})"
    elif occupied is not None:
        if occupied and room.get("presence_mode") == "always" and target < comfort:
            target, mode, cause = comfort, "belegt", "Präsenzmelder: jemand im Raum – Komfort"
        elif not occupied and mode in ("komfort", "vorheizen"):
            target, mode, cause = eco, "leer", f"Präsenzmelder: niemand im Raum – Eco ({plan_text})"

    max_setback = float(room_setting(room, "max_setback") or 0)
    if max_setback > 0 and mode in ("eco", "abwesend", "urlaub", "leer") and target < comfort - max_setback:
        target = comfort - max_setback
        cause += f" · höchstens {_de(max_setback)} °C unter Komfort"

    off_above = float(room_setting(room, "off_above") or 0)
    if off_above > 0 and room_temp is not None and mode != "boost":
        # Abschalten ab Soll + off_above, wieder einschalten, sobald der Raum unter Soll fällt.
        if room_temp >= target + off_above or (was_warm and room_temp >= target):
            return result("warm", target, True, f"Warm genug – Thermostat aus ({cause})")

    return result(mode, target, cause=cause)


def window_paused(
    open_since: float | None,
    closed_since: float | None,
    was_paused: bool,
    now: float,
    delay: float,
    resume_delay: float,
) -> bool:
    """Entscheidet über die Fensterpause.

    open_since: Zeitpunkt, seit dem mindestens ein Fenster offen ist (oder None).
    closed_since: Zeitpunkt, seit dem alle Fenster zu sind (oder None).
    """
    if open_since is not None:
        return was_paused or now - open_since >= delay
    if was_paused and closed_since is not None:
        return now - closed_since < resume_delay
    return False


def compensated(target: float, thermostat_temp: float | None, room_temp: float | None) -> float:
    """Sollwert für ein Thermostat, das wärmer/kälter misst als der Raumsensor."""
    if thermostat_temp is None or room_temp is None:
        return target
    offset = max(-MAX_COMPENSATION, min(MAX_COMPENSATION, thermostat_temp - room_temp))
    return target + offset


def snap(value: float, step: float | None, low: float | None, high: float | None) -> float:
    """Auf die Schrittweite und Grenzen des Thermostats runden."""
    step = step or 0.5
    value = round(round(value / step) * step, 2)
    if low is not None:
        value = max(float(low), value)
    if high is not None:
        value = min(float(high), value)
    return value


def next_comfort(blocks: list[dict], week_min: int, comfort: float, horizon: int) -> tuple[int, float] | None:
    """Nächster Komfortbeginn innerhalb von horizon Minuten: (Minuten bis dahin, Temperatur)."""
    week_min %= WEEK_MIN
    best: tuple[int, float] | None = None
    for start, _end, temp, _i, kind in _week_blocks(blocks):
        if kind == "eco":
            continue
        delta = (start - week_min) % WEEK_MIN
        if 0 < delta <= horizon:
            value = float(temp) if temp is not None else float(comfort)
            if best is None or delta < best[0]:
                best = (delta, value)
    return best


def smart_lead(room_temp: float | None, target: float, rate: float, max_lead: int) -> int:
    """Vorlaufzeit in Minuten, damit der Raum zum Komfortbeginn warm ist.

    rate = gelernte Aufheizgeschwindigkeit in K/h. 15 % Reserve plus 5 Minuten,
    auf 5 Minuten aufgerundet und auf max_lead begrenzt.
    """
    if room_temp is None:
        return max_lead // 2
    needed = target - room_temp
    if needed <= 0:
        return 0
    minutes = needed / max(rate, 0.1) * 60 * 1.15 + 5
    minutes = int(-(-minutes // 5) * 5)
    return max(0, min(int(max_lead), minutes))


def learn_rate(old: float | None, start_temp: float, end_temp: float, hours: float) -> float | None:
    """Neue Aufheizgeschwindigkeit (K/h) aus einem Aufheizvorgang, gleitend gemittelt."""
    if hours < 0.25 or end_temp - start_temp < 0.5:
        return None
    rate = max(0.1, min(6.0, (end_temp - start_temp) / hours))
    if old is None:
        return round(rate, 2)
    return round(old * 0.7 + rate * 0.3, 2)


def aggressive(target: float, room_temp: float | None, span: float, offset: float) -> float:
    """Übersteuern, solange der Raum weit vom Soll entfernt ist."""
    if not span or room_temp is None:
        return target
    if room_temp <= target - span:
        return target + offset
    if room_temp >= target + span:
        return target - offset
    return target


def calibration_offset(
    room_temp: float | None,
    thermostat_temp: float | None,
    current_offset: float,
    step: float,
    low: float,
    high: float,
) -> float | None:
    """Neuer Kalibrierwert, damit das Thermostat die Raumtemperatur misst.

    Das Thermostat zeigt bereits seinen Messwert inklusive des aktuellen Offsets.
    Gibt None zurück, wenn sich nichts ändern muss.
    """
    if room_temp is None or thermostat_temp is None:
        return None
    step = step or 0.1
    wanted = current_offset + (room_temp - thermostat_temp)
    wanted = round(round(wanted / step) * step, 2)
    wanted = max(low, min(high, wanted))
    if abs(wanted - current_offset) < step - 1e-9:
        return None
    return wanted


def valve_opening(target: float, room_temp: float | None, full_diff: float, max_open: float, step: float = 10) -> float | None:
    """Ventilöffnung in Prozent: zu bei erreichtem Soll, voll offen ab full_diff darunter."""
    if room_temp is None:
        return None
    gap = target - room_temp
    if gap <= 0:
        return 0.0
    full_diff = full_diff or 1.0
    value = min(1.0, gap / full_diff) * max_open
    return float(min(max_open, max(step, round(value / step) * step)))


def occupied(is_on: bool | None, since_s: float, was: bool | None, on_delay_s: float, off_delay_s: float) -> bool | None:
    """Belegung eines Raums aus einem Präsenzmelder mit Ein- und Ausschaltverzögerung."""
    if is_on is None:
        return was
    if is_on:
        return True if since_s >= on_delay_s else bool(was)
    if was is None:
        return since_s < off_delay_s
    return False if since_s >= off_delay_s else bool(was)


def summer_state(
    outside: float | None, threshold: float, was: bool, hysteresis: float = 1.0, fallback: str = "keep"
) -> bool:
    """Sommerpause ab der Schwelle, Heizbetrieb erst wieder eine Hysterese darunter.

    fallback, wenn der Außensensor nichts liefert: keep = letzten Zustand behalten,
    heat = heizen, summer = Sommerpause.
    """
    if outside is None:
        return {"heat": False, "summer": True}.get(fallback, was)
    if outside >= threshold:
        return True
    if outside < threshold - hysteresis:
        return False
    return was


def hourly_mean(buckets: dict, now_ts: float, hours: int) -> float | None:
    """Mittel der Stundenwerte der letzten `hours` Stunden; None, wenn zu wenig Werte (unter einem Viertel, mindestens 3)."""
    cur = int(now_ts // 3600)
    vals = [s / n for h, (s, n) in ((int(k), v) for k, v in buckets.items()) if cur - hours < h <= cur and n]
    return sum(vals) / len(vals) if len(vals) >= max(3, hours // 4) else None


def liming_active(settings: dict, week_min: int) -> bool:
    """Liegt die Minute im wöchentlichen Entkalkungsfenster?"""
    if not settings.get("liming"):
        return False
    try:
        start = int(settings.get("liming_day", 0)) * DAY_MIN + parse_hm(settings.get("liming_time", "10:00"))
    except (TypeError, ValueError):
        return False
    duration = int(settings.get("liming_minutes", 5) or 0)
    return 0 <= (week_min - start) % WEEK_MIN < duration


def distance_km(value: float | None, unit: str | None) -> float | None:
    """Entfernung eines Annäherungs-Sensors in Kilometer."""
    if value is None:
        return None
    unit = (unit or "km").lower()
    if unit == "m":
        return value / 1000
    if unit in ("mi", "miles"):
        return value * 1.609344
    if unit in ("ft", "feet"):
        return value * 0.0003048
    return value


def minutes_until(iso_or_dt: Any, now_ts: float) -> int | None:
    """Minuten bis zu einem Zeitpunkt (ISO-Text oder datetime), None wenn unbekannt."""
    if iso_or_dt is None:
        return None
    try:
        when = iso_or_dt if isinstance(iso_or_dt, datetime) else datetime.fromisoformat(str(iso_or_dt))
        return max(0, int((when.timestamp() - now_ts) // 60))
    except (TypeError, ValueError):
        return None


def is_vacation(settings: dict, today_iso: str, calendar: bool = False) -> bool:
    """Urlaub: Schalter von Hand, sonst je nach Quelle Zeitraum, Kalender oder aus."""
    if settings.get("vacation"):
        return True
    source = settings.get("vacation_source") or "period"
    if source == "calendar":
        return bool(calendar)
    if source == "period":
        start, end = settings.get("vacation_from"), settings.get("vacation_to")
        if start and end:
            return start <= today_iso <= end
    return False


def keywords(text: str | None) -> list[str]:
    """'Urlaub, Ferien' -> ['urlaub', 'ferien']."""
    return [k.strip().lower() for k in str(text or "").replace(";", ",").split(",") if k.strip()]


def keyword_match(title: str | None, words: list[str]) -> bool:
    """Kommt eines der Stichworte im Titel vor? Ohne Stichworte zählt jeder Termin."""
    if not words:
        return True
    low = str(title or "").lower()
    return any(w in low for w in words)


def calendar_state(events: list[tuple[float, float]], now_ts: float) -> tuple[bool, int | None]:
    """Kalender als Heizplan: (läuft gerade ein Termin?, Minuten bis zum nächsten Wechsel).

    Wie bei einem schedule.*-Helfer: läuft ein Termin, ist der nächste Wechsel sein Ende
    (anschließende oder überlappende Termine zählen durchgehend), sonst der nächste Beginn.
    events: (Beginn, Ende) als Zeitstempel.
    """
    running = [e for s, e in events if s <= now_ts < e]
    if running:
        end = max(running)
        changed = True
        while changed:
            changed = False
            for s, e in events:
                if s <= end < e:
                    end, changed = e, True
        return True, int((end - now_ts) // 60)
    future = [s for s, _ in events if s > now_ts]
    return False, (int((min(future) - now_ts) // 60) if future else None)


def events_to_blocks(events: list[tuple[int, str, str]]) -> list[dict]:
    """Termine (Wochentag, 'HH:MM', 'HH:MM') zu Heizplan-Zeitfenstern zusammenfassen.

    Gleiche Uhrzeiten an mehreren Tagen werden ein Zeitfenster mit mehreren Tagen.
    """
    grouped: dict[tuple[str, str], set[int]] = {}
    for day, start, end in events:
        if start == end:
            continue
        grouped.setdefault((start, end), set()).add(int(day) % 7)
    blocks = [{"days": sorted(days), "start": s, "end": e} for (s, e), days in grouped.items()]
    return sorted(blocks, key=lambda b: (b["days"][0], b["start"]))[:50]


# ------------------------------------------------------------ Vorheizen nach Wetter
WEATHER_REF_TEMP = 5.0  # bei dieser Außentemperatur gilt die gelernte bzw. feste Vorlaufzeit unverändert


def weather_lead_factor(outside: float | None, ref: float = WEATHER_REF_TEMP, per_deg: float = 0.04,
                        low: float = 0.6, high: float = 1.8) -> float:
    """Faktor für die Vorlaufzeit nach Außentemperatur: kälter = länger, milder = kürzer.

    Je Grad unter ref 4 % mehr Vorlauf, je Grad darüber 4 % weniger (begrenzt auf 0,6 … 1,8).
    Ohne Außentemperatur 1.
    """
    if outside is None:
        return 1.0
    return round(max(low, min(high, 1 + (ref - float(outside)) * per_deg)), 2)


# ------------------------------------------------------------ Luftfeuchte und Lüften
def abs_humidity(temp: float, rh: float) -> float:
    """Absolute Luftfeuchte in g/m³ (Magnus-Formel)."""
    sat = 6.112 * math.exp(17.62 * temp / (243.12 + temp))  # hPa
    return 216.7 * (rh / 100 * sat) / (273.15 + temp)


def dew_point(temp: float, rh: float) -> float:
    """Taupunkt in °C (Magnus-Formel)."""
    rh = max(1.0, min(100.0, rh))
    gamma = math.log(rh / 100) + 17.62 * temp / (243.12 + temp)
    return 243.12 * gamma / (17.62 - gamma)


def ventilate_advice(in_temp: float | None, in_rh: float | None, out_temp: float | None, out_rh: float | None,
                     limit_rh: float = 65.0, min_gain: float = 1.0) -> dict | None:
    """Lohnt sich Lüften? Drinnen feucht (ab limit_rh) und draußen um min_gain g/m³ trockenere Luft.

    Ergebnis mit Werten für den Hinweis oder None.
    """
    if None in (in_temp, in_rh, out_temp, out_rh) or not limit_rh or in_rh < limit_rh:
        return None
    inside = abs_humidity(in_temp, in_rh)
    outside = abs_humidity(out_temp, out_rh)
    if inside - outside < min_gain:
        return None
    return {"rh": round(in_rh), "inside_g": round(inside, 1), "outside_g": round(outside, 1),
            "dew_point": round(dew_point(in_temp, in_rh), 1)}


def vent_minutes(out_temp: float | None) -> int:
    """Empfohlene Dauer fürs Stoßlüften nach Außentemperatur (Richtwerte: kalt = kurz, mild = länger)."""
    if out_temp is None:
        return 10
    if out_temp < 0:
        return 5
    if out_temp < 10:
        return 10
    if out_temp < 15:
        return 15
    return 25


def vent_limit(room: dict, default: float = 65.0) -> float:
    """Feuchte-Grenze des Raums: eigener Wert, sonst nach Raumart bzw. Name (Bad 70 %, Schlafzimmer 60 %)."""
    if room.get("vent_rh"):
        return float(room["vent_rh"])
    use = str(room.get("use") or "").lower()
    name = str(room.get("name") or "").lower()
    if use == "bad" or any(w in name for w in ("bad", "dusche", "wc")):
        return max(default, 70.0)
    if use in ("schlafen", "kind") or any(w in name for w in ("schlaf", "kinder")):
        return min(default, 60.0)
    return float(default)


def mold_risk(in_temp: float | None, in_rh: float | None, out_temp: float | None, frsi: float = 0.7) -> dict | None:
    """Schimmel-Ampel: Feuchte an der kühlsten Stelle der Außenwand (Temperaturfaktor fRsi 0,7 nach DIN 4108-2).

    Wandtemperatur = außen + fRsi × (innen − außen); daraus die relative Feuchte direkt an der Wand.
    ok unter 70 %, warn 70–80 %, bad ab 80 % (Schimmel kann wachsen).
    """
    if None in (in_temp, in_rh, out_temp) or out_temp >= in_temp:
        return None
    wall = out_temp + frsi * (in_temp - out_temp)
    water = abs_humidity(in_temp, in_rh)
    sat = 216.7 * 6.112 * math.exp(17.62 * wall / (243.12 + wall)) / (273.15 + wall)
    rh = min(100.0, 100.0 * water / sat)
    level = "bad" if rh >= 80 else "warn" if rh >= 70 else "ok"
    return {"wall_temp": round(wall, 1), "wall_rh": round(rh), "level": level}


def window_loss_kwh(minutes: float, in_temp: float | None, out_temp: float | None, watt_per_k: float = 20.0) -> float:
    """Grobe Wärmeverluste durch ein offenes Fenster (ca. 20 W je Kelvin Unterschied) in kWh."""
    if in_temp is None or out_temp is None or in_temp <= out_temp or minutes <= 0:
        return 0.0
    return round(watt_per_k * (in_temp - out_temp) * minutes / 60 / 1000, 2)


def vent_tau(minutes: float, t0: float | None, rh0: float | None, t1: float | None, rh1: float | None,
             t_out: float | None, rh_out: float | None) -> float | None:
    """Luftwechsel eines Raums aus einer Lüftung lernen: Zeitkonstante τ in Minuten.

    Die absolute Feuchte nähert sich beim Lüften der Außenluft: x(t) = x_out + (x0 − x_out) · e^(−t/τ).
    Nur verwertbar, wenn drinnen deutlich feuchter als draußen war und die Feuchte wirklich gesunken ist.
    """
    if None in (t0, rh0, t1, rh1, t_out, rh_out) or minutes < 2:
        return None
    x0, x1, xo = abs_humidity(t0, rh0), abs_humidity(t1, rh1), abs_humidity(t_out, rh_out)
    if x0 - xo < 1.5 or x1 >= x0 - 0.2 or x1 <= xo + 0.1:
        return None
    tau = minutes / math.log((x0 - xo) / (x1 - xo))
    return round(tau, 1) if 1 <= tau <= 120 else None


def vent_learned_minutes(taus: list[float], in_temp: float | None, in_rh: float | None, out_temp: float | None,
                         out_rh: float | None, limit_rh: float, fallback: int) -> tuple[int, bool]:
    """Lüftdauer: aus dem gelernten Luftwechsel (Median der letzten τ, ab 3 Messungen) bis die Feuchte
    10 % unter der Grenze liegt; ohne Feuchte-Anlass 2·τ (≈ 85 % der Luft getauscht). Sonst die Richtwerte."""
    good = sorted(t for t in taus if t)[-10:]
    if len(good) < 3:
        return fallback, False
    tau = sorted(good)[len(good) // 2]
    minutes = 2 * tau
    if None not in (in_temp, in_rh, out_temp, out_rh) and limit_rh and in_rh >= limit_rh - 5:
        x0, xo = abs_humidity(in_temp, in_rh), abs_humidity(out_temp, out_rh)
        xt = abs_humidity(in_temp, max(30.0, limit_rh - 10))
        if x0 > xt > xo:
            minutes = tau * math.log((x0 - xo) / (xt - xo))
    return int(max(3, min(30, round(minutes)))), True


def vent_helps(in_temp: float | None, in_rh: float | None, out_temp: float | None, out_rh: float | None,
               min_gain: float = 1.0) -> bool | None:
    """Trocknet Lüften gerade? Draußen mindestens min_gain g/m³ weniger Wasser in der Luft (None = unbekannt)."""
    if None in (in_temp, in_rh, out_temp, out_rh):
        return None
    return abs_humidity(in_temp, in_rh) - abs_humidity(out_temp, out_rh) >= min_gain


def vent_plan(hours: list[dict], now_ts: float, in_temp: float = 21.0, in_rh: float = 55.0) -> list[dict]:
    """Beste Lüftzeiten der nächsten 24 Stunden aus der Stunden-Vorhersage: kein Regen, trockene Außenluft,
    möglichst wenig Wärmeverlust – je eine Zeit am Vormittag (6–12 Uhr) und am Nachmittag/Abend (12–22 Uhr).

    hours: [{"ts": Sekunden, "hour": Ortsstunde 0–23, "temp": °C, "rh": %, "rain": bool}]
    """
    best: dict[str, dict] = {}
    for h in hours:
        ts, hour, temp = h.get("ts"), h.get("hour"), h.get("temp")
        if ts is None or hour is None or temp is None or ts < now_ts - 1800 or ts > now_ts + 86400 or not 6 <= hour < 22:
            continue
        if h.get("rain"):
            continue
        gain = None
        if h.get("rh") is not None:
            gain = abs_humidity(in_temp, in_rh) - abs_humidity(temp, h["rh"])
            if gain < 1.0:
                continue
        minutes = vent_minutes(temp)
        kwh = window_loss_kwh(minutes, in_temp, temp)
        score = kwh - 0.002 * (gain or 0)  # Wärmeverlust zählt; trockenere Luft nur als Gleichstand-Entscheid
        slot = "morning" if hour < 12 else "evening"
        key = f"{slot}:{int((ts - now_ts) // 86400 + (1 if hour < 6 else 0))}"
        if key not in best or score < best[key]["score"]:
            best[key] = {"ts": ts, "hour": hour, "temp": round(temp, 1), "minutes": minutes, "kwh": kwh,
                         "gain": round(gain, 1) if gain is not None else None, "score": score}
    out = sorted(best.values(), key=lambda x: x["ts"])[:3]
    for x in out:
        x.pop("score", None)
    return out


def next_dry_hour(hours: list[dict], now_ts: float, in_temp: float, in_rh: float) -> dict | None:
    """Erste Stunde (nächste 24 h, ohne Regen), in der die Außenluft trocknet – für „später lüften, ab … trockener“."""
    for h in sorted(hours, key=lambda x: x.get("ts") or 0):
        ts = h.get("ts")
        if ts is None or ts <= now_ts or ts > now_ts + 86400 or h.get("rain") or h.get("temp") is None or h.get("rh") is None:
            continue
        if vent_helps(in_temp, in_rh, h["temp"], h["rh"]):
            return {"ts": ts, "hour": h.get("hour"), "temp": h["temp"]}
    return None


def vent_done(minutes_open: float, target_min: float, rh_start: float | None, rh_now: float | None,
              t_start: float | None, t_now: float | None, limit_rh: float) -> str | None:
    """Genug gelüftet? Zeit erreicht, Feuchte deutlich gesunken oder Raum zu stark abgekühlt – mit Grund."""
    if minutes_open >= target_min:
        return f"{int(target_min)} Min. gelüftet"
    if rh_start is not None and rh_now is not None and minutes_open >= 3 and rh_now <= min(rh_start - 10, limit_rh - 5):
        return f"Luftfeuchte {rh_start:.0f} → {rh_now:.0f} %"
    if t_start is not None and t_now is not None and t_start - t_now >= 3:
        return f"Raum {t_start - t_now:.1f} °C kühler".replace(".", ",")
    return None


# ------------------------------------------------------------ Verläufe (Fenster- und Duscherkennung)
def drop_within(samples: list[tuple[float, float]], now: float, seconds: float) -> float:
    """Wie stark ist der Wert in den letzten seconds Sekunden gefallen? (höchster Wert minus aktueller)"""
    recent = [v for ts, v in samples if now - ts <= seconds]
    if len(recent) < 2:
        return 0.0
    return round(max(recent) - recent[-1], 2)


def rise_within(samples: list[tuple[float, float]], now: float, seconds: float) -> float:
    """Wie stark ist der Wert in den letzten seconds Sekunden gestiegen? (aktueller minus tiefster Wert)"""
    recent = [v for ts, v in samples if now - ts <= seconds]
    if len(recent) < 2:
        return 0.0
    return round(recent[-1] - min(recent), 2)


# ------------------------------------------------------------ Feiertage
def holiday_week_minute(week_min: int, workday: bool | None, as_day: int = 6) -> int:
    """An einem freien Werktag (Feiertag laut Sensor „Arbeitstag“) gelten die Zeiten von as_day (5 = Sa, 6 = So)."""
    day, minute = divmod(week_min % WEEK_MIN, DAY_MIN)
    if workday is not False or day >= 5:
        return week_min
    return int(as_day) % 7 * DAY_MIN + minute


# ------------------------------------------------------------ Benachrichtigungen
def in_quiet_hours(now_min: int, start: str | None, end: str | None) -> bool:
    """Liegt die Tagesminute in der Ruhezeit (auch über Mitternacht, z. B. 22:00–07:00)?"""
    if not start or not end:
        return False
    try:
        a, b = parse_hm(start), parse_hm(end)
    except (TypeError, ValueError):
        return False
    if a == b:
        return False
    return a <= now_min < b if a < b else now_min >= a or now_min < b


def battery_level(state: str | None, device_class: str | None, unit: str | None) -> float | None:
    """Ladestand in % aus einem Batterie-Sensor; binäre Sensoren (an = schwach) als 0 bzw. 100."""
    if state is None:
        return None
    if device_class == "battery" and state in ("on", "off"):
        return 0.0 if state == "on" else 100.0
    if unit not in (None, "%"):
        return None
    try:
        return float(state)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------ Andere Regelungen, Kopplung, Funk
def find_references(value: Any, ids: set[str], found: set[str] | None = None, depth: int = 0) -> set[str]:
    """Welche der Entitäts-IDs kommen irgendwo in den Attributen vor (auch verschachtelt)?"""
    found = set() if found is None else found
    if depth > 6 or not ids:
        return found
    if isinstance(value, str):
        if value in ids:
            found.add(value)
    elif isinstance(value, dict):
        for item in value.values():
            find_references(item, ids, found, depth + 1)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            find_references(item, ids, found, depth + 1)
    return found


# Gerätemodelle verschiedener Hersteller (Kleinschreibung, Teilwort genügt)
TRV_MODELS = (
    "trv",            # Homematic IP eTRV, Sonoff TRVZB, Hive TRV001, Drayton iTRV, Bosch TRV_GEN2, Shelly TRV
    "rt-dn",          # Homematic HM-CC-RT-DN
    "bth-ra",         # Bosch Heizkörper-Thermostat (Zigbee)
    "radiator",       # Bosch „Radiator Thermostat II“, tado „Smart Radiator Thermostat“
    "va01", "va02", "va04",  # tado Heizkörper-Thermostat (V3+, X)
    "nrv",            # Netatmo Smarte Heizkörperventile
    "srts",           # Aqara Thermostat E1
    "spzb",           # Eurotronic Spirit Zigbee
    "hr91", "hr92",   # Honeywell evohome
    "ally",           # Danfoss Ally
    "dect 300", "dect 301", "dect 302", "comet",  # AVM FRITZ!DECT, Comet DECT
    "eve thermo",     # Eve Thermo
    "zk03840",        # Viessmann ViCare Heizkörper-Thermostat
    "heizkörper", "heizkorper",
)
WALL_MODELS = (
    "wth", "bwth", "sth",  # Homematic IP Wandthermostate (WTH, BWTH, STH/STHD)
    "tc-it",          # Homematic HM-TC-IT-WM
    "bth-rm",         # Bosch Raumthermostat (Zigbee)
    "rth",            # Bosch „Room Thermostat II“ (RTH2)
    "room thermostat", "raumthermostat", "wall", "wand",
    "ru01", "ru02", "su02",  # tado Smart Thermostat (Funk/verkabelt)
    "t87rf",          # Honeywell evohome
    "roomstat",       # Drayton Wiser
    "natherm", "nathermostat",  # Netatmo Thermostat
    "w100",           # Aqara Climate Sensor W100
    "bht-",           # Moes/Beca Wandthermostate
    "ct100", "ct200", # Bosch EasyControl
    "nest", "ecobee",
)
_WALL_NAME = ("wth", "wandthermostat", "wall_thermostat", "wall thermostat", "raumthermostat", "room thermostat")
_TRV_NAME = ("etrv", "trv", "heizkörper", "heizkorper", "heizkoerper", "radiator", "stellantrieb", "ventil")


def thermostat_kind(model: str | None, entity_id: str, name: str | None = None) -> str | None:
    """'wall' für Wandthermostate, 'trv' für Heizkörper-Thermostate, sonst None.

    Erst das Modell (Homematic, Bosch, tado, Netatmo, Danfoss, Aqara, AVM, Honeywell …), dann der Name.
    """
    model_l = (model or "").lower()
    if model_l:
        if any(w in model_l for w in TRV_MODELS):
            return "trv"
        if any(w in model_l for w in WALL_MODELS):
            return "wall"
    text = f"{entity_id} {name or ''}".lower()
    if any(w in text for w in _WALL_NAME):
        return "wall"
    if any(w in text for w in _TRV_NAME):
        return "trv"
    return None


def radio_should_send(
    busy: bool,
    current: float | None,
    value: float,
    since_last: float | None,
    important: bool = False,
    min_step: float = 1.0,
    min_interval: float = 900,
) -> bool:
    """Bei ausgelastetem Funk nur wichtige oder größere Änderungen senden, höchstens alle 15 Minuten."""
    if not busy or important or current is None:
        return True
    if abs(value - current) < min_step:
        return False
    return since_last is None or since_last >= min_interval


def retry_wait(fails: int) -> float:
    """Wartezeit vor dem nächsten Versuch, wenn ein Sollwert nicht übernommen wird: 2 Versuche sofort, dann 15 Min., dann stündlich."""
    if fails < 2:
        return 0.0
    return 900.0 if fails == 2 else 3600.0


# ------------------------------------------------------------ Mischbetrieb (Fußbodenheizung + Heizkörper)
def assist_on(mode: str, room_temp: float | None, target: float | None, diff: float, was_on: bool) -> bool:
    """Soll der Heizkörper als Zusatzheizung mitheizen?

    Die Fußbodenheizung trägt die Grundlast. Der Heizkörper hilft beim Vorheizen, beim Boost und
    sobald der Raum diff °C unter Soll liegt – bis das Soll fast erreicht ist (0,1 °C darunter).
    """
    if mode in ("vorheizen", "boost", "entkalken"):
        return True
    if mode in ("fenster", "sommer", "aus", "warm") or target is None:
        return False
    if room_temp is None:
        return True  # ohne Messwert lieber mitheizen
    if was_on:
        return room_temp < target - 0.1
    return room_temp <= target - max(0.1, diff)


# ------------------------------------------------------------ Ventile, kalte Heizkörper, Wärmeanforderung
VALVE_ATTRS = ("valve_position", "valve_opening", "valve_tappet", "pi_heating_demand", "heating_demand",
               "heating_power_request", "heating_power", "position", "valve")
# Sensoren am Thermostat-Gerät: Homematic „Ventilöffnungsgrad“, Bosch „Ventilstößel“, Zigbee „pi_heating_demand“,
# tado „Heizleistung“ (sensor.*_heating), Netatmo „heating_power_request“
VALVE_WORDS = re.compile(r"ventil|valve|stellung|st(ö|oe)(ß|ss)el|tappet|heating_demand|heizbedarf|pi_heating|heating_power|heizleistung|_heating$|position", re.I)
VALVE_SKIP = re.compile(r"max|min|limit|grenze|offset", re.I)
COLD_MINUTES = 60  # so lange Ventil (fast) ganz offen ohne Erwärmung = Heizkörper bleibt kalt
NO_HEAT_MODES = ("fenster", "sommer", "aus", "warm", "entkalken")


def vent_balance(last_at: float | None, rh_morning: dict[str, float], limit: float, mold: dict | None,
                 now: float, today: str) -> dict:
    """Lüft-Bilanz eines Raums als Ampel: wie lange nicht gelüftet und wie feucht morgens (Mittel der letzten 3 Tage).

    rot: ≥ 3 Tage nicht gelüftet und morgens feucht (ab Grenze − 5 %) oder Schimmel-Ampel rot;
    gelb: ≥ 2 Tage nicht gelüftet oder morgens über der Grenze; sonst grün.
    """
    days = None if last_at is None else int((now - last_at) // 86400)
    recent = [v for k, v in sorted(rh_morning.items()) if k <= today][-3:]
    rh = round(sum(recent) / len(recent)) if recent else None
    moldbad = (mold or {}).get("level") == "bad"
    level = "ok"
    if moldbad or (days is not None and days >= 3 and rh is not None and rh >= limit - 5):
        level = "bad"
    elif (days is not None and days >= 2) or (rh is not None and rh >= limit):
        level = "warn"
    parts = []
    if days is None:
        parts.append("noch keine Lüftung erfasst")
    elif days >= 1:
        parts.append(f"{days} {'Tag' if days == 1 else 'Tage'} nicht gelüftet")
    else:
        parts.append("heute gelüftet")
    if rh is not None:
        parts.append(f"Feuchte morgens {rh} %")
    return {"level": level, "days": days, "rh_morning": rh, "text": ", ".join(parts)}


def cold_radiator(valve: float | None, room_temp: float | None, target: float | None, mode: str,
                  windows_open: bool, run: dict | None, now: float, closed_ago: float | None = None,
                  floor: bool = False) -> tuple[dict | None, bool]:
    """Bleibt ein Heizkörper kalt, obwohl sein Ventil offen ist?

    run: laufende Beobachtung {since, t0} oder None. Ergebnis: (neue Beobachtung, kalt?).
    Kalt heißt: Ventil ≥ 90 % seit COLD_MINUTES Minuten, der Raum mindestens 0,5 °C unter Soll und
    in der Zeit um weniger als 0,3 °C wärmer geworden. Wird der Raum wärmer, beginnt die Messung neu.
    Kein Fehlalarm nach dem Lüften: bis 30 Min. nach dem Schließen (closed_ago in s) wird nicht gemessen –
    der Raum muss erst die ausgekühlten Wände nachheizen. Räume mit Fußbodenheizung (träge) erst nach 3 Std.
    """
    active = (valve is not None and valve >= 90 and room_temp is not None and target is not None
              and target - room_temp >= 0.5 and mode not in NO_HEAT_MODES and not windows_open
              and (closed_ago is None or closed_ago >= 1800))
    if not active:
        return None, False
    if run is None or room_temp - run["t0"] >= 0.3:
        return {"since": now, "t0": room_temp}, False
    return run, now - run["since"] >= (180 if floor else COLD_MINUTES) * 60


def demand_state(need: bool, current: str | None, no_need_since: float | None, now: float, hold_min: float,
                 preheat: bool, raise_by: float) -> str:
    """Wärmeanforderung an den Wärmeerzeuger: 'low' (abgesenkt/aus), 'normal' oder 'raise' (Vorheizen).

    Abgesenkt wird erst, wenn hold_min Minuten lang kein Raum Wärme braucht; Bedarf hebt sofort wieder an.
    """
    if need:
        return "raise" if preheat and raise_by > 0 else "normal"
    if current == "low":
        return "low"
    if no_need_since is not None and now - no_need_since >= hold_min * 60:
        return "low"
    return current or "normal"


# ------------------------------------------------------------ Rollwerk (Rollläden)
FACADES = {"N": 0, "NO": 45, "O": 90, "SO": 135, "S": 180, "SW": 225, "W": 270, "NW": 315}


def facade_sun(azimuth: float | None, elevation: float | None, facade: str | None, min_elev: float = 15,
               width: float = 60) -> bool:
    """Scheint die Sonne auf diese Fassade? (Azimut höchstens width° neben der Fassadenrichtung, hoch genug)"""
    if azimuth is None or elevation is None or facade not in FACADES or elevation < min_elev:
        return False
    diff = abs((float(azimuth) - FACADES[facade] + 180) % 360 - 180)
    return diff <= width


def day_window(sunrise_min: int | None, sunset_min: int | None, settings: dict, free_day: bool,
               jitter: int = 0) -> tuple[int, int]:
    """Öffnen und Schließen heute als Tagesminuten.

    Sonne: Sonnenaufgang + Versatz, aber nicht vor „frühestens“; Sonnenuntergang + Versatz, aber nicht nach
    „spätestens“. Feste Zeit: Uhrzeit (am Wochenende/Feiertag eigene). jitter verschiebt beides (Urlaub).
    """
    def hm(key: str, default: str) -> int:
        try:
            return parse_hm(settings.get(key) or default)
        except (TypeError, ValueError):
            return parse_hm(default)

    if (settings.get("rw_open_mode") or "sun") == "sun" and sunrise_min is not None:
        not_before = hm("rw_open_not_before_we" if free_day else "rw_open_not_before", "08:00" if free_day else "06:30")
        open_at = max(sunrise_min + int(settings.get("rw_open_offset") or 0), not_before)
    else:
        open_at = hm("rw_open_time_we" if free_day else "rw_open_time", "08:30" if free_day else "07:00")
    if (settings.get("rw_close_mode") or "sun") == "sun" and sunset_min is not None:
        close_at = min(sunset_min + int(settings.get("rw_close_offset") or 0), hm("rw_close_not_after", "22:30"))
    else:
        close_at = hm("rw_close_time", "21:00")
    return max(0, min(DAY_MIN - 1, open_at + jitter)), max(0, min(DAY_MIN - 1, close_at + jitter))


def cover_target(now_min: int, open_at: int, close_at: int, settings: dict, cover: dict, *, sun_on_facade: bool,
                 outside: float | None, storm: bool, was_shading: bool = False) -> tuple[int | None, str, bool]:
    """Sollposition eines Rollladens (100 = offen, 0 = zu), Begründung und ob gerade beschattet wird.

    Vorrang: Automatik aus > Sturm (hochfahren) > Nacht > Sonnenschutz > Tag. None = nichts tun.
    """
    if cover.get("auto") is False:
        return None, "Automatik aus", False
    if storm and cover.get("storm", True):
        return 100, "Sturmschutz", False
    open_mode = settings.get("rw_open_mode") or "sun"
    close_mode = settings.get("rw_close_mode") or "sun"
    day = open_at <= now_min < close_at
    night_pos = int(cover.get("night_pos") if cover.get("night_pos") is not None else 0)
    if not day:
        if (now_min >= close_at and close_mode == "off") or (now_min < open_at and open_mode == "off" and close_mode == "off"):
            return None, "keine Zeit eingestellt", False
        return night_pos, "Nacht", False
    shade_temp = float(settings.get("rw_shade_temp") or 24)
    hot = outside is not None and outside >= (shade_temp - 1 if was_shading else shade_temp)
    if settings.get("rw_shade") and cover.get("shade", True) and cover.get("facade") and sun_on_facade and hot:
        pos = cover.get("shade_pos")
        return int(pos if pos is not None else settings.get("rw_shade_pos") or 30), "Sonnenschutz", True
    if open_mode == "off":
        return None, "Tag (morgens nicht automatisch öffnen)", False
    return 100, "Tag", False


# ---------------------------------------------------------------- Rollwerk-Beschattung (wie CCA)
SHADE_CONDS = ("azimuth", "elevation", "brightness", "temp1", "temp2", "forecast_temp", "forecast_weather", "custom")


def _in_azimuth(az: float, start: float, end: float) -> bool:
    start, end = start % 360, end % 360
    return start <= az <= end if start <= end else az >= start or az <= end


def shade_conditions(values: dict, prof: dict, active: bool = False) -> tuple[dict, dict]:
    """Je Bedingung: erfüllt fürs Starten bzw. Beenden (None = nicht messbar/nicht eingerichtet)."""
    start: dict[str, bool | None] = {}
    end: dict[str, bool | None] = {}

    def num(key, default=0.0):
        try:
            return float(prof.get(key) if prof.get(key) is not None else default)
        except (TypeError, ValueError):
            return float(default)

    az, el = values.get("azimuth"), values.get("elevation")
    if az is not None:
        inside = _in_azimuth(float(az), num("azimuth_start", 95), num("azimuth_end", 265))
        start["azimuth"], end["azimuth"] = inside, not inside
    if el is not None:
        inside = num("elevation_min", 25) <= float(el) <= num("elevation_max", 90)
        start["elevation"], end["elevation"] = inside, not inside
    b = values.get("brightness")
    if b is not None:
        start["brightness"] = float(b) >= num("shade_bright_start", 35000)
        end["brightness"] = float(b) <= num("shade_bright_end", 25000)
    for key in ("temp1", "temp2"):
        t = values.get(key)
        if t is not None:
            start[key] = float(t) >= num(f"{key}_min", 18)
            end[key] = float(t) < num(f"{key}_min", 18) - num(f"{key}_hyst", 0.2)
    fc = values.get("forecast_temp")
    if fc is not None and prof.get("forecast_temp") is not None:
        start["forecast_temp"] = float(fc) >= num("forecast_temp")
        end["forecast_temp"] = float(fc) < num("forecast_temp") - num("temp2_hyst", 0.2)
    cond = values.get("forecast_weather")
    if cond and prof.get("weather_conditions"):
        hit = cond in (prof.get("weather_conditions") or [])
        start["forecast_weather"], end["forecast_weather"] = hit, not hit
    if values.get("custom") is not None:
        start["custom"], end["custom"] = bool(values["custom"]), not values["custom"]
    return start, end


def _combine(cond: dict, and_list: list, or_list: list) -> bool:
    """UND-Liste: alle messbaren erfüllt; ODER-Liste: mindestens eine. Beide gewählt → beide nötig."""
    and_vals = [cond[k] for k in and_list or [] if cond.get(k) is not None]
    or_vals = [cond[k] for k in or_list or [] if cond.get(k) is not None]
    if not and_vals and not or_vals:
        return False
    return (all(and_vals) if and_vals else True) and (any(or_vals) if or_vals else True)


def shade_wanted(prof: dict, start: dict, end: dict, active: bool) -> bool:
    """Nicht aktiv: soll die Beschattung starten? Aktiv: soll sie enden?"""
    if active:
        return _combine(end, prof.get("shade_end_and") or [], prof.get("shade_end_or") or [])
    return _combine(start, prof.get("shade_start_and") or [], prof.get("shade_start_or") or [])


# ---------------------------------------------------------------- Bericht: Heizleistung je Raum
def room_analysis(rows: list[dict], heat_rate: float | None, room_type: str = "heizkoerper") -> dict:
    """Einschätzung der Heizleistung eines Raums aus den Tageswerten des Berichts.

    Kennzahlen (alle nur in der Komfortzeit, ohne die Aufheizzeit nach dem Lüften):
    - warm genug: Anteil, in dem der Raum höchstens 0,5 °C unter Soll lag,
    - zu warm: Anteil, in dem er mehr als 1 °C über Soll lag (Eco-Zeiten zählen nicht – nach dem Absenken ist es
      natürlich noch wärmer),
    - Ø Abweichung vom Soll, Ø Ventilöffnung, Anteil der Heizzeit mit Ventil ≥ 90 %, Aufheizgeschwindigkeit.
    Daraus ein Urteil (good/tight/weak/reserve/sensor/nodata) und Hinweise. Die Hinweise widersprechen dem Urteil nicht:
    z. B. kein „Reserve“ zusammen mit „bei Frost zu kalt“, kein „heizt schnell auf“ bei „zu schwach“.
    """
    floor = room_type == "flaeche"
    sum_ = lambda k: sum(r.get(k) or 0 for r in rows)  # noqa: E731
    cn, under, full, heat = sum_("comfort_n"), sum_("under_min"), sum_("full_min"), sum_("heat_min")
    pause, openings, fire = sum_("pause_min"), sum_("openings"), sum_("fire_min")
    devs = [(r["comfort_dev"], r["comfort_n"]) for r in rows if r.get("comfort_dev") is not None and r.get("comfort_n")]
    dev = round(sum(d * n for d, n in devs) / sum(n for _, n in devs), 1) if devs else None
    valves = [r["valve_avg"] for r in rows if r.get("valve_avg") is not None]
    valve = round(sum(valves) / len(valves)) if valves else None
    ok_pct = round(100 * (cn - under) / cn) if cn else None
    # zu warm: nur Tage, an denen schon in der Komfortzeit gezählt wurde (ältere Tage zählten auch Eco-Zeiten mit)
    co_rows = [r for r in rows if r.get("comfort_over") is not None and r.get("comfort_n")]
    co_n = sum(r["comfort_n"] for r in co_rows)
    over_pct = round(100 * sum(r["comfort_over"] for r in co_rows) / co_n) if co_n >= 120 else None
    full_pct = min(100, round(100 * full / heat)) if heat else None
    # kalte Tage (Ø außen < 3 °C) gegen milde
    cold = [r for r in rows if r.get("outside_avg") is not None and r["outside_avg"] < 3 and r.get("comfort_n")]
    mild = [r for r in rows if r.get("outside_avg") is not None and r["outside_avg"] >= 3 and r.get("comfort_n")]
    pct = lambda rs: round(100 * sum(r["comfort_n"] - r["under_min"] for r in rs) / sum(r["comfort_n"] for r in rs)) if rs else None  # noqa: E731
    ok_cold, ok_mild = pct(cold), pct(mild)
    findings: list[dict] = []
    add = lambda level, title, text: findings.append({"level": level, "title": title, "text": text})  # noqa: E731
    facts = {"ok_pct": ok_pct, "dev": dev, "valve": valve, "full_pct": full_pct, "over_pct": over_pct,
             "heat_h": round(heat / 60, 1), "rate": round(heat_rate, 2) if heat_rate else None,
             "ok_cold": ok_cold, "ok_mild": ok_mild, "pause_h": round(pause / 60, 1), "openings": openings,
             "fire_h": round(fire / 60, 1)}
    if cn < 120:
        return {"verdict": "nodata", "facts": facts,
                "findings": [{"level": "info", "title": "Noch zu wenig Daten",
                              "text": "Für eine Einschätzung braucht Hauswerk mindestens 2 Stunden Komfortzeit mit Messwert im gewählten Zeitraum."}]}
    heater = "die Fußbodenheizung" if floor else "der Heizkörper"
    de = lambda x: f"{x:.1f}".replace(".", ",")  # noqa: E731
    dev_txt = f" – im Schnitt {de(abs(dev))} °C {'unter' if dev < 0 else 'über'} Soll" if dev is not None and abs(dev) >= 0.1 else ""
    frost = ok_cold is not None and ok_mild is not None and len(cold) >= 2 and ok_cold < 85 and ok_mild - ok_cold >= 20
    verdict = "good"
    if ok_pct < 75 and valve is None:
        verdict = "weak"
        add("warn", "Wird nicht warm genug",
            f"Nur in {ok_pct} % der Komfortzeit warm genug{dev_txt}. Ohne Werte zur Ventilöffnung lässt sich nicht sagen, "
            f"ob {heater} zu wenig Wärme liefert oder das Thermostat zu früh abregelt.")
    elif ok_pct < 75 and (valve >= 60 or (full_pct or 0) >= 30):
        verdict = "weak"
        add("warn", "Zu schwach – wird nicht warm genug",
            f"Nur in {ok_pct} % der Komfortzeit warm genug, obwohl das Ventil weit offen ist (im Schnitt {valve} %"
            + (f", {full_pct} % der Heizzeit fast ganz auf" if full_pct else "") + f"). {heater[0].upper()}{heater[1:]} gibt also nicht genug Wärme ab. "
            + ("Mögliche Ursachen: Vorlauftemperatur zu niedrig oder zu wenig Durchfluss im Heizkreis (hydraulischer Abgleich)."
               if floor else "Mögliche Ursachen: Heizkörper zu klein, Vorlauftemperatur bzw. Heizkurve zu niedrig, Luft im Heizkörper oder fehlender hydraulischer Abgleich."))
    elif ok_pct < 75:
        verdict = "sensor"
        add("warn", "Zu kalt, aber das Ventil bleibt fast zu",
            f"Nur in {ok_pct} % der Komfortzeit warm genug, das Ventil ist dabei im Schnitt nur {valve} % offen. Die Heizung könnte mehr – "
            "das Thermostat regelt zu früh ab, vermutlich weil es direkt am Heizkörper zu warm misst. "
            "Abhilfe: Raumsensor eintragen, Kalibrierung oder „Thermostat nachführen“ einschalten (Raum › Regelung).")
    elif ok_pct < 90:
        verdict = "tight"
        add("info", "Meist warm genug, aber knapp",
            f"In {ok_pct} % der Komfortzeit warm genug{dev_txt}. "
            + ("Hilft meist: früher vorheizen (Vorheizen › Lernen) oder die Heizkurve etwas anheben." if not floor
               else "Hilft meist: längere Vorheizzeit oder die Heizkurve etwas anheben."))
    elif valve is not None and valve < 25 and (over_pct or 0) < 15 and not frost:
        verdict = "reserve"
        add("ok", "Wird warm – mit Reserve",
            f"In {ok_pct} % der Komfortzeit warm genug, das Ventil ist dabei im Schnitt nur {valve} % offen. "
            f"{heater[0].upper()}{heater[1:]} schafft mehr als nötig. Die Vorlauftemperatur ließe sich etwas senken – das spart Energie, besonders mit Wärmepumpe.")
    else:
        add("ok", "Wird warm",
            f"In {ok_pct} % der Komfortzeit warm genug{dev_txt}."
            + (f" Das Ventil ist dabei im Schnitt {valve} % offen" + (" – die Heizung arbeitet schon kräftig." if valve >= 60 else ".") if valve is not None else ""))
    if frost and verdict != "weak":
        add("warn", "Bei Frost zu kalt",
            f"An Frosttagen (unter 3 °C außen) nur in {ok_cold} % der Komfortzeit warm genug, an milden Tagen in {ok_mild} %. "
            "Die Heizkurve ist im kalten Bereich zu flach – Steilheit an der Heizung leicht erhöhen.")
    if over_pct is not None and over_pct >= 15:
        if verdict in ("weak", "sensor", "tight"):
            add("info", "Mal zu kalt, mal zu warm",
                f"Außerdem war es in {over_pct} % der Komfortzeit mehr als 1 °C zu warm. Die Temperatur schwankt also stark – "
                + ("typisch für die träge Fußbodenheizung (früher absenken)." if floor else "z. B. durch Sonne oder ein Thermostat am falschen Platz."))
        else:
            add("info", "Oft zu warm",
                f"In {over_pct} % der Komfortzeit mehr als 1 °C wärmer als gewollt. Mögliche Gründe: Sonne oder andere Wärmequellen, "
                + ("die Trägheit der Fußbodenheizung (früher absenken) " if floor else "ein zu hohes Soll am Thermostat ")
                + "oder ein Thermostat, das zu kalt misst. Weniger heizen spart hier Energie.")
    if heat_rate:
        slow, fast = (0.2, 1.0) if floor else (0.5, 3.0)
        if heat_rate < slow:
            if verdict in ("good", "reserve"):
                add("info", "Braucht lange zum Aufheizen",
                    f"Gelernt: {de(heat_rate)} °C pro Stunde. Hauswerk heizt deshalb früher vor – der Raum ist trotzdem rechtzeitig warm.")
            else:
                add("warn", "Heizt langsam auf",
                    f"Gelernt: {de(heat_rate)} °C pro Stunde – wenig für {'Fußbodenheizung' if floor else 'Heizkörper'}. Deshalb startet das Vorheizen früh.")
        elif heat_rate > fast and verdict not in ("weak", "sensor"):
            add("ok", "Heizt schnell auf", f"Gelernt: {de(heat_rate)} °C pro Stunde – kurze Vorheizzeit reicht.")
    if fire >= 30:
        add("info", "Zusätzliche Wärme herausgerechnet",
            f"{de(fire / 60)} Std. war der Raum durch eine andere Wärmequelle (Kamin oder Ähnliches) wärmer – "
            "diese Zeit zählt nicht für „warm genug“ und „zu warm“; Aufheizmessungen daraus werden verworfen.")
    if pause >= 180 or openings >= 5 * max(1, len(rows)):
        add("info", "Viel gelüftet", f"{de(pause / 60)} Std. Fensterpause bei {openings} Öffnungen. "
            "Die Aufheizzeit danach ist aus der Bewertung herausgenommen. Stoßlüften (kurz, weit auf) verliert weniger Wärme als lange gekippte Fenster.")
    return {"verdict": verdict, "facts": facts, "findings": findings}


# ---------------------------------------------------------------- Heizwerk: Kamin / zusätzliche Wärme
def extra_heat_rise(samples: list[tuple[float, float, bool]], now: float, floor: bool = False,
                    window: float = 1800, rise_min: float = 0.4) -> float | None:
    """Raum wird wärmer, ohne dass geheizt wird? samples = [(Zeit, Raumtemperatur, Heizanforderung)], älteste zuerst.

    Anstieg ≥ rise_min °C innerhalb von `window` Sekunden, und in dieser Zeit plus Nachlauf keine Heizanforderung
    (Heizkörper 20 Min., Fußbodenheizung 3 Std. – deren Restwärme ist kein fremder Wärmeeintrag).
    Rückgabe: Anstieg in °C, sonst None. Sagt nichts über die Ursache (Kamin, Sonne, Kochen, viele Leute).
    """
    if not samples or now - samples[-1][0] > 300:
        return None
    calm = window + (3 * 3600 if floor else 1200)
    if samples[0][0] > now - calm + 120:
        return None  # zu kurze Vorgeschichte (z. B. nach Neustart): keine Aussage
    if any(demand for ts, _, demand in samples if ts >= now - calm):
        return None
    recent = [t for ts, t, _ in samples if ts >= now - window]
    if len(recent) < 3:
        return None
    rise = samples[-1][1] - min(recent)
    return round(rise, 1) if rise >= rise_min else None


def fireplace_phase(prev: dict | None, now: float, *, manual: bool = False, signal: bool | None = None,
                    rise: float | None = None, temp: float | None = None, target: float | None = None) -> dict | None:
    """Phase zusätzlicher Wärme in einem Raum mit Kamin.

    - on:    Kamin in Betrieb – von Hand angegeben oder vom Signal (Sensor, Schalter) gemeldet.
    - maybe: wird wärmer ohne Heizanforderung; Ursache offen (cause "kamin?" bzw. "other", wenn das Signal „aus“ sagt).
    - after: Nachwirkung – der Raum ist noch wärmer als gewollt; endet, sobald er höchstens 0,3 °C über Soll liegt
             (frühestens 15 Min. nach dem letzten Hinweis) bzw. spätestens 3 Std. danach.
    Kamin vorhanden heißt nicht Kamin an: ohne Signal oder Angabe bleibt es bei „maybe“.
    """
    if manual or signal:
        keep = prev and prev.get("state") == "on"
        return {"state": "on", "source": "manuell" if manual else "signal", "since": prev["since"] if keep else now, "last": now}
    if rise is not None:
        keep = prev and prev.get("state") == "maybe"
        return {"state": "maybe", "source": "verlauf", "cause": "other" if signal is False else "kamin?",
                "since": prev["since"] if keep else now, "last": now, "rise": rise}
    if prev:
        last = prev.get("last", now)
        cooled = temp is not None and target is not None and temp <= target + 0.3
        if now - last > 3 * 3600 or (cooled and now - last >= 900):
            return None
        return {**prev, "state": "after"}
    return None


# ---------------------------------------------------------------- Rollwerk: Öffnen/Schließen vorausberechnen
def sun_crossing(elev: Callable[[float], float | None], target: float, rising: bool,
                 lo: float = 0.0, hi: float = 1440.0, step: float = 10.0) -> float | None:
    """Minute (seit Mitternacht, Ortszeit), zu der die Sonnenhöhe `target` erreicht – aufsteigend (rising)
    bzw. absteigend. Grob in `step`-Minuten-Schritten suchen, dann auf Sekunden genau halbieren. None = nie."""
    prev_m, prev = lo, elev(lo)
    m = lo
    while m < hi:
        m = min(m + step, hi)
        cur = elev(m)
        if prev is not None and cur is not None:
            if (rising and prev < target <= cur) or (not rising and prev > target >= cur):
                a, b = prev_m, m
                for _ in range(12):  # 10 Min. / 2^12 < 0,2 s
                    mid = (a + b) / 2
                    v = elev(mid)
                    if v is None:
                        break
                    if (rising and v >= target) or (not rising and v <= target):
                        b = mid
                    else:
                        a = mid
                return b
        prev_m, prev = m, cur
    return None


def predict_open_close(prof: dict, up: tuple[int, int] | None, down: tuple[int, int] | None,
                       elev: Callable[[float], float | None] | None,
                       azim: Callable[[float], float | None] | None = None) -> dict[str, Any]:
    """Voraussichtliche Minute fürs Öffnen, Stufe 1 und Schließen an einem Tag – wie die Steuerung entscheidet.

    Steuerung (Rollwerk._day_phase): Mit Zeitsteuerung wird im Fenster [früheste, späteste] Zeit geöffnet bzw.
    geschlossen, sobald die Sonnenregel erfüllt ist (Sonnenhöhe ≥ „Öffnen ab“ bzw. ≤ „Schließen ab“, so lange
    wie „Sonnenhöhe Dauer“ am Stück) – spätestens zur spätesten Zeit. Ohne Sonnenregel zur frühesten Zeit.
    Ohne Zeitsteuerung entscheidet allein die Sonne. Hängt es (auch) an der Helligkeit, ist der Zeitpunkt
    nicht vorhersagbar: None statt einer erfundenen Uhrzeit.
    """
    feats = set(prof.get("features") or [])
    hold = float(prof.get("sun_duration") or 0) / 60
    sun = "sun" in feats and elev is not None
    bright = "brightness" in feats
    both_and = prof.get("bs_operator") == "and"
    out: dict[str, Any] = {"open": None, "close": None, "stage1": None}

    def when(window: tuple[int, int] | None, target: float, rising: bool) -> float | None:
        if bright and (not sun or both_and):
            # Helligkeit entscheidet mit: nur sicher, wenn ohnehin die späteste Zeit greift
            return None
        # Sonne: aufsteigend am Vormittag, absteigend ab Mittag; „Dauer“ muss die Bedingung am Stück halten
        cross = sun_crossing(elev, target, rising, lo=0, hi=1440) if sun and rising else \
            sun_crossing(elev, target, rising, lo=720, hi=1440) if sun else None
        hit = None if cross is None else cross + hold
        if window and "time" in feats:
            lo, hi = window
            if not sun:
                return float(lo)
            # schon vor der frühesten Zeit erfüllt → zur frühesten Zeit; nie erfüllt → späteste Zeit
            return float(hi) if hit is None or hit > hi else max(float(lo), hit)
        if not sun or hit is None:
            return None
        return min(hit, 1439)

    if "up" in feats:
        out["open"] = when(up if "time" in feats else None, float(prof.get("sun_up") or 0), True)
    two = bool(prof.get("close_stage1")) and "down" in feats
    if "down" in feats:
        if two:
            out["close"] = float(down[1]) if down and prof.get("close_stage2", True) else None
        else:
            out["close"] = when(down if "time" in feats else None, float(prof.get("sun_down") or 0), False)
    if two:
        trig = prof.get("stage1_trigger") or "azimuth"
        if trig == "time":
            out["stage1"] = float(parse_hm(prof.get("stage1_time") or "18:00"))
        elif trig == "elevation" and elev is not None:
            out["stage1"] = sun_crossing(elev, float(prof.get("stage1_elevation") or 10), False, lo=720)
        elif trig == "azimuth" and azim is not None:
            out["stage1"] = sun_crossing(azim, float(prof.get("stage1_azimuth") or 250), True, lo=720)
        if out["stage1"] is not None and out["close"] is not None and out["stage1"] >= out["close"]:
            out["stage1"] = None
    for k in out:
        if out[k] is not None:
            out[k] = int(math.ceil(out[k] - 1e-6))  # zur vollen Minute, in der es soweit ist
    return out


# Benachrichtigungen: dezent ein Emoji vor dem Titel – erst nach Stichwort im Titel, sonst nach Anlass.
EMOJI_WORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("regen",), "🌧️"), (("sturm",), "💨"), (("winterpause", "frost"), "❄️"), (("saison starten",), "🌱"),
    (("bleibt kalt",), "🌡️"), (("batterie", "akku"), "🪫"), (("nicht erreichbar",), "📡"),
    (("fenster",), "🪟"), (("lüften",), "🌬️"), (("braucht hilfe",), "🆘"), (("fährt heim",), "🧒"),
    (("nachts",), "🌙"), (("messer", "wartung"), "🔧"), (("mähroboter", "mäher"), "🤖"), (("licht", "leuchte"), "💡"),
    (("müll",), "🗑️"), (("waschmaschine",), "🧺"), (("trockner",), "👕"), (("spül", "geschirr"), "🍽️"),
    (("meldungen",), "📬"), ((" fertig",), "✅"), (("testnachricht", "hauswerk"), "👋"),
)
EMOJI_KINDS = {"window": "🪟", "offline": "📡", "frost": "❄️", "battery": "🪫", "cold": "🌡️", "vent": "🌬️",
               "vent_done": "🪟", "storm": "💨", "cover": "📡", "light_away": "💡", "light_offline": "📡",
               "mower": "🤖", "mower_care": "🔧", "mower_guard": "🧒", "waste": "🗑️", "appliance": "✅",
               "smoke": "🔥", "water": "💧", "warn": "⚠️", "door": "🚪", "leave": "🏠", "bell": "🔔", "maint": "🔧", "weekly": "📰"}


def notify_emoji(title: str, kind: str | None = None) -> str:
    """Passendes Emoji für eine Benachrichtigung („“ = keins)."""
    low = f" {title.lower()}"
    for words, emo in EMOJI_WORDS:
        if any(w in low for w in words):
            return emo
    return EMOJI_KINDS.get(kind or "", "")


def with_emoji(title: str, kind: str | None = None) -> str:
    """Titel mit Emoji davor – nicht doppelt, wenn schon eins dasteht."""
    if not title or not title[0].isalnum():
        return title
    emo = notify_emoji(title, kind)
    return f"{emo} {title}" if emo else title


# ---------------------------------------------------------------- Beetwerk: Mähplan
MOW_MONTH = {1: 0.2, 2: 0.2, 3: 0.5, 4: 0.8, 5: 1.0, 6: 1.0, 7: 0.9, 8: 0.85, 9: 0.8, 10: 0.6, 11: 0.3, 12: 0.2}
MOW_DAYS = ("mo", "tu", "we", "th", "fr", "sa", "su")


def mow_growth(temp: float | None, month: int) -> float:
    """Wie schnell der Rasen wächst (0–1): aus der mittleren Tagestemperatur, sonst nach Monat."""
    if temp is None:
        return MOW_MONTH.get(month, 0.8)
    if temp < 5:
        return 0.2
    if temp < 10:
        return 0.2 + (temp - 5) / 5 * 0.5
    if temp < 15:
        return 0.7 + (temp - 10) / 5 * 0.3
    if temp <= 26:
        return 1.0
    return max(0.7, 1.0 - (temp - 26) / 6 * 0.3)


def plan_mowing(now_local, hours: list[dict], cfg: dict, done: dict[str, float],
                sun: tuple[int, int] | None = None, blocked: list[tuple[int, int]] | None = None) -> dict:
    """Mähplan der nächsten 7 Tage: Wochenziel (nach Wachstum) auf die erlaubten Tage verteilt, in trockene,
    nicht zu kalte/heiße Stunden gelegt; Ausgefallenes der letzten Tage wird nachgeholt.

    now_local: lokale Zeit jetzt; hours: Stunden-Vorhersage [{ts, hour, temp, rain}] (ts in s, lokale Stunde);
    cfg: hours_week, from, to (Minuten), days (mo…su), season, frost, heat, wet (Std. nach Regen), margin;
    done: gemähte Stunden je Tag (ISO-Datum); sun: (Aufgang, Untergang) in Minuten oder None (kein Igelschutz);
    blocked: täglich gesperrte Zeiten (z. B. Bewässerung) in Minuten.
    """
    from datetime import datetime, timedelta  # noqa: PLC0415 - logic.py bleibt ohne Home Assistant importierbar

    allowed = [d for d in MOW_DAYS if d in set(cfg.get("days") or MOW_DAYS)] or list(MOW_DAYS)
    frm, to = int(cfg.get("from", 540)), int(cfg.get("to", 1140))
    today = now_local.date()
    # Vorhersage je (Datum, Stunde)
    fc: dict[tuple, dict] = {}
    for h in hours or []:
        try:
            local = datetime.fromtimestamp(h["ts"], now_local.tzinfo)
        except (KeyError, TypeError, ValueError, OSError):
            continue
        fc[(local.date(), local.hour)] = h
    day_temps = [h["temp"] for (d, hr), h in fc.items() if h.get("temp") is not None and frm // 60 <= hr < max(frm // 60 + 1, to // 60)]
    mean = sum(day_temps) / len(day_temps) if day_temps else None
    factor = mow_growth(mean, now_local.month) if cfg.get("season", True) else 1.0
    target = float(cfg.get("hours_week") or 0) * factor
    quota = target / len(allowed) if allowed else 0
    # Nachholen: was an erlaubten Tagen der letzten Woche fehlte (oder zu viel war), höchstens 2 Tagesmengen
    backlog = 0.0
    for i in range(1, 8):
        d = today - timedelta(days=i)
        if MOW_DAYS[d.weekday()] in allowed and d.isoformat() in done:  # nur Tage mit Messung
            backlog += quota - float(done[d.isoformat()] or 0)
    backlog = max(0.0, min(backlog, 2 * quota))
    margin = int(cfg.get("margin") or 0)
    wet = int(cfg.get("wet", 2))
    frost, heat = cfg.get("frost"), cfg.get("heat")
    now_min = now_local.hour * 60 + now_local.minute
    carry = backlog + max(0.0, quota - float(done.get(today.isoformat(), 0) or 0)) - quota  # heute schon Gemähtes zählt
    out_days = []
    holidays = set(cfg.get("holidays") or [])
    hmode = cfg.get("holiday") or "sunday"
    for i in range(7):
        d = today + timedelta(days=i)
        wd = MOW_DAYS[d.weekday()]
        holiday = d.isoformat() in holidays
        ok = wd in allowed
        if holiday:  # Feiertag laut Arbeitstage-Kalender: wie Sonntag, nicht mähen oder wie ein normaler Tag
            ok = False if hmode == "off" else ("su" in allowed) if hmode == "sunday" else ok
        slots = []  # (Beginn, Grund oder None)
        for s in range(frm, to, 30):
            why = None
            if i == 0 and s + 30 <= now_min:
                why = "vorbei"
            elif sun and (s < sun[0] + margin or s + 30 > sun[1] - margin):
                why = "night"
            elif any(a <= s < b or a < s + 30 <= b for a, b in blocked or []):
                why = "water"
            else:
                h = fc.get((d, s // 60))
                if h is not None:
                    if h.get("rain"):
                        why = "rain"
                    elif any((fc.get((d, s // 60 - k)) or {}).get("rain") for k in range(1, wet + 1)):
                        why = "wet"
                    elif frost is not None and h.get("temp") is not None and h["temp"] < frost:
                        why = "frost"
                    elif heat is not None and h.get("temp") is not None and h["temp"] >= heat:
                        why = "heat"
            slots.append((s, why))
        need = 0.0
        if ok:
            need = max(0.0, quota + carry)
        windows: list[list[int]] = []
        if need > 0:
            runs, cur = [], None
            for s, why in slots:
                if why is None:
                    cur = [s, s + 30] if cur is None else [cur[0], s + 30]
                else:
                    if cur:
                        runs.append(cur)
                    cur = None
            if cur:
                runs.append(cur)
            need_min = max(60, round(need * 60 / 30) * 30)
            fit = [r for r in runs if r[1] - r[0] >= need_min]
            if fit:
                windows = [[fit[0][0], fit[0][0] + need_min]]
            else:
                left = need_min
                for r in sorted(runs, key=lambda r: r[0] - r[1])[:2]:
                    if r[1] - r[0] < 60 or left <= 0:
                        continue
                    take = min(r[1] - r[0], max(60, left))
                    windows.append([r[0], r[0] + take])
                    left -= take
                windows.sort()
        planned = sum(b - a for a, b in windows) / 60
        carry = (need - planned) if ok else carry
        carry = max(0.0, carry)
        bad = []
        for s, why in slots:
            if why in (None, "vorbei"):
                continue
            if bad and bad[-1][2] == why and bad[-1][1] == s:
                bad[-1][1] = s + 30
            else:
                bad.append([s, s + 30, why])
        out_days.append({"date": d.isoformat(), "wd": wd, "allowed": ok, "holiday": holiday, "windows": windows,
                         "hours": round(planned, 2), "bad": bad})
    return {"target": round(target, 1), "factor": round(factor, 2), "quota": round(quota, 2), "backlog": round(backlog, 2),
            "mean_temp": None if mean is None else round(mean, 1), "days": out_days,
            "planned": round(sum(x["hours"] for x in out_days), 1)}
