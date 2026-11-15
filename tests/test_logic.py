"""Tests für die Regel-Logik (ohne Home Assistant).

Ausführen im Projektordner: python -m pytest tests
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# logic.py direkt laden, ohne das Paket (und damit Home Assistant) zu importieren
_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "heizwerk" / "logic.py"
_spec = importlib.util.spec_from_file_location("heizwerk_logic", _PATH)
L = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(L)

SETTINGS = {"frost_temp": 7.0, "away_temp": 17.0, "vacation_temp": 15.0}
MON = 0


def room(**kw):
    base = {
        "type": L.TYPE_RADIATOR,
        "comfort": 21.0,
        "eco": 18.0,
        "schedule": [{"start": "06:00", "end": "22:00", "days": [0, 1, 2, 3, 4, 5, 6]}],
    }
    base.update(kw)
    return base


def target(r, minute, **kw):
    args = dict(window_paused=False, away=False, vacation=False, override=None)
    args.update(kw)
    return L.compute_target(r, SETTINGS, minute, **args)


def wm(h, m=0, day=MON):
    return L.week_minute(day, h, m)


# ------------------------------------------------------------------ Uhrzeiten
def test_parse_hm():
    assert L.parse_hm("06:30") == 390
    assert L.parse_hm("24:00") == 1440
    assert L.parse_hm("07:15:42") == 435
    with pytest.raises(ValueError):
        L.parse_hm("25:00")
    with pytest.raises(ValueError):
        L.parse_hm("abc")


# ------------------------------------------------------------------ Heizplan
def test_schedule_comfort_and_eco():
    assert target(room(), wm(12))["mode"] == "komfort"
    res = target(room(), wm(23))
    assert res["mode"] == "eco" and res["target"] == 18.0


def test_schedule_over_midnight():
    r = room(schedule=[{"start": "22:00", "end": "02:00", "days": [6]}])  # Sonntag
    assert L.schedule_at(r["schedule"], wm(1, 0, MON), 21, 18) == (21.0, True)  # Mo 01:00 (Wochenwechsel)
    assert L.schedule_at(r["schedule"], wm(3, 0, MON), 21, 18) == (18.0, False)


def test_preheat_before_comfort():
    res = target(room(), wm(5, 50), lead=15)
    assert res["mode"] == "vorheizen" and res["target"] == 21.0
    assert target(room(), wm(5, 30), lead=15)["mode"] == "eco"


def test_minutes_to_next_change():
    assert L.minutes_to_next_change(room()["schedule"], wm(21, 0)) == 60


# ------------------------------------------------------------------ Vorrang
def test_priority_order():
    r = room()
    assert target(room(enabled=False), wm(12))["mode"] == "aus"
    assert target(r, wm(12), window_paused=True)["mode"] == "fenster"
    assert target(r, wm(12), window_paused=True, liming=True)["mode"] == "fenster"
    assert target(r, wm(12), liming=True, summer=True)["mode"] == "entkalken"
    assert target(r, wm(12), summer=True, override=25)["mode"] == "sommer"
    assert target(r, wm(12), override=23, party=True)["mode"] == "manuell"
    assert target(r, wm(12), party=True, vacation=True)["mode"] == "party"
    assert target(r, wm(12), vacation=True, away=True)["mode"] == "urlaub"


def test_window_temp_and_pause_mode():
    res = target(room(window_temp=12.0), wm(12), window_paused=True)
    assert res["target"] == 12.0 and res["hvac_off"] is False
    assert target(room(pause_mode="off"), wm(12), window_paused=True)["hvac_off"] is True


def test_away_only_lowers():
    assert target(room(), wm(12), away=True)["target"] == 17.0
    res = target(room(), wm(23), away=True)  # Eco 18 > ? nein: 17 < 18 -> abgesenkt
    assert res["target"] == 17.0
    r = room(eco=16.0)
    assert target(r, wm(23), away=True)["mode"] == "eco"  # 17 würde anheben


def test_away_offset_and_off():
    s = dict(SETTINGS, away_mode="offset", away_offset=3)
    res = L.compute_target(room(), s, wm(12), window_paused=False, away=True, vacation=False, override=None)
    assert res["target"] == 18.0
    s = dict(SETTINGS, away_action="off")
    res = L.compute_target(room(), s, wm(12), window_paused=False, away=True, vacation=False, override=None)
    assert res["hvac_off"] is True


def test_long_away_frost():
    assert target(room(), wm(12), away=True, long_away=True)["mode"] == "frost"


def test_floor_max_setback():
    r = room(type=L.TYPE_FLOOR)
    assert target(r, wm(23))["target"] == 19.0  # höchstens 2 K unter Komfort


def test_presence():
    r = room(presence_sensor="binary_sensor.x")
    assert target(r, wm(12), occupied=False)["mode"] == "leer"
    r = room(presence_mode="always")
    assert target(r, wm(23), occupied=True)["mode"] == "belegt"


def test_warm_enough():
    r = room(off_above=1.0)
    assert target(r, wm(12), room_temp=22.5)["mode"] == "warm"
    assert target(r, wm(12), room_temp=21.5, was_warm=True)["mode"] == "warm"
    assert target(r, wm(12), room_temp=20.5, was_warm=True)["mode"] == "komfort"
    assert target(r, wm(12), room_temp=25, override=30, boost=True)["mode"] == "boost"


def test_schedule_entity():
    res = target(room(), wm(3), schedule_on=True, schedule_next_on=60)
    assert res["mode"] == "komfort" and res["next_change"] == 60
    assert target(room(), wm(12), schedule_on=False, schedule_next_on=10, lead=15)["mode"] == "vorheizen"


def test_eco_force():
    assert target(room(), wm(12), force_eco=True)["mode"] == "eco_fix"


# ------------------------------------------------------------------ Fenster
def test_window_paused():
    assert L.window_paused(100, None, False, 130, 60, 0) is False
    assert L.window_paused(100, None, False, 170, 60, 0) is True
    assert L.window_paused(None, 200, True, 210, 60, 30) is True
    assert L.window_paused(None, 200, True, 240, 60, 30) is False


# ------------------------------------------------------------------ Hilfen
def test_snap_and_compensation():
    assert L.snap(21.3, 0.5, 5, 30) == 21.5
    assert L.snap(3, 0.5, 5, 30) == 5
    assert L.compensated(21, 24, 20) == 25
    assert L.compensated(21, 30, 20) == 25  # auf 4 K begrenzt


def test_smart_lead_and_learning():
    assert L.smart_lead(21, 21, 2, 90) == 0
    assert L.smart_lead(19, 21, 2, 90) == 75
    assert L.smart_lead(15, 21, 1, 90) == 90
    assert L.smart_lead(None, 21, 1, 90) == 45
    assert L.learn_rate(None, 18, 21, 1.5) == 2.0
    assert L.learn_rate(2.0, 18, 21, 1.0) == 2.3
    assert L.learn_rate(2.0, 18, 18.2, 1.0) is None


def test_next_comfort():
    assert L.next_comfort(room()["schedule"], wm(5, 0), 21, 90) == (60, 21.0)
    assert L.next_comfort(room()["schedule"], wm(3, 0), 21, 90) is None


def test_aggressive():
    assert L.aggressive(21, 18, 2, 1.5) == 22.5
    assert L.aggressive(21, 24, 2, 1.5) == 19.5
    assert L.aggressive(21, 20.5, 2, 1.5) == 21


def test_calibration_offset():
    assert L.calibration_offset(20.0, 22.0, 0.0, 0.1, -5, 5) == -2.0
    assert L.calibration_offset(20.0, 20.03, 0.0, 0.1, -5, 5) is None
    assert L.calibration_offset(20.0, 30.0, 0.0, 0.1, -5, 5) == -5


def test_valve_opening():
    assert L.valve_opening(21, 21.5, 1.5, 100) == 0.0
    assert L.valve_opening(21, 19, 1.5, 100) == 100.0
    assert L.valve_opening(21, 20.25, 1.5, 100) == 50.0
    assert L.valve_opening(21, None, 1.5, 100) is None


def test_occupied():
    assert L.occupied(True, 200, False, 120, 1200) is True
    assert L.occupied(True, 60, False, 120, 1200) is False
    assert L.occupied(False, 600, True, 120, 1200) is True
    assert L.occupied(False, 1300, True, 120, 1200) is False


def test_summer_state():
    assert L.summer_state(17, 16, False) is True
    assert L.summer_state(15.5, 16, True) is True  # Hysterese
    assert L.summer_state(14.9, 16, True) is False
    assert L.summer_state(None, 16, True, fallback="heat") is False
    assert L.summer_state(None, 16, True) is True


def test_liming_active():
    s = {"liming": True, "liming_day": 0, "liming_time": "10:00", "liming_minutes": 5}
    assert L.liming_active(s, wm(10, 2)) is True
    assert L.liming_active(s, wm(10, 6)) is False
    assert L.liming_active(dict(s, liming=False), wm(10, 2)) is False


def test_distance_km():
    assert L.distance_km(1500, "m") == 1.5
    assert round(L.distance_km(1, "mi"), 3) == 1.609
    assert L.distance_km(None, "km") is None


def test_vacation():
    s = {"vacation_source": "period", "vacation_from": "2026-12-20", "vacation_to": "2026-12-27"}
    assert L.is_vacation(s, "2026-12-22") is True
    assert L.is_vacation(s, "2026-12-28") is False
    assert L.is_vacation({"vacation": True}, "2026-01-01") is True
    assert L.is_vacation({"vacation_source": "calendar"}, "2026-01-01", True) is True
    assert L.is_vacation({"vacation_source": "off", "vacation_from": "2026-01-01", "vacation_to": "2026-12-31"}, "2026-06-01") is False


def test_keywords():
    assert L.keywords("Urlaub, Ferien; Reise") == ["urlaub", "ferien", "reise"]
    assert L.keyword_match("Sommerferien Ostsee", ["ferien"]) is True
    assert L.keyword_match("Zahnarzt", ["ferien"]) is False
    assert L.keyword_match("egal", []) is True


def test_calendar_state():
    events = [(1000, 1600), (1600, 2200), (5000, 5600)]
    assert L.calendar_state(events, 1200) == (True, 16)  # durchgehend bis 2200
    assert L.calendar_state(events, 3000) == (False, 33)
    assert L.calendar_state(events, 6000) == (False, None)


def test_events_to_blocks():
    blocks = L.events_to_blocks([(0, "18:00", "22:00"), (2, "18:00", "22:00"), (5, "09:00", "12:00"), (1, "10:00", "10:00")])
    assert blocks == [
        {"days": [0, 2], "start": "18:00", "end": "22:00"},
        {"days": [5], "start": "09:00", "end": "12:00"},
    ]
