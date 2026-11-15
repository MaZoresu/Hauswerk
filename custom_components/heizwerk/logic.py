"""Reine Regel-Logik von Heizwerk (ohne Home-Assistant-Abhängigkeit, testbar)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

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
        "heat_rate": 2.0,          # K pro Stunde, Startwert bis Heizwerk den Raum kennt
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


def _week_blocks(blocks: list[dict]) -> list[tuple[int, int, float | None]]:
    out: list[tuple[int, int, float | None]] = []
    for block in blocks or []:
        start = parse_hm(block["start"])
        end = parse_hm(block["end"])
        if end <= start:  # über Mitternacht
            end += DAY_MIN
        days = block.get("days")
        if days is None:
            days = list(range(7))
        temp = block.get("temp")
        for day in days:
            out.append((int(day) * DAY_MIN + start, int(day) * DAY_MIN + end, temp))
    return out


def schedule_at(blocks: list[dict], week_min: int, comfort: float, eco: float) -> tuple[float, bool]:
    """Solltemperatur laut Heizplan und ob gerade ein Komfortblock aktiv ist."""
    week_min %= WEEK_MIN
    best: float | None = None
    for start, end, temp in _week_blocks(blocks):
        if start <= week_min < end or start <= week_min + WEEK_MIN < end:
            value = float(temp) if temp is not None else float(comfort)
            best = value if best is None else max(best, value)
    if best is None:
        return float(eco), False
    return best, True


def minutes_to_next_change(blocks: list[dict], week_min: int) -> int | None:
    """Minuten bis zur nächsten Blockgrenze im Heizplan."""
    points = set()
    for start, end, _ in _week_blocks(blocks):
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
    """Ermittelt Solltemperatur und Betriebsart eines Raums.

    Vorrang: Automatik aus > Fenster > Entkalken > Sommerpause > Boost/Manuell
    > Eco erzwungen > Party > Urlaub > Abwesend > Präsenzmelder > Heizplan.
    Danach kann "Warm genug" den Raum noch abschalten.

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

    def result(mode: str, target: float | None, hvac_off: bool = False) -> dict[str, Any]:
        if target is not None:
            target = round(min(MAX_TEMP, max(MIN_TEMP, target)), 1)
        return {"mode": mode, "target": target, "hvac_off": hvac_off, "next_change": next_change}

    if not room.get("enabled", True):
        return result("aus", None)

    if window_paused:
        # Eigene Fenster-Temperatur des Raums, sonst der allgemeine Frostschutz
        return result("fenster", float(window_temp) if window_temp is not None else frost, room_setting(room, "pause_mode") == "off")

    if liming:
        return result("entkalken", MAX_TEMP)

    if summer:
        return result("sommer", frost, settings.get("summer_action", "off") == "off")

    lead = int(lead if lead is not None else (room_setting(room, "lead_min") or 0))
    if use_entity:
        in_comfort = bool(schedule_on)
        target = comfort if in_comfort else eco
        mode = "komfort" if in_comfort else "eco"
        if not in_comfort and lead > 0 and schedule_next_on is not None and schedule_next_on <= lead:
            target, mode = comfort, "vorheizen"
    else:
        target, in_comfort = schedule_at(blocks, week_min, comfort, eco)
        mode = "komfort" if in_comfort else "eco"
        if not in_comfort and lead > 0:
            ahead, ahead_comfort = schedule_at(blocks, week_min + lead, comfort, eco)
            if ahead_comfort and ahead > target:
                target, mode = ahead, "vorheizen"

    if override is not None:
        target, mode = float(override), ("boost" if boost else "manuell")
    elif force_eco:
        target, mode = eco, "eco_fix"
    elif party:
        target, mode = max(target, comfort), "party"
    elif vacation:
        target, mode = float(settings.get("vacation_temp", 16)), "urlaub"
    elif away and long_away:
        # Lange niemand da: auf Frostschutz
        return result("frost", frost)
    elif away:
        if settings.get("away_action") == "off":
            return result("abwesend", target, True)
        if settings.get("away_mode") == "offset":
            away_temp = target - float(settings.get("away_offset", 2) or 0)
        else:
            away_temp = float(settings.get("away_temp", 17))
        if away_temp < target:
            target, mode = away_temp, "abwesend"
    elif occupied is not None:
        if occupied and room.get("presence_mode") == "always" and target < comfort:
            target, mode = comfort, "belegt"
        elif not occupied and mode in ("komfort", "vorheizen"):
            target, mode = eco, "leer"

    max_setback = float(room_setting(room, "max_setback") or 0)
    if max_setback > 0 and mode in ("eco", "abwesend", "urlaub", "leer"):
        target = max(target, comfort - max_setback)

    off_above = float(room_setting(room, "off_above") or 0)
    if off_above > 0 and room_temp is not None and mode != "boost":
        # Abschalten ab Soll + off_above, wieder einschalten, sobald der Raum unter Soll fällt.
        if room_temp >= target + off_above or (was_warm and room_temp >= target):
            return result("warm", target, True)

    return result(mode, target)


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
    for start, _end, temp in _week_blocks(blocks):
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
