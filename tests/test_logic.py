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
    res = target(r, wm(23), away=True)  # 17 würde anheben: bleibt 16, heißt aber „abwesend“
    assert res["mode"] == "abwesend" and res["target"] == 16.0
    assert target(room(), wm(12), away=True)["mode"] == "abwesend"  # nie „Komfort“, solange niemand da ist


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
    # nach dem Lüften: 30 Min. nicht messen; Fußbodenheizung erst nach 3 Std.
    assert L.cold_radiator(100, 19.0, 21.0, "komfort", False, None, 0, closed_ago=600) == (None, False)
    run, cold = L.cold_radiator(100, 19.0, 21.0, "komfort", False, None, 0, closed_ago=1900, floor=True)
    assert run and not cold
    assert L.cold_radiator(100, 19.1, 21.0, "komfort", False, run, 3600, floor=True)[1] is False
    assert L.cold_radiator(100, 19.1, 21.0, "komfort", False, run, 3 * 3600, floor=True)[1] is True
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


def test_tagesmittel_fuer_sommerpause():
    hourly_mean = L.hourly_mean
    now = 1000 * 3600 + 1800
    b = {str(1000 - i): [20.0 * 2, 2] for i in range(24)}  # 24 Stunden je 20 °C
    assert hourly_mean(b, now, 24) == 20.0
    b[str(1000)] = [30.0, 1]  # eine warme Stunde ändert das Mittel kaum
    assert 20 < hourly_mean(b, now, 24) < 21
    assert hourly_mean({str(1000): [25.0, 1]}, now, 24) is None  # zu wenig Werte
    old = {str(1000 - 30 - i): [10.0, 1] for i in range(10)}  # älter als 24 h zählt nicht
    assert hourly_mean({**b, **old}, now, 24) == hourly_mean(b, now, 24)


# ---------------------------------------------------------------- Rollwerk: Öffnen/Schließen vorausberechnen
import math as _m
from datetime import datetime as _dt, timedelta as _td, timezone as _tz


def _noaa(lat, lon, day, tz_h):
    """Unabhängige Sonnenhöhe/-richtung (NOAA, vereinfacht) als Funktion der Ortsminute – nur für Tests."""
    def pos(minute):
        t = _dt(day.year, day.month, day.day, tzinfo=_tz(_td(hours=tz_h))) + _td(minutes=minute)
        jd = t.timestamp() / 86400 + 2440587.5
        n = jd - 2451545.0
        L = (280.46 + 0.9856474 * n) % 360
        g = _m.radians((357.528 + 0.9856003 * n) % 360)
        lam = _m.radians(L + 1.915 * _m.sin(g) + 0.020 * _m.sin(2 * g))
        eps = _m.radians(23.439 - 0.0000004 * n)
        dec = _m.asin(_m.sin(eps) * _m.sin(lam))
        ra = _m.atan2(_m.cos(eps) * _m.sin(lam), _m.cos(lam))
        gmst = (280.46061837 + 360.98564736629 * n) % 360
        ha = _m.radians((gmst + lon) % 360) - ra
        la = _m.radians(lat)
        el = _m.asin(_m.sin(la) * _m.sin(dec) + _m.cos(la) * _m.cos(dec) * _m.cos(ha))
        az = _m.degrees(_m.atan2(-_m.sin(ha), _m.tan(dec) * _m.cos(la) - _m.sin(la) * _m.cos(ha))) % 360
        return _m.degrees(el), az
    return (lambda m: pos(m)[0]), (lambda m: pos(m)[1])


def test_sonne_kreuzt_genau_leipzig():
    from datetime import date
    elev, azim = _noaa(51.34, 12.37, date(2026, 11, 20), 1)
    down = L.sun_crossing(elev, 0.0, False, lo=720)
    up = L.sun_crossing(elev, 0.0, True)
    # Leipzig, 20.11.: Sonnenuntergang (Mittelpunkt 0°) gegen 16:16, Aufgang gegen 07:38
    assert 16 * 60 + 8 <= down <= 16 * 60 + 24, down
    assert 7 * 60 + 28 <= up <= 7 * 60 + 46, up
    assert abs(elev(down)) < 0.01  # auf Sekunden genau


def _prof(**kw):
    base = {"features": ["up", "down", "time", "sun"], "sun_up": 0, "sun_down": 0, "sun_duration": 0}
    base.update(kw)
    return base


def test_schliessen_nach_sonnenhoehe_mit_zeitfenster_und_dauer():
    from datetime import date
    elev, azim = _noaa(51.34, 12.37, date(2026, 11, 20), 1)
    sunset = L.sun_crossing(elev, 3.0, False, lo=720)
    # Fenster 16:00–22:00, Sonnenhöhe 3°, 5 Min. am Stück: Schließen zur Kreuzung + 5 Min.
    p = L.predict_open_close(_prof(sun_down=3, sun_duration=300), (420, 540), (900, 1320), elev, azim)
    assert p["close"] == _m.ceil(sunset + 5), (p, sunset)
    # früheste Zeit erst 17:30 → Sonne schon tiefer → genau 17:30
    p = L.predict_open_close(_prof(sun_down=3), (420, 540), (1050, 1320), elev, azim)
    assert p["close"] == 1050
    # späteste Zeit 15:00 vor der Kreuzung → 15:00 (späteste Zeit greift)
    p = L.predict_open_close(_prof(sun_down=3), (420, 540), (840, 900), elev, azim)
    assert p["close"] == 900
    # Öffnen: aufsteigend 5°, Fenster 06:00–09:00
    rise5 = L.sun_crossing(elev, 5.0, True)
    p = L.predict_open_close(_prof(sun_up=5), (360, 540), (900, 1320), elev, azim)
    assert p["open"] == _m.ceil(rise5)
    # Sonne erreicht 30° im November nie: Öffnen zur spätesten Zeit, ohne Zeitsteuerung gar nicht
    assert L.predict_open_close(_prof(sun_up=30), (360, 540), None, elev, azim)["open"] == 540
    assert L.predict_open_close(_prof(sun_up=30, features=["up", "down", "sun"]), None, None, elev, azim)["open"] is None


def test_vorhersage_ohne_erfundene_zeit():
    from datetime import date
    elev, azim = _noaa(51.34, 12.37, date(2026, 11, 20), 1)
    # nur Helligkeit: nicht vorhersagbar
    p = L.predict_open_close(_prof(features=["up", "down", "time", "brightness"]), (420, 540), (900, 1320), elev, azim)
    assert p["open"] is None and p["close"] is None
    # nur Zeit: früheste Zeit
    p = L.predict_open_close(_prof(features=["up", "down", "time"]), (420, 540), (1000, 1320), None, None)
    assert p == {"open": 420, "close": 1000, "stage1": None}
    # Schließen aus: keine Schließzeit
    assert L.predict_open_close(_prof(features=["up", "time", "sun"]), (420, 540), (900, 1320), elev, azim)["close"] is None
    # zwei Stufen: Stufe 1 bei Sonnenrichtung 220°, Stufe 2 zur spätesten Zeit
    p = L.predict_open_close(_prof(close_stage1=True, stage1_trigger="azimuth", stage1_azimuth=220), (420, 540), (900, 1320), elev, azim)
    assert p["close"] == 1320 and 13 * 60 <= p["stage1"] <= 16 * 60 and abs(azim(p["stage1"]) - 220) < 0.5


def test_kamin_zusaetzliche_waerme():
    """Wärmer ohne Heizanforderung → „vielleicht Kamin“; Restwärme der Heizung zählt nicht; Phasen mit Nachwirkung."""
    t0 = 100000.0
    # 2 Std. ruhig bei 20 °C ohne Heizung, dann in 30 Min. +0,8 °C
    s = [(t0 + i * 60, 20.0, False) for i in range(90)] + [(t0 + (90 + i) * 60, 20.0 + 0.8 * i / 30, False) for i in range(31)]
    now = s[-1][0]
    assert L.extra_heat_rise(s, now) == 0.8
    # geheizt in den letzten 50 Min. → Restwärme, keine Aussage
    h = [(ts, t, ts > now - 2700 and ts < now - 2400) for ts, t, _ in s]
    assert L.extra_heat_rise(h, now) is None
    # Fußbodenheizung: Heizanforderung vor 2 Std. reicht schon aus
    f = [(ts, t, ts < now - 2 * 3600 + 60) for ts, t, _ in s]
    assert L.extra_heat_rise(f, now) == 0.8 and L.extra_heat_rise(f, now, floor=True) is None
    # zu kurze Vorgeschichte (Neustart) bzw. kleiner Anstieg
    assert L.extra_heat_rise(s[-31:], now) is None
    assert L.extra_heat_rise([(ts, 20.0 + (0.2 if ts > now - 600 else 0), False) for ts, _, _ in s], now) is None
    # Phasen
    p = L.fireplace_phase(None, now, rise=0.8, temp=20.8, target=20)
    assert p["state"] == "maybe" and p["cause"] == "kamin?"
    assert L.fireplace_phase(None, now, rise=0.8, signal=False)["cause"] == "other"
    on = L.fireplace_phase(p, now + 60, manual=True)
    assert on["state"] == "on" and on["source"] == "manuell"
    after = L.fireplace_phase(on, now + 600, temp=22.0, target=20)
    assert after["state"] == "after"
    assert L.fireplace_phase(after, now + 1200, temp=22.0, target=20)["state"] == "after"
    assert L.fireplace_phase(after, now + 1200, temp=20.2, target=20) is None  # abgekühlt
    assert L.fireplace_phase(after, now + 3 * 3600 + 120, temp=22.0, target=20) is None
    # Bericht: Kamin-Zeit ausgewiesen
    rows = [{"comfort_n": 300, "under_min": 0, "measured_min": 400, "over_min": 0, "fire_min": 120, "heat_min": 100, "comfort_dev": 0.1, "valve_avg": 40}]
    a = L.room_analysis(rows, None)
    assert a["facts"]["fire_h"] == 2.0 and any(f["title"] == "Zusätzliche Wärme herausgerechnet" for f in a["findings"])


def test_heizplan_modell():
    """Komfort-Fenster (Komfortwert bzw. eigene Temperatur), Eco-Fenster, sonst Eco; Mitternacht; Ursache."""
    blocks = [{"start": "06:00", "end": "08:00", "days": [0, 1, 2, 3, 4]},
              {"start": "17:00", "end": "21:00", "days": [0, 1, 2, 3, 4], "temp": 22.0},
              {"start": "12:00", "end": "13:00", "days": [0], "kind": "eco", "temp": 25}]
    at = lambda d, h, m=0: L.plan_state(blocks, d * 1440 + h * 60 + m, 21.0, 18.0)  # noqa: E731
    assert (at(0, 7)["target"], at(0, 7)["kind"], at(0, 7)["custom"]) == (21.0, "komfort", False)
    assert (at(0, 18)["target"], at(0, 18)["custom"]) == (22.0, True)
    assert (at(0, 10)["target"], at(0, 10)["kind"]) == (18.0, "eco")          # Lücke = Eco, ohne Eintrag
    assert (at(0, 12, 30)["target"], at(0, 12, 30)["kind"]) == (18.0, "eco_window")  # Eco-Fenster: Temperatur zählt nicht
    assert at(0, 8)["kind"] == "eco" and at(0, 21)["kind"] == "eco"           # Ende gehört nicht mehr dazu
    assert at(5, 7)["kind"] == "eco"                                          # Samstag kein Fenster
    assert L.plan_label(at(0, 18), 21.0) == "Komfort 17:00–21:00 (eigene 22,0 °C)"
    assert L.plan_label(at(0, 10), 21.0) == "Eco (kein Zeitfenster)"
    # Mitternacht: Sa 22:00 – So 02:00, So 23:00 – Mo 01:00 (Wochenwechsel)
    night = [{"start": "22:00", "end": "02:00", "days": [5]}, {"start": "23:00", "end": "01:00", "days": [6]}]
    assert L.plan_state(night, 6 * 1440 + 60, 21, 18)["kind"] == "komfort"
    assert L.plan_state(night, 30, 21, 18)["kind"] == "komfort"               # Montag 00:30
    assert L.plan_state(night, 90, 21, 18)["kind"] == "eco"
    assert L.block_conflicts(night) == []
    segs = L.day_segments(night, 6, 21, 18)
    assert [(s["start"], s["end"], s["kind"]) for s in segs] == [(0, 120, "komfort"), (120, 1380, "eco"), (1380, 1440, "komfort")]
    # „24:00“ und ganzer Tag
    assert L.block_conflicts([{"start": "00:00", "end": "24:00", "days": [0]}]) == []
    assert L.plan_state([{"start": "18:00", "end": "24:00", "days": [0]}], 23 * 60 + 59, 21, 18)["kind"] == "komfort"


def test_heizplan_konflikte_und_aufloesen():
    b = [{"start": "06:00", "end": "09:00", "days": [0, 1]}, {"start": "08:00", "end": "10:00", "days": [1], "temp": 23}]
    c = L.block_conflicts(b)
    assert len(c) == 1 and c[0]["i"] == 0 and c[0]["j"] == 1 and "Di 08:00–09:00" in c[0]["text"]
    assert "gleich" in L.block_conflicts([{"start": "07:00", "end": "07:00", "days": [0]}])[0]["text"]
    assert "kein Wochentag" in L.block_conflicts([{"start": "07:00", "end": "08:00", "days": []}])[0]["text"]
    # über Mitternacht in den nächsten Tag hinein
    n = [{"start": "22:00", "end": "07:00", "days": [6]}, {"start": "06:00", "end": "08:00", "days": [0]}]
    assert "Mo 06:00–07:00" in L.block_conflicts(n)[0]["text"]
    # Auflösen: Fenster 2 (höhere Temperatur) hat Vorrang → Fenster 1 am Di nur bis 08:00, am Mo unverändert
    r = L.resolve_overlaps(b, lambda i: (b[i].get("temp") or 21, -i))
    assert L.block_conflicts(r) == []
    assert {"start": "06:00", "end": "09:00", "days": [0]} in r and {"start": "06:00", "end": "08:00", "days": [1]} in r
    assert {"start": "08:00", "end": "10:00", "days": [1], "temp": 23} in r
    # Wirkung wie früher (höherer Wert gewinnt)
    for m in range(0, 7 * 1440, 15):
        assert L.plan_state(r, m, 21, 18)["target"] == max(
            [L.block_value("comfort", x.get("temp"), 21, 18) for x in b if L.plan_state([x], m, 21, 18)["kind"] == "komfort"] or [18])


def test_vent_balance():
    day = 86400
    b = L.vent_balance(0, {"2026-11-19": 68, "2026-11-20": 70, "2026-11-21": 66}, 65, None, 3.5 * day, "2026-11-21")
    assert b["level"] == "bad" and b["days"] == 3 and b["rh_morning"] == 68 and b["text"] == "3 Tage nicht gelüftet, Feuchte morgens 68 %"
    assert L.vent_balance(3 * day, {"2026-11-21": 55}, 65, None, 3.2 * day, "2026-11-21")["level"] == "ok"
    assert L.vent_balance(0, {"2026-11-21": 55}, 65, None, 2.1 * day, "2026-11-21")["level"] == "warn"
    assert L.vent_balance(None, {}, 65, {"level": "bad"}, 0, "2026-11-21")["level"] == "bad"


def test_lueften_lernen_hilft_beste_zeit():
    # Luftwechsel lernen: 10 Min. von 70 % auf 55 % bei 20 °C, draußen 5 °C / 80 %
    tau = L.vent_tau(10, 20, 70, 19, 55, 5, 80)
    assert tau and 5 < tau < 40
    assert L.vent_tau(10, 20, 50, 20, 50, 5, 80) is None  # keine Änderung
    assert L.vent_tau(10, 20, 60, 19, 55, 18, 90) is None  # draußen kaum trockener
    # ab 3 Messungen gelernt: kürzer als der Richtwert, wenn der Raum schnell lüftet
    m, learned = L.vent_learned_minutes([3, 3.5, 4], 21, 70, 5, 80, 65, L.vent_minutes(5))
    assert learned and 3 <= m < L.vent_minutes(5)
    assert L.vent_learned_minutes([4, 5], 21, 70, 5, 80, 65, 10) == (10, False)
    # hilft Lüften? draußen schwül → nein
    assert L.vent_helps(22, 65, 25, 90) is False and L.vent_helps(21, 65, 2, 80) is True and L.vent_helps(None, 65, 2, 80) is None
    # beste Lüftzeit: kein Regen, trocken, wenig Wärmeverlust; je eine am Vormittag und am Abend
    now = 1_000_000
    hours = [{"ts": now + i * 3600, "hour": (6 + i) % 24, "temp": t, "rh": 80, "rain": r} for i, (t, r) in
             enumerate([(2, False), (4, False), (6, True), (8, False), (9, False), (10, False), (11, False), (10, False), (8, False), (6, False), (5, False), (4, False)])]
    plan = L.vent_plan(hours, now, 21, 55)
    assert [p["hour"] for p in plan] == [9, 14], plan  # 8 Uhr regnet; je Hälfte die Stunde mit dem kleinsten Wärmeverlust
    assert all(p["minutes"] for p in plan)
    wet = [{**h, "rh": 100, "temp": 22} for h in hours]
    assert L.vent_plan(wet, now, 21, 55) == []
    assert L.next_dry_hour(hours, now, 21, 70)["hour"] == 7


def test_notify_emoji():
    """Dezent ein Emoji vor dem Titel: nach Stichwort, sonst nach Anlass; nicht doppelt."""
    assert L.with_emoji("Fenster offen – Regen", "storm") == "🌧️ Fenster offen – Regen"
    assert L.with_emoji("Sturm – Rollläden fahren hoch", "storm") == "💨 Sturm – Rollläden fahren hoch"
    assert L.with_emoji("Thermostat nicht erreichbar", "offline").startswith("📡")
    assert L.with_emoji("Heizkörper bleibt kalt", "cold").startswith("🌡️")
    assert L.with_emoji("Mähroboter braucht Hilfe", "mower").startswith("🆘")
    assert L.with_emoji("Waschmaschine fertig").startswith("🧺") and L.with_emoji("Wama fertig").startswith("✅")
    assert L.with_emoji("Mähroboter: Winterpause einlegen?", "mower_care").startswith("❄️")
    assert L.with_emoji("🪟 schon da", "window") == "🪟 schon da"
    assert L.with_emoji("Irgendwas", "unbekannt") == "Irgendwas"
