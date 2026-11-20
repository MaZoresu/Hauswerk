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
        # Niemand da: immer „abwesend“ – höchstens die Abwesend-Temperatur, nie wärmer als der Plan
        target, mode = min(away_temp, target), "abwesend"
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


def cold_radiator(valve: float | None, room_temp: float | None, target: float | None, mode: str,
                  windows_open: bool, run: dict | None, now: float) -> tuple[dict | None, bool]:
    """Bleibt ein Heizkörper kalt, obwohl sein Ventil offen ist?

    run: laufende Beobachtung {since, t0} oder None. Ergebnis: (neue Beobachtung, kalt?).
    Kalt heißt: Ventil ≥ 90 % seit COLD_MINUTES Minuten, der Raum mindestens 0,5 °C unter Soll und
    in der Zeit um weniger als 0,3 °C wärmer geworden. Wird der Raum wärmer, beginnt die Messung neu.
    """
    active = (valve is not None and valve >= 90 and room_temp is not None and target is not None
              and target - room_temp >= 0.5 and mode not in NO_HEAT_MODES and not windows_open)
    if not active:
        return None, False
    if run is None or room_temp - run["t0"] >= 0.3:
        return {"since": now, "t0": room_temp}, False
    return run, now - run["since"] >= COLD_MINUTES * 60


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

    Kennzahlen: Komfort erreicht (Anteil der Komfortzeit, in der der Raum höchstens 0,5 °C unter Soll lag),
    Ø Abweichung vom Soll, Ø Ventilöffnung, Zeit mit Ventil ≥ 90 %, überheizt (> 1 °C über Soll), Aufheiz-
    geschwindigkeit. Daraus ein Urteil (good/tight/weak/reserve/sensor/nodata) und Hinweise mit Tipps.
    """
    floor = room_type == "flaeche"
    sum_ = lambda k: sum(r.get(k) or 0 for r in rows)  # noqa: E731
    cn, under, mn, over, full, heat = sum_("comfort_n"), sum_("under_min"), sum_("measured_min"), sum_("over_min"), sum_("full_min"), sum_("heat_min")
    pause, openings = sum_("pause_min"), sum_("openings")
    devs = [(r["comfort_dev"], r["comfort_n"]) for r in rows if r.get("comfort_dev") is not None and r.get("comfort_n")]
    dev = round(sum(d * n for d, n in devs) / sum(n for _, n in devs), 1) if devs else None
    valves = [(r["valve_avg"], 1) for r in rows if r.get("valve_avg") is not None]
    valve = round(sum(v for v, _ in valves) / len(valves)) if valves else None
    ok_pct = round(100 * (cn - under) / cn) if cn else None
    over_pct = round(100 * over / mn) if mn else None
    full_pct = round(100 * full / heat) if heat else None
    # kalte Tage (Ø außen < 3 °C) gegen milde
    cold = [r for r in rows if r.get("outside_avg") is not None and r["outside_avg"] < 3 and r.get("comfort_n")]
    mild = [r for r in rows if r.get("outside_avg") is not None and r["outside_avg"] >= 3 and r.get("comfort_n")]
    pct = lambda rs: round(100 * sum(r["comfort_n"] - r["under_min"] for r in rs) / sum(r["comfort_n"] for r in rs)) if rs else None  # noqa: E731
    ok_cold, ok_mild = pct(cold), pct(mild)
    findings: list[dict] = []
    add = lambda level, title, text: findings.append({"level": level, "title": title, "text": text})  # noqa: E731
    facts = {"ok_pct": ok_pct, "dev": dev, "valve": valve, "full_pct": full_pct, "over_pct": over_pct,
             "heat_h": round(heat / 60, 1), "rate": round(heat_rate, 2) if heat_rate else None,
             "ok_cold": ok_cold, "ok_mild": ok_mild, "pause_h": round(pause / 60, 1), "openings": openings}
    if cn < 120:
        return {"verdict": "nodata", "facts": facts,
                "findings": [{"level": "info", "title": "Noch zu wenig Daten",
                              "text": "Für eine Einschätzung braucht Hauswerk mindestens 2 Stunden Komfortzeit mit Messwert im gewählten Zeitraum."}]}
    verdict = "good"
    if ok_pct < 75 and (valve is None or valve >= 60 or (full_pct or 0) >= 30):
        verdict = "weak"
        add("warn", "Heizleistung reicht nicht",
            f"Der Raum erreicht nur in {ok_pct} % der Komfortzeit sein Soll, obwohl das Ventil im Schnitt {valve if valve is not None else '?'} % offen ist"
            + (f" und {full_pct} % der Heizzeit fast ganz offen steht" if full_pct else "") + ". "
            + ("Mögliche Gründe: Vorlauftemperatur der Fußbodenheizung zu niedrig, Heizkreis zu wenig Durchfluss (hydraulischer Abgleich)."
               if floor else "Mögliche Gründe: Heizkörper zu klein für den Raum, Vorlauftemperatur/Heizkurve zu niedrig, Luft im Heizkörper oder fehlender hydraulischer Abgleich."))
    elif ok_pct < 75:
        verdict = "sensor"
        add("warn", "Zu kalt, obwohl das Ventil wenig öffnet",
            f"Komfort nur in {ok_pct} % der Zeit erreicht, aber das Ventil steht im Schnitt nur bei {valve} %. "
            "Das Thermostat glaubt, es sei warm genug – es misst vermutlich am Heizkörper zu warm. Abhilfe: Raumsensor eintragen, "
            "Kalibrierung oder „Thermostat nachführen“ (Raum › Regelung/Erweitert) einschalten.")
    elif ok_pct < 90:
        verdict = "tight"
        add("info", "Heizleistung knapp",
            f"Komfort in {ok_pct} % der Zeit erreicht (Ø {dev:+.1f} °C). "
            + ("Früher vorheizen hilft (Vorheizen › Lernen), " if not floor else "Bei Fußbodenheizung längere Vorheizzeit wählen, ")
            + "oder die Heizkurve etwas anheben.")
    elif valve is not None and valve < 25 and (over_pct or 0) < 15:
        verdict = "reserve"
        add("ok", "Viel Reserve",
            f"Soll in {ok_pct} % der Zeit erreicht, Ventil im Schnitt nur {valve} % offen. "
            "Die Heizung könnte mit niedrigerer Vorlauftemperatur laufen – das spart, besonders bei Wärmepumpen.")
    else:
        add("ok", "Heizleistung passt", f"Soll in {ok_pct} % der Komfortzeit erreicht, Ø {dev:+.1f} °C, Ventil im Schnitt {valve if valve is not None else '–'} %.")
    if ok_cold is not None and ok_mild is not None and ok_mild - ok_cold >= 20 and len(cold) >= 2:
        add("warn", "Reicht bei Frost nicht",
            f"An kalten Tagen (unter 3 °C außen) wird der Komfort nur in {ok_cold} % der Zeit erreicht, an milden in {ok_mild} %. "
            "Die Heizkurve ist im kalten Bereich zu flach – Steilheit an der Heizung leicht erhöhen.")
    if over_pct is not None and over_pct >= 15:
        add("info", "Oft überheizt",
            f"In {over_pct} % der Zeit war es mehr als 1 °C wärmer als gewollt. Gründe: Sonne oder andere Wärmequellen, "
            + ("die Trägheit der Fußbodenheizung (früher absenken) " if floor else "ein zu hohes Soll am Thermostat ")
            + "oder ein Thermostat, das zu kalt misst. Spart Energie, wenn behoben.")
    if heat_rate:
        slow, fast = (0.2, 1.0) if floor else (0.5, 3.0)
        if heat_rate < slow:
            add("warn", "Heizt langsam auf", f"Gelernt: {heat_rate:.1f} °C pro Stunde. Für {'Fußbodenheizung' if floor else 'Heizkörper'} ist das wenig – Vorheizen startet deshalb früh.")
        elif heat_rate > fast:
            add("ok", "Heizt schnell auf", f"Gelernt: {heat_rate:.1f} °C pro Stunde – kurze Vorheizzeit reicht.")
    if pause >= 180 or openings >= 5 * max(1, len(rows)):
        add("info", "Viel gelüftet", f"{round(pause / 60, 1)} h Fensterpause bei {openings} Öffnungen. Stoßlüften (kurz, weit auf) verliert weniger Wärme als lange gekippte Fenster.")
    return {"verdict": verdict, "facts": facts, "findings": findings}


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
