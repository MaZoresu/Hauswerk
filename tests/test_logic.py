"""Tests für die Regel-Logik (ohne Home Assistant).

Ausführen im Projektordner: python -m pytest tests
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# logic.py direkt laden, ohne das Paket (und damit Home Assistant) zu importieren
_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "hauswerk" / "logic.py"
_spec = importlib.util.spec_from_file_location("hauswerk_logic", _PATH)
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


# ------------------------------------------------------------ 0.19: Wetter, Lüften, Verläufe, Feiertage, Nachrichten
def test_weather_lead_factor():
    assert L.weather_lead_factor(None) == 1.0
    assert L.weather_lead_factor(5) == 1.0
    assert L.weather_lead_factor(-5) == pytest.approx(1.4)
    assert L.weather_lead_factor(15) == pytest.approx(0.6)
    assert L.weather_lead_factor(-40) == 1.8  # begrenzt


def test_abs_humidity_and_dew_point():
    assert L.abs_humidity(20, 50) == pytest.approx(8.6, abs=0.1)
    assert L.dew_point(20, 50) == pytest.approx(9.3, abs=0.1)


def test_ventilate_advice():
    # Winter: drinnen feucht, draußen kalt und damit trocken -> lüften
    advice = L.ventilate_advice(22, 72, 2, 90)
    assert advice and advice["rh"] == 72 and advice["inside_g"] > advice["outside_g"]
    # schwüler Sommer: draußen feuchter -> nicht lüften
    assert L.ventilate_advice(24, 70, 28, 80) is None
    # unter der Grenze oder ohne Werte -> nichts
    assert L.ventilate_advice(22, 60, 2, 90) is None
    assert L.ventilate_advice(22, 72, None, 90) is None
    assert L.ventilate_advice(22, 72, 2, 90, limit_rh=0) is None


def test_drop_and_rise_within():
    samples = [(0, 21.0), (60, 20.8), (120, 20.1), (180, 19.7)]
    assert L.drop_within(samples, 180, 300) == pytest.approx(1.3)
    assert L.drop_within(samples, 180, 60) == pytest.approx(0.4)
    assert L.drop_within([(0, 21.0)], 0, 300) == 0
    hums = [(0, 55.0), (300, 60.0), (600, 71.0)]
    assert L.rise_within(hums, 600, 900) == pytest.approx(16.0)


def test_holiday_week_minute():
    wed_10 = 2 * L.DAY_MIN + 600
    assert L.holiday_week_minute(wed_10, True) == wed_10
    assert L.holiday_week_minute(wed_10, None) == wed_10
    assert L.holiday_week_minute(wed_10, False) == 6 * L.DAY_MIN + 600  # wie Sonntag
    assert L.holiday_week_minute(wed_10, False, 5) == 5 * L.DAY_MIN + 600  # wie Samstag
    sat = 5 * L.DAY_MIN + 600
    assert L.holiday_week_minute(sat, False) == sat  # Wochenende bleibt


def test_in_quiet_hours():
    assert L.in_quiet_hours(23 * 60, "22:00", "07:00")
    assert L.in_quiet_hours(6 * 60, "22:00", "07:00")
    assert not L.in_quiet_hours(7 * 60, "22:00", "07:00")
    assert L.in_quiet_hours(13 * 60, "12:00", "14:00")
    assert not L.in_quiet_hours(13 * 60, None, "07:00")


def test_battery_level():
    assert L.battery_level("17", "battery", "%") == 17
    assert L.battery_level("on", "battery", None) == 0
    assert L.battery_level("off", "battery", None) == 100
    assert L.battery_level("3.1", "voltage", "V") is None
    assert L.battery_level("x", "battery", "%") is None


# ------------------------------------------------------------------ Andere Regelungen, Kopplung, Funk
def test_find_references_nested():
    attrs = {"settings": {"trv": "climate.wth", "heat_sources": [{"entity": "climate.trv"}]}, "x": "climate.andere"}
    assert L.find_references(attrs, {"climate.wth", "climate.trv", "climate.bad"}) == {"climate.wth", "climate.trv"}


def test_thermostat_kind():
    assert L.thermostat_kind("HmIP-WTH-2", "climate.s_wth_wohnzimmer_1") == "wall"
    assert L.thermostat_kind("HMIP-eTRV", "climate.a_heizkorper_wohnzimmer_1") == "trv"
    assert L.thermostat_kind(None, "climate.heizkoerper_bad") == "trv"
    assert L.thermostat_kind(None, "climate.wohnzimmer", "Wandthermostat Wohnzimmer") == "wall"
    assert L.thermostat_kind("Thermostat X", "climate.bad") is None
    # andere Hersteller
    for model in ("TRV_GEN2", "BTH-RA", "Radiator Thermostat II", "VA02", "NRV", "SRTS-A01", "TRVZB", "HR92",
                  "eTRV0100", "FRITZ!DECT 301", "Eve Thermo", "HM-CC-RT-DN", "SPZB0001"):
        assert L.thermostat_kind(model, "climate.x") == "trv", model
    for model in ("BTH-RM", "Room Thermostat II", "RU02", "T87RF", "NATherm1", "HM-TC-IT-WM-W-EU", "HmIP-BWTH", "BHT-002"):
        assert L.thermostat_kind(model, "climate.x") == "wall", model


def test_radio_should_send():
    assert L.radio_should_send(False, 20.0, 20.5, 10)
    assert not L.radio_should_send(True, 20.0, 20.5, 2000)  # kleine Änderung
    assert not L.radio_should_send(True, 20.0, 22.0, 300)  # zu bald
    assert L.radio_should_send(True, 20.0, 22.0, 1000)
    assert L.radio_should_send(True, 20.0, 20.5, 10, important=True)  # Wechsel der Betriebsart


def test_assist_on():
    # Grundlast Boden: erst ab 0,5 °C unter Soll hilft der Heizkörper
    assert not L.assist_on("komfort", 20.7, 21.0, 0.5, False)
    assert L.assist_on("komfort", 20.5, 21.0, 0.5, False)
    # bleibt an bis kurz vor Soll
    assert L.assist_on("komfort", 20.85, 21.0, 0.5, True)
    assert not L.assist_on("komfort", 20.95, 21.0, 0.5, True)
    # Vorheizen und Boost immer, Fenster nie
    assert L.assist_on("vorheizen", 22.0, 21.0, 0.5, False)
    assert L.assist_on("boost", 22.0, 30.0, 0.5, False)
    assert not L.assist_on("fenster", 15.0, 7.0, 0.5, True)
    assert L.assist_on("eco", None, 18.0, 0.5, False)


def test_cold_radiator():
    run, cold = L.cold_radiator(100, 19.0, 21.0, "komfort", False, None, 0)
    assert run == {"since": 0, "t0": 19.0} and not cold
    run, cold = L.cold_radiator(100, 19.1, 21.0, "komfort", False, run, 3600)
    assert cold  # eine Stunde offen, nur +0,1 °C
    run2, cold = L.cold_radiator(100, 19.4, 21.0, "komfort", False, run, 3700)
    assert not cold and run2["t0"] == 19.4  # wird wärmer: neu messen
    assert L.cold_radiator(50, 19.0, 21.0, "komfort", False, run, 7200) == (None, False)
    assert L.cold_radiator(100, 19.0, 21.0, "fenster", False, run, 7200) == (None, False)
    assert L.cold_radiator(100, 19.0, 21.0, "komfort", True, run, 7200) == (None, False)


def test_demand_state():
    assert L.demand_state(True, "low", None, 0, 20, False, 0) == "normal"
    assert L.demand_state(True, "normal", None, 0, 20, True, 1.5) == "raise"
    assert L.demand_state(False, "normal", 0, 600, 20, False, 0) == "normal"  # erst nach 20 Min.
    assert L.demand_state(False, "normal", 0, 1200, 20, False, 0) == "low"
    assert L.demand_state(False, "low", 0, 5, 20, False, 0) == "low"


def test_rollwerk_logic():
    assert L.facade_sun(180, 30, "S") and not L.facade_sun(90, 30, "W") and not L.facade_sun(180, 5, "S")
    assert L.facade_sun(350, 20, "N")
    s = {"rw_open_mode": "sun", "rw_open_not_before": "06:30", "rw_close_mode": "sun", "rw_close_offset": 15, "rw_close_not_after": "22:30"}
    assert L.day_window(5 * 60, 21 * 60 + 40, s, False) == (6 * 60 + 30, 21 * 60 + 55)
    assert L.day_window(8 * 60, 16 * 60 + 30, s, False) == (8 * 60, 16 * 60 + 45)
    assert L.day_window(5 * 60, 22 * 60 + 30, s, True)[0] == 8 * 60  # Wochenende frühestens 08:00
    t, why, _ = L.cover_target(12 * 60, 420, 1260, {"rw_shade": True, "rw_shade_temp": 24}, {"facade": "S"},
                               sun_on_facade=True, outside=28, storm=False)
    assert (t, why) == (30, "Sonnenschutz")
    assert L.cover_target(23 * 60, 420, 1260, {}, {}, sun_on_facade=False, outside=10, storm=False)[:2] == (0, "Nacht")
    assert L.cover_target(23 * 60, 420, 1260, {}, {"storm": True}, sun_on_facade=False, outside=10, storm=True)[0] == 100
    assert L.cover_target(12 * 60, 420, 1260, {}, {"auto": False}, sun_on_facade=False, outside=10, storm=True)[0] is None


def test_shade_conditions():
    prof = {"azimuth_start": 300, "azimuth_end": 60, "elevation_min": 10, "elevation_max": 90, "temp2_min": 24,
            "temp2_hyst": 0.5, "shade_start_and": ["azimuth", "elevation", "temp2"], "shade_end_or": ["azimuth", "temp2"]}
    start, end = L.shade_conditions({"azimuth": 20, "elevation": 30, "temp2": 25}, prof)
    assert start == {"azimuth": True, "elevation": True, "temp2": True}
    assert L.shade_wanted(prof, start, end, active=False)
    # 23.7 °C: unter Grenze, aber innerhalb der Hysterese -> bleibt
    start, end = L.shade_conditions({"azimuth": 20, "elevation": 30, "temp2": 23.7}, prof)
    assert not L.shade_wanted(prof, start, end, active=False) and not L.shade_wanted(prof, start, end, active=True)
    start, end = L.shade_conditions({"azimuth": 120, "elevation": 30, "temp2": 26}, prof)
    assert L.shade_wanted(prof, start, end, active=True)
    # nichts messbar -> keine Beschattung
    assert not L.shade_wanted(prof, {}, {}, active=False)


def _day(cn=600, under=0, dev=0.0, valve=40, full=0, heat=300, over=0, mn=1400, out=8.0):
    return {"comfort_n": cn, "under_min": under, "comfort_dev": dev, "valve_avg": valve, "full_min": full, "heat_min": heat,
            "over_min": over, "measured_min": mn, "outside_avg": out, "pause_min": 0, "openings": 0}


def test_room_analysis():
    assert L.room_analysis([_day(cn=60)], None)["verdict"] == "nodata"
    assert L.room_analysis([_day()] * 7, 1.2)["verdict"] == "good"
    weak = L.room_analysis([_day(under=300, dev=-1.2, valve=85, full=200)] * 7, 0.3)
    assert weak["verdict"] == "weak" and any(f["title"] == "Heizt langsam auf" for f in weak["findings"])
    assert L.room_analysis([_day(under=300, dev=-1.0, valve=20)] * 7, None)["verdict"] == "sensor"
    assert L.room_analysis([_day(valve=15)] * 7, None)["verdict"] == "reserve"
    frost = L.room_analysis([_day(out=0.0, under=200)] * 3 + [_day(out=8.0)] * 4, None)
    assert any(f["title"] == "Reicht bei Frost nicht" for f in frost["findings"])
