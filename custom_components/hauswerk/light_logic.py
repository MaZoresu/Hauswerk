"""Regel-Logik von Lichtwerk (ohne Home-Assistant-Abhängigkeit, testbar).

Vorbild ist das Blueprint „Smart Light“ (Blackshome): Licht schaltet bei festen Auslösern ein und aus –
Sonnenhöhe (fallend an, steigend aus), Umgebungshelligkeit (unter/über einem Lux-Wert), Uhrzeit und
Entitätszustand; dazu Wochentage, Helligkeit, Übergang, Farbe, dynamisches Licht, Nachtlicht und Bypass.
Lichtwerk ergänzt Bewegung (wie „Sensor Light“), Anwesenheit/Urlaub aus Hauswerk und die Ursache je Licht.

Ein **Profil** entspricht einer Smart-Light-Automation. Wie dort zählt der *Wechsel*: ein Einschalt-Auslöser
schaltet ein, ein Ausschalt-Auslöser aus – dazwischen bleibt es so (z. B. an bei Sonnenuntergang, aus um 23 Uhr,
und um 5 Uhr nicht wieder an, obwohl es noch dunkel ist).
"""
from __future__ import annotations

from typing import Any, Callable

from .logic import parse_hm, sun_crossing

# Profil: (Standardwert, Art). Arten: bool, num, time, text, entity, list, choice
LW_PROFILE_SPEC: dict[str, tuple[Any, str]] = {
    "name": ("Standard", "text"),
    # Einschalten
    "on_sun": (True, "bool"),          # Sonne sinkt unter sun_on
    "sun_on": (-1.0, "num"),
    "on_lux": (False, "bool"),         # Helligkeit fällt unter lux_on
    "lux_on": (30, "num"),
    "on_time": (False, "bool"),        # Uhrzeit
    "time_on": ("17:00", "time"),
    "on_entity": (False, "bool"),      # Entität geht an (z. B. Fernseher)
    "entity": (None, "entity"),
    "on_covers": (False, "bool"),      # Rollläden im selben Bereich schließen (abends)
    # Ausschalten
    "off_sun": (True, "bool"),         # Sonne steigt über sun_off
    "sun_off": (1.0, "num"),
    "off_lux": (False, "bool"),        # Helligkeit steigt über lux_off
    "lux_off": (80, "num"),
    "off_time": (True, "bool"),        # spätestens um
    "time_off": ("23:00", "time"),
    "off_entity": (False, "bool"),     # Entität geht aus
    "lux_sensor": (None, "entity"),    # leer = Helligkeit aus Hauswerk › Wetter bzw. erster Lux-Sensor
    # Bewegung (optional, wie „Sensor Light“)
    "motion": ([], "list"),
    "motion_off": (3, "num"),          # Minuten ohne Bewegung bis aus
    "motion_dark": (True, "bool"),     # nur wenn dunkel (Sonne/Helligkeit wie oben)
    # Tage
    "days": ([0, 1, 2, 3, 4, 5, 6], "list"),
    "day_mode": ("all", "choice"),     # all | workday | free (Arbeitstage-Kalender aus Hauswerk)
    # Licht
    "brightness": (80, "num"),
    "transition_on": (1, "num"),
    "transition_off": (2, "num"),
    "color": ("keep", "choice"),       # keep | temp | rgb
    "kelvin": (2700, "num"),
    "rgb": ("#ffb464", "text"),
    # Dynamisch
    "dynamic": ("off", "choice"),      # off | sun | lux
    "dyn_min": (35, "num"),
    "dyn_max": (100, "num"),
    "dyn_warm": (2200, "num"),
    "dyn_cold": (4000, "num"),
    # Nachtlicht
    "night": (False, "bool"),
    "night_from": ("22:30", "time"),
    "night_to": ("06:00", "time"),
    "night_brightness": (10, "num"),
    "night_kelvin": (2200, "num"),
    "night_adjust": (True, "bool"),    # brennt das Licht beim Wechsel, wird übergeblendet
    # Von Hand / Bypass
    "manual_hold": ("next", "choice"),  # next (bis zum nächsten Wechsel) | hours
    "manual_hours": (2, "num"),
    "bypass": (None, "entity"),         # Schalter „Lichtwerk pausieren“
    "bypass_action": ("keep", "choice"),  # keep | on | off
    # Hauswerk
    "away": ("off", "choice"),          # off (niemand zu Hause → aus) | keep
    "simulate": (False, "bool"),        # Urlaub: Anwesenheit vortäuschen (Zeiten zufällig ±30 Min.)
}
LW_PROFILE_DEFAULTS = {k: v for k, (v, _kind) in LW_PROFILE_SPEC.items()}

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _hm(m: float) -> str:
    m = int(round(m)) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def _de(v: float) -> str:
    return (f"{v:.1f}" if v % 1 else f"{v:.0f}").replace(".", ",")


def day_allowed(prof: dict, weekday: int, free: bool | None) -> bool:
    """Gilt das Profil an diesem Tag? Wochentage und – falls gewählt – Arbeitstag/frei aus dem Kalender."""
    days = prof.get("days")
    if days is not None and int(weekday) not in [int(d) for d in days]:
        return False
    mode = prof.get("day_mode") or "all"
    if mode == "workday":
        return free is False or (free is None and weekday < 5)
    if mode == "free":
        return free is True or (free is None and weekday >= 5)
    return True


def day_events(prof: dict, elev: Callable[[float], float | None] | None, allowed: bool = True,
               shift: float = 0) -> list[tuple[float, str, str]]:
    """Feste Auslöser eines Tages: [(Minute, "on"|"off", Grund)], zeitlich sortiert.

    Sonne: an, wenn sie abends unter sun_on sinkt; aus, wenn sie morgens über sun_off steigt.
    Uhrzeit: an um time_on, aus um time_off. An einem nicht erlaubten Tag gibt es nur Ausschalt-Auslöser.
    shift verschiebt alle Zeiten (Anwesenheitssimulation im Urlaub).
    """
    out: list[tuple[float, str, str]] = []
    if elev is not None:
        if prof.get("on_sun") and allowed:
            m = sun_crossing(elev, float(prof.get("sun_on", -1)), rising=False, lo=720, hi=1440)
            if m is not None:
                out.append((m, "on", f"Sonne unter {_de(float(prof.get('sun_on', -1)))}°"))
        if prof.get("off_sun"):
            m = sun_crossing(elev, float(prof.get("sun_off", 1)), rising=True, lo=0, hi=720)
            if m is not None:
                out.append((m, "off", f"Sonne über {_de(float(prof.get('sun_off', 1)))}°"))
    if prof.get("on_time") and allowed:
        try:
            out.append((float(parse_hm(prof.get("time_on") or "17:00")), "on", f"Uhrzeit {prof.get('time_on')}"))
        except ValueError:
            pass
    if prof.get("off_time"):
        try:
            out.append((float(parse_hm(prof.get("time_off") or "23:00")), "off", f"spätestens {prof.get('time_off')}"))
        except ValueError:
            pass
    if shift:
        out = [(min(1439.0, max(0.0, m + shift)), a, r) for m, a, r in out]
    return sorted(out, key=lambda e: (e[0], e[1] == "on"))  # gleiche Minute: erst aus, dann an


def latched_at(today: list[tuple[float, str, str]], yesterday: list[tuple[float, str, str]], minute: float
               ) -> tuple[bool, str | None, float | None]:
    """Stand der festen Auslöser zur Minute: letzter Wechsel heute davor, sonst der letzte von gestern.
    Rückgabe: (an?, Grund, Minute des Wechsels – negativ = gestern)."""
    last = [e for e in today if e[0] <= minute]
    if last:
        m, a, r = last[-1]
        return a == "on", r, m
    if yesterday:
        m, a, r = yesterday[-1]
        return a == "on", r, m - 1440
    return False, None, None


def day_plan(today: list[tuple[float, str, str]], yesterday: list[tuple[float, str, str]]) -> list[dict]:
    """Abschnitte, in denen das Licht laut festen Auslösern heute an ist: [{start, end, reason}]."""
    on, reason, _ = latched_at([], yesterday, 0)
    start = 0.0 if on else None
    segs: list[dict] = []
    for m, a, r in today:
        if a == "on" and start is None:
            start, reason = m, r
        elif a == "off" and start is not None:
            if m > start:
                segs.append({"start": round(start), "end": round(m), "reason": reason, "until": r})
            start = None
    if start is not None:
        segs.append({"start": round(start), "end": 1440, "reason": reason, "until": None})
    return segs


def in_window(minute: float, start: str | None, end: str | None) -> bool:
    """Liegt die Minute im Zeitraum (auch über Mitternacht)?"""
    try:
        a, b = parse_hm(start or ""), parse_hm(end or "")
    except ValueError:
        return False
    if a == b:
        return False
    return a <= minute < b if a < b else minute >= a or minute < b


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def light_params(prof: dict, minute: float, elev: float | None = None, lux: float | None = None) -> dict:
    """Helligkeit (%), Farbtemperatur (K) bzw. Farbe und Übergang für „an“ – Nachtlicht, dynamisch oder fest."""
    color = prof.get("color") or "keep"
    if prof.get("night") and in_window(minute, prof.get("night_from"), prof.get("night_to")):
        out = {"brightness": int(prof.get("night_brightness") or 10), "night": True, "mode": "Nachtlicht"}
        if color != "keep":
            out["kelvin"] = int(prof.get("night_kelvin") or 2200)
        return out
    dyn = prof.get("dynamic") or "off"
    if dyn != "off":
        if dyn == "sun" and elev is not None:
            f = _clamp((float(elev) + 6) / 36)            # −6° (Dämmerung) … 30°
            label = f"dynamisch nach Sonne ({_de(round(float(elev), 1))}°)"
        elif dyn == "lux" and lux is not None:
            f = _clamp(float(lux) / 200)                    # 0 … 200 lx
            label = f"dynamisch nach Helligkeit ({lux:.0f} lx)"
        else:
            f, label = None, None
        if f is not None:
            lo, hi = float(prof.get("dyn_min") or 35), float(prof.get("dyn_max") or 100)
            warm, cold = float(prof.get("dyn_warm") or 2200), float(prof.get("dyn_cold") or 4000)
            # hell draußen → kühler und (bei Sonne) heller; dunkel → warm und gedimmt
            out = {"brightness": int(round(lo + (hi - lo) * (f if dyn == "sun" else 1 - f))), "night": False, "mode": label}
            out["kelvin"] = int(round((warm + (cold - warm) * f) / 50) * 50)
            return out
    out = {"brightness": int(prof.get("brightness") or 80), "night": False, "mode": None}
    if color == "temp":
        out["kelvin"] = int(prof.get("kelvin") or 2700)
    elif color == "rgb":
        out["rgb"] = hex_rgb(prof.get("rgb") or "#ffb464")
    return out


def hex_rgb(value: str) -> list[int]:
    v = str(value or "").lstrip("#")
    if len(v) != 6:
        return [255, 180, 100]
    try:
        return [int(v[i:i + 2], 16) for i in (0, 2, 4)]
    except ValueError:
        return [255, 180, 100]


def decide(*, auto: bool = True, bypass_on: bool = False, bypass_action: str = "keep", manual: bool = False,
           away: bool = False, away_action: str = "off", simulating: bool = False,
           motion_on: bool = False, motion_reason: str | None = None,
           latched: bool = False, latched_reason: str | None = None) -> tuple[str | None, str]:
    """Die eine Vorrang-Logik von Lichtwerk: Soll „on“/„off“ oder None (nichts tun) und die Ursache.

    1. Automatik aus  2. Pause-Schalter (Bypass)  3. von Hand  4. niemand zu Hause (außer Urlaubs-Simulation)
    5. Bewegung  6. feste Auslöser des Profils (Sonne, Helligkeit, Uhrzeit, Entität, Rollläden)
    """
    if not auto:
        return None, "Automatik aus – Lichtwerk schaltet nicht"
    if bypass_on:
        if bypass_action == "on":
            return "on", "Pause-Schalter an – Licht an"
        if bypass_action == "off":
            return "off", "Pause-Schalter an – Licht aus"
        return None, "Pause-Schalter an – Lichtwerk wartet"
    if manual:
        return None, "Von Hand geschaltet – Automatik wartet"
    if away and not simulating and away_action == "off":
        return "off", "Niemand zu Hause"
    if motion_on:
        return "on", motion_reason or "Bewegung"
    if latched:
        return "on", latched_reason or "Profil"
    return "off", latched_reason or "kein Auslöser aktiv"
