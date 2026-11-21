"""WebSocket-Befehle für das Hauswerk-Panel."""
from __future__ import annotations

from functools import wraps
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, HOUSE_KEYS, LOG_DAYS, MODULE_GARDEN, MODULE_HEATING, MODULE_HOUSE, MODULE_LIGHT, MODULE_LOG, MODULE_POWER, MODULE_SHUTTER
from .logic import MODES, TYPE_DEFAULTS, TYPE_FLOOR, TYPE_RADIATOR, block_conflicts, parse_hm


def _hm(value: Any) -> str:
    """'HH:MM' (Sekunden, wie manche Geräte sie mitschicken, werden abgeschnitten)."""
    try:
        total = parse_hm(value)
    except (ValueError, AttributeError) as err:
        raise vol.Invalid(f"Ungültige Uhrzeit: {value}") from err
    return f"{total // 60:02d}:{total % 60:02d}"


def _opt(validator):
    return vol.Any(None, validator)


TEMP = vol.All(vol.Coerce(float), vol.Range(min=5, max=30))
ENTITY = vol.All(str, vol.Match(r"^[a-z0-9_]+\.[a-z0-9_]+$"))
ENTITY_LIST = vol.All([ENTITY], vol.Length(max=20))
SENSOR = vol.All(str, vol.Match(r"^sensor\.[a-z0-9_]+$"))
# Benachrichtigungskanal (siehe core.Haus.send)
CHANNEL = vol.All(str, vol.Match(
    r"^(ha|svc:[a-z0-9_]+|ent:notify\.[a-z0-9_]+|tts:tts\.[a-z0-9_]+\|media_player\.[a-z0-9_]+|sat:assist_satellite\.[a-z0-9_]+)$"))
CHANNELS = vol.All([CHANNEL], vol.Length(max=12))
MINUTES = vol.All(vol.Coerce(int), vol.Range(min=0, max=240))
NOTIFY_MODE = vol.Any(bool, vol.In(["off", "log", "normal", "important"]))

BLOCK_SCHEMA = vol.Schema(
    {
        vol.Required("start"): _hm,
        vol.Required("end"): _hm,
        vol.Optional("days", default=[0, 1, 2, 3, 4, 5, 6]): [vol.All(vol.Coerce(int), vol.Range(min=0, max=6))],
        vol.Optional("temp"): _opt(TEMP),
        # Art: comfort (Standard; Komfortwert oder eigene Temperatur) oder eco (ausdrücklich Eco)
        vol.Optional("kind"): vol.In(["comfort", "eco"]),
    },
    extra=vol.REMOVE_EXTRA,
)


def _schedule_error(connection, msg, blocks: list[dict]) -> bool:
    """Zeitfenster prüfen: keine Überschneidungen, Beginn ≠ Ende. True = Fehler gemeldet."""
    problems = block_conflicts(blocks or [])
    if problems:
        connection.send_error(msg["id"], "schedule_conflict", "; ".join(p["text"] for p in problems[:3]))
        return True
    return False

ROOM_SCHEMA = vol.Schema(
    {
        vol.Optional("id"): _opt(str),
        vol.Required("name"): vol.All(str, vol.Strip, vol.Length(min=1, max=60)),
        vol.Required("type"): vol.In([TYPE_RADIATOR, TYPE_FLOOR]),
        vol.Optional("icon"): _opt(str),
        vol.Optional("enabled", default=True): bool,
        vol.Optional("allow_manual", default=True): bool,
        vol.Optional("climates", default=[]): ENTITY_LIST,
        vol.Optional("windows", default=[]): ENTITY_LIST,
        vol.Optional("temp_sensor"): _opt(str),
        vol.Optional("humidity_sensor"): _opt(str),
        vol.Optional("comfort", default=21.0): TEMP,
        vol.Optional("eco", default=18.0): TEMP,
        vol.Optional("window_delay"): _opt(vol.All(vol.Coerce(int), vol.Range(min=0, max=7200))),
        vol.Optional("resume_delay"): _opt(vol.All(vol.Coerce(int), vol.Range(min=0, max=3600))),
        vol.Optional("pause_mode"): _opt(vol.In(["frost", "off"])),
        vol.Optional("lead_min"): _opt(vol.All(vol.Coerce(int), vol.Range(min=0, max=600))),
        vol.Optional("max_setback"): _opt(vol.All(vol.Coerce(float), vol.Range(min=0, max=15))),
        vol.Optional("compensation"): _opt(bool),
        vol.Optional("schedule", default=[]): vol.All([BLOCK_SCHEMA], vol.Length(max=50)),
        # Komfort/Eco aus Helfer-Entitäten
        vol.Optional("comfort_entity"): _opt(ENTITY),
        vol.Optional("eco_entity"): _opt(ENTITY),
        # Präsenzmelder
        vol.Optional("presence_sensor"): _opt(ENTITY),
        vol.Optional("presence_mode", default="plan"): vol.In(["plan", "always"]),
        vol.Optional("presence_on"): _opt(MINUTES),
        vol.Optional("presence_off"): _opt(MINUTES),
        # Feinregelung
        vol.Optional("min_instead_of_off", default=False): bool,
        vol.Optional("off_above"): _opt(vol.All(vol.Coerce(float), vol.Range(min=0, max=5))),
        vol.Optional("aggressive_range"): _opt(vol.All(vol.Coerce(float), vol.Range(min=0, max=5))),
        vol.Optional("aggressive_offset"): _opt(vol.All(vol.Coerce(float), vol.Range(min=0, max=5))),
        vol.Optional("calibration", default=False): bool,
        vol.Optional("valve_control", default=False): bool,
        vol.Optional("valve_diff"): _opt(vol.All(vol.Coerce(float), vol.Range(min=0.2, max=5))),
        vol.Optional("valve_max"): _opt(vol.All(vol.Coerce(float), vol.Range(min=10, max=100))),
        # Vorheizen: feste Vorlaufzeit oder lernend
        vol.Optional("preheat_mode"): _opt(vol.In(["fixed", "smart", "off"])),
        # Gemeinsamer Heizplan (leer = eigener Plan des Raums)
        vol.Optional("plan_id"): _opt(str),
        vol.Optional("preheat_max"): _opt(vol.All(vol.Coerce(int), vol.Range(min=10, max=600))),
        # Zeitplan aus Home Assistant statt eigenem Heizplan
        vol.Optional("schedule_entity"): _opt(ENTITY),
        vol.Optional("presence_schedule"): _opt(ENTITY),
        # Fenster-Temperatur je Raum (leer = Frostschutz)
        vol.Optional("window_temp"): _opt(TEMP),
        # Manuelle Änderungen getrennt nach Herkunft
        vol.Optional("manual_device"): _opt(bool),
        vol.Optional("manual_ui"): _opt(bool),
        # Fester Ausgleich und selbst gewählte Kalibrier-/Ventil-Entitäten
        vol.Optional("target_offset"): _opt(vol.All(vol.Coerce(float), vol.Range(min=-5, max=5))),
        vol.Optional("calibration_entities", default=[]): ENTITY_LIST,
        vol.Optional("valve_entities", default=[]): ENTITY_LIST,
        # Fenster ohne Kontakt: Temperatursturz erkennen
        vol.Optional("window_detect"): _opt(bool),
        vol.Optional("window_detect_drop"): _opt(vol.All(vol.Coerce(float), vol.Range(min=0.3, max=5))),
        vol.Optional("window_detect_min"): _opt(vol.All(vol.Coerce(int), vol.Range(min=5, max=60))),
        # Nach dem Duschen nachheizen (Minuten, 0 = aus) ab einem Feuchte-Anstieg in Prozentpunkten
        vol.Optional("shower_boost"): _opt(vol.All(vol.Coerce(int), vol.Range(min=0, max=120))),
        vol.Optional("use"): _opt(vol.In(["wohnen", "schlafen", "kind", "bad", "kueche", "buero", "flur"])),
        vol.Optional("vent_rh"): _opt(vol.All(vol.Coerce(int), vol.Range(min=0, max=95))),
        vol.Optional("co2_sensor"): _opt(str),
        vol.Optional("vent_morning"): _opt(bool),
        # Kamin im Raum: vorhanden; optional ein Signal „in Betrieb“ (Schalter, Binärsensor, Ofen-/Rohrtemperatur, Leistung)
        vol.Optional("fireplace"): _opt(bool),
        # Fensterpause der CCU überlassen, wenn der Fensterkontakt direkt mit dem Thermostat verknüpft ist (Standard an)
        vol.Optional("window_ccu"): _opt(bool),
        vol.Optional("fireplace_entity"): _opt(ENTITY),
        vol.Optional("shower_rise"): _opt(vol.All(vol.Coerce(float), vol.Range(min=3, max=40))),
        # Weitere Geräte nur zur Anzeige (z. B. Heizkörper-Thermostat oder Stellantrieb neben dem Wandthermostat)
        vol.Optional("show_entities", default=[]): ENTITY_LIST,
        # Wandthermostat und Heizkörper-Thermostate gekoppelt (z. B. Homematic IP): nur das Wandthermostat stellen
        vol.Optional("pair_mode"): _opt(vol.In(["auto", "off"])),
        # Mischbetrieb: diese Heizkörper-Thermostate helfen der Fußbodenheizung nur nach (ab assist_diff °C unter Soll)
        vol.Optional("assist_entities", default=[]): ENTITY_LIST,
        # Heizkörper-Thermostate, die Hauswerk selbst stellt, obwohl ein Wandthermostat im Raum ist
        vol.Optional("pair_exclude", default=[]): ENTITY_LIST,
        vol.Optional("assist_diff"): _opt(vol.All(vol.Coerce(float), vol.Range(min=0.2, max=3))),
    },
    extra=vol.REMOVE_EXTRA,
)

WIDGET_TYPES = ["vent", "light", "heat", "presence", "weather", "rooms", "shortcuts", "windows", "schedule", "report", "values", "forecast",
                "hints", "power", "shutters", "rwnext", "energy", "lage", "events", "calendar", "mower"]
WIDGET_SCHEMA = vol.Schema(
    {
        vol.Required("id"): vol.All(str, vol.Length(min=1, max=20)),
        vol.Required("type"): vol.In(WIDGET_TYPES),
        vol.Optional("size", default="m"): vol.In(["s", "m", "l", "w"]),  # klein, mittel, groß (w = alt für groß)
        vol.Optional("title"): _opt(vol.All(str, vol.Length(max=40))),
        vol.Optional("entities", default=[]): ENTITY_LIST,
        vol.Optional("mode"): _opt(vol.In(["hourly", "daily"])),  # Wetterprognose
    },
    extra=vol.REMOVE_EXTRA,
)

SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Optional("frost_temp"): TEMP,
        vol.Optional("away_temp"): TEMP,
        vol.Optional("away_delay"): vol.All(vol.Coerce(int), vol.Range(min=0, max=240)),
        vol.Optional("vacation_temp"): TEMP,
        vol.Optional("vacation"): bool,
        vol.Optional("vacation_from"): _opt(vol.Match(r"^\d{4}-\d{2}-\d{2}$")),
        vol.Optional("vacation_to"): _opt(vol.Match(r"^\d{4}-\d{2}-\d{2}$")),
        vol.Optional("persons"): ENTITY_LIST,
        vol.Optional("presence_force"): _opt(vol.In(["away"])),
        vol.Optional("arrive_delay"): MINUTES,
        vol.Optional("guest"): bool,
        vol.Optional("party"): bool,
        vol.Optional("proximity_sensors"): ENTITY_LIST,
        vol.Optional("proximity_m"): vol.All(vol.Coerce(float), vol.Range(min=0, max=50000)),
        vol.Optional("home_zone"): _opt(vol.All(str, vol.Match(r"^zone\.[a-z0-9_]+$"))),
        vol.Optional("summer_mode"): vol.In(["off", "auto", "on", "entity"]),
        vol.Optional("season_entity"): _opt(ENTITY),
        vol.Optional("summer_fallback"): vol.In(["keep", "heat", "summer"]),
        vol.Optional("summer_basis"): vol.In(["now", "day", "days3"]),
        vol.Optional("away_mode"): vol.In(["temp", "offset"]),
        vol.Optional("away_offset"): vol.All(vol.Coerce(float), vol.Range(min=0, max=10)),
        vol.Optional("away_action"): vol.In(["lower", "off"]),
        vol.Optional("long_away_days"): vol.All(vol.Coerce(float), vol.Range(min=0, max=60)),
        vol.Optional("eco_force"): bool,
        vol.Optional("calibration_interval"): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
        vol.Optional("outside_sensor"): _opt(ENTITY),
        vol.Optional("wind_sensor"): _opt(ENTITY),
        vol.Optional("summer_temp"): vol.All(vol.Coerce(float), vol.Range(min=5, max=30)),
        vol.Optional("summer_action"): vol.In(["off", "frost"]),
        vol.Optional("liming"): bool,
        vol.Optional("liming_day"): vol.All(vol.Coerce(int), vol.Range(min=0, max=6)),
        vol.Optional("liming_time"): _hm,
        vol.Optional("liming_minutes"): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
        vol.Optional("liming_winter"): bool,
        vol.Optional("boost_minutes"): vol.All(vol.Coerce(int), vol.Range(min=5, max=240)),
        vol.Optional("vacation_source"): vol.In(["off", "period", "calendar"]),
        vol.Optional("vacation_calendar"): _opt(ENTITY),
        vol.Optional("vacation_keywords"): _opt(vol.All(str, vol.Length(max=200))),
        vol.Optional("preheat_mode"): vol.In(["smart", "fixed", "off"]),
        vol.Optional("lead_radiator"): vol.All(vol.Coerce(int), vol.Range(min=0, max=600)),
        vol.Optional("lead_floor"): vol.All(vol.Coerce(int), vol.Range(min=0, max=600)),
        vol.Optional("allow_users"): bool,
        vol.Optional("weather_entity"): _opt(ENTITY),
        vol.Optional("start_widgets"): _opt(vol.All([WIDGET_SCHEMA], vol.Length(max=24))),
        vol.Optional("start_widgets_tablet"): _opt(vol.All([WIDGET_SCHEMA], vol.Length(max=24))),
        vol.Optional("tablet_wake"): ENTITY_LIST,
        vol.Optional("tablet_calendars"): ENTITY_LIST,
        vol.Optional("calendars"): ENTITY_LIST,
        vol.Optional("main_calendar"): _opt(vol.All(str, vol.Match(r"^calendar\.[a-z0-9_]+$"))),
        vol.Optional("waste_calendars"): ENTITY_LIST,
        vol.Optional("waste_hidden"): vol.All([vol.All(str, vol.Length(max=80))], vol.Length(max=30)),
        vol.Optional("waste_remind"): vol.Any(None, _hm),
        vol.Optional("notify_waste"): NOTIFY_MODE,
        # Darstellung
        vol.Optional("look_theme"): vol.In(["auto", "sun", "light", "dark"]),
        vol.Optional("look_accent"): _opt(vol.Match(r"^#[0-9a-fA-F]{6}$")),
        vol.Optional("look_background"): vol.In(["pattern", "daytime", "plain"]),
        vol.Optional("look_header_weather"): bool,
        vol.Optional("look_header_clock"): bool,
        # Wetter-Hinweise
        vol.Optional("cold_snap_temp"): vol.All(vol.Coerce(float), vol.Range(min=-30, max=25)),
        vol.Optional("storm_kmh"): vol.All(vol.Coerce(float), vol.Range(min=20, max=200)),
        # Benachrichtigungen
        vol.Optional("notify_targets"): vol.All([vol.All(str, vol.Match(r"^[a-z0-9_]+$"))], vol.Length(max=10)),
        vol.Optional("notify_channels"): CHANNELS,
        vol.Optional("notify_routes"): vol.All(dict, vol.Length(max=20), {vol.All(str, vol.Match(r"^[a-z_]{2,30}$")): CHANNELS}),
        vol.Optional("notify_hours"): vol.All(dict, vol.Length(max=20), {CHANNEL: vol.All([_hm], vol.Length(min=2, max=2))}),
        vol.Optional("notify_voice_away"): bool,
        vol.Optional("notify_emoji"): bool,
        vol.Optional("notify_bundle"): CHANNELS,
        vol.Optional("notify_off"): vol.All([CHANNEL], vol.Length(max=30)),
        vol.Optional("notify_storm"): NOTIFY_MODE,
        vol.Optional("notify_cover"): NOTIFY_MODE,
        vol.Optional("notify_light_away"): NOTIFY_MODE,
        vol.Optional("notify_light_offline"): NOTIFY_MODE,
        vol.Optional("notify_mower"): NOTIFY_MODE,
        vol.Optional("notify_mower_care"): NOTIFY_MODE,
        vol.Optional("notify_mower_guard"): NOTIFY_MODE,
        # Beetwerk (Garten)
        vol.Optional("bw_mower"): _opt(vol.All(str, vol.Match(r"^lawn_mower\.[a-z0-9_]+$"))),
        vol.Optional("bw_soil"): _opt(ENTITY),
        vol.Optional("bw_watering"): _opt(ENTITY),
        vol.Optional("bw_need"): _opt(ENTITY),
        vol.Optional("bw_valve"): _opt(ENTITY),
        vol.Optional("bw_pause"): vol.All([vol.In(["rain", "soil", "frost", "water"])], vol.Length(max=4)),
        vol.Optional("bw_soil_wet"): vol.All(vol.Coerce(int), vol.Range(min=20, max=100)),
        vol.Optional("bw_frost"): vol.All(vol.Coerce(float), vol.Range(min=-10, max=15)),
        vol.Optional("bw_water_after"): vol.All(vol.Coerce(int), vol.Range(min=0, max=600)),
        vol.Optional("bw_resume"): bool,
        vol.Optional("bw_resume_wait"): vol.All(vol.Coerce(int), vol.Range(min=0, max=600)),
        vol.Optional("bw_resume_until"): _hm,
        vol.Optional("bw_blades_days"): vol.All(vol.Coerce(int), vol.Range(min=0, max=365)),
        vol.Optional("bw_zones"): vol.All([vol.Schema({vol.Required("zone"): ENTITY, vol.Optional("valve"): _opt(ENTITY),
                                                      vol.Optional("valves"): vol.All([ENTITY], vol.Length(max=6)), vol.Optional("auto"): bool},
                                                      extra=vol.REMOVE_EXTRA)], vol.Length(max=16)),
        vol.Optional("bw_water_auto"): bool,
        vol.Optional("bw_water_time"): _hm,
        vol.Optional("bw_water_skip"): bool,
        vol.Optional("bw_guard"): bool,
        vol.Optional("bw_guard_sensors"): vol.All([ENTITY], vol.Length(max=10)),
        vol.Optional("bw_guard_wait"): vol.All(vol.Coerce(int), vol.Range(min=1, max=240)),
        vol.Optional("bw_camera"): _opt(vol.All(str, vol.Match(r"^camera\.[a-z0-9_]+$"))),
        vol.Optional("bw_night"): bool,
        vol.Optional("bw_night_margin"): vol.All(vol.Coerce(int), vol.Range(min=0, max=180)),
        vol.Optional("bw_heat"): bool,
        vol.Optional("bw_heat_temp"): vol.All(vol.Coerce(float), vol.Range(min=20, max=45)),
        vol.Optional("bw_season"): bool,
        vol.Optional("bw_watch"): bool,
        vol.Optional("bw_watch_min"): vol.All(vol.Coerce(int), vol.Range(min=5, max=240)),
        vol.Optional("bw_battery_min"): vol.All(vol.Coerce(int), vol.Range(min=30, max=95)),
        vol.Optional("bw_plan"): bool,
        vol.Optional("bw_plan_hours"): vol.All(vol.Coerce(float), vol.Range(min=1, max=60)),
        vol.Optional("bw_plan_season"): bool,
        vol.Optional("bw_plan_from"): _hm,
        vol.Optional("bw_plan_to"): _hm,
        vol.Optional("bw_plan_days"): vol.All([vol.In(["mo", "tu", "we", "th", "fr", "sa", "su"])], vol.Length(min=1, max=7)),
        # Lichtwerk
        vol.Optional("lw_lights"): vol.All([vol.All(str, vol.Match(r"^(light|switch|input_boolean)\.[a-z0-9_]+$"))], vol.Length(max=80)),
        vol.Optional("lw_lux_sensor"): _opt(SENSOR),
        vol.Optional("lw_away_min"): vol.All(vol.Coerce(int), vol.Range(min=5, max=720)),
        vol.Optional("notify_window"): NOTIFY_MODE,
        vol.Optional("notify_window_min"): vol.All(vol.Coerce(int), vol.Range(min=5, max=720)),
        vol.Optional("notify_offline"): NOTIFY_MODE,
        vol.Optional("notify_offline_min"): vol.All(vol.Coerce(int), vol.Range(min=1, max=720)),
        vol.Optional("notify_frost"): NOTIFY_MODE,
        vol.Optional("notify_battery"): NOTIFY_MODE,
        vol.Optional("notify_cold"): NOTIFY_MODE,
        vol.Optional("notify_vent"): NOTIFY_MODE,
        vol.Optional("notify_vent_done"): NOTIFY_MODE,
        # Rollwerk
        vol.Optional("rw_covers"): vol.All([vol.All(str, vol.Match(r"^cover\.[a-z0-9_]+$"))], vol.Length(max=60)),
        vol.Optional("rw_storm"): bool,
        vol.Optional("rw_wind_entity"): _opt(ENTITY),
        vol.Optional("rw_recovery"): vol.In(["never", "outage", "always"]),
        # Kraftwerk
        vol.Optional("kw_solar"): vol.All([SENSOR], vol.Length(max=10)),
        vol.Optional("kw_grid"): _opt(SENSOR),
        vol.Optional("kw_grid_export"): _opt(SENSOR),
        vol.Optional("kw_grid_invert"): bool,
        vol.Optional("kw_battery"): _opt(SENSOR),
        vol.Optional("kw_battery_invert"): bool,
        vol.Optional("kw_battery_soc"): _opt(SENSOR),
        vol.Optional("kw_battery_energy"): _opt(SENSOR),
        vol.Optional("kw_battery_kwh"): vol.Any(None, vol.All(vol.Coerce(float), vol.Range(min=0, max=100))),
        vol.Optional("kw_battery_min"): vol.All(vol.Coerce(int), vol.Range(min=0, max=90)),
        vol.Optional("kw_home"): _opt(SENSOR),
        vol.Optional("kw_consumers"): vol.All([SENSOR], vol.Length(max=20)),
        vol.Optional("kw_names"): vol.All(dict, vol.Length(max=20), {SENSOR: vol.All(str, vol.Length(max=40))}),
        vol.Optional("kw_appliances"): vol.All([vol.Schema({
            vol.Required("id"): vol.All(str, vol.Match(r"^[a-z0-9_]{1,40}$")),
            vol.Required("name"): vol.All(str, vol.Length(min=1, max=40)),
            vol.Required("type"): vol.In(["waschmaschine", "trockner", "geschirrspueler", "sonstiges"]),
            vol.Required("power"): SENSOR,
            vol.Optional("door"): _opt(vol.All(str, vol.Match(r"^binary_sensor\.[a-z0-9_]+$"))),
            vol.Optional("status"): _opt(vol.All(str, vol.Match(r"^[a-z_]+\.[a-z0-9_]+$"))),
            vol.Optional("status_done"): vol.All([vol.All(str, vol.Length(max=40))], vol.Length(max=10)),
            vol.Optional("notify"): CHANNELS,
            vol.Optional("notify_ha"): bool,
            vol.Optional("important"): bool,
        })], vol.Length(max=10)),
        vol.Optional("demand_entity"): _opt(vol.All(str, vol.Match(r"^climate\.[a-z0-9_]+$"))),
        vol.Optional("demand_action"): vol.In(["lower", "off"]),
        vol.Optional("demand_low"): vol.All(vol.Coerce(float), vol.Range(min=5, max=25)),
        vol.Optional("demand_valve"): vol.All(vol.Coerce(int), vol.Range(min=1, max=80)),
        vol.Optional("demand_hold"): vol.All(vol.Coerce(int), vol.Range(min=5, max=180)),
        vol.Optional("demand_preheat"): vol.All(vol.Coerce(float), vol.Range(min=0, max=5)),
        vol.Optional("notify_ha"): bool,
        vol.Optional("sun_entity"): _opt(vol.All(str, vol.Match(r"^sun\.[a-z0-9_]+$"))),
        vol.Optional("notify_quiet"): bool,
        vol.Optional("notify_quiet_from"): _hm,
        vol.Optional("notify_quiet_to"): _hm,
        vol.Optional("battery_low"): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
        vol.Optional("radio_entities"): ENTITY_LIST,
        vol.Optional("radio_limit"): vol.All(vol.Coerce(int), vol.Range(min=30, max=95)),
        # Vorheizen nach Wetter, Feiertage, Lüften
        vol.Optional("preheat_weather"): bool,
        vol.Optional("workday_entity"): _opt(vol.All(str, vol.Match(r"^binary_sensor\.[a-z0-9_]+$"))),
        vol.Optional("workday_as"): vol.All(vol.Coerce(int), vol.In([5, 6])),
        vol.Optional("workday_calendar"): _opt(vol.All(str, vol.Match(r"^calendar\.[a-z0-9_]+$"))),
        vol.Optional("vent_rh"): vol.All(vol.Coerce(int), vol.Range(min=0, max=95)),
        vol.Optional("vent_morning"): vol.Any(None, _hm),
        vol.Optional("vent_co2"): vol.All(vol.Coerce(int), vol.Range(min=0, max=5000)),
        vol.Optional("vent_cool"): bool,
        vol.Optional("vent_long_min"): vol.All(vol.Coerce(int), vol.Range(min=5, max=240)),
    },
    extra=vol.REMOVE_EXTRA,
)

PLAN_SCHEMA = vol.Schema(
    {
        vol.Optional("id"): _opt(str),
        vol.Required("name"): vol.All(str, vol.Strip, vol.Length(min=1, max=60)),
        vol.Optional("schedule", default=[]): vol.All([BLOCK_SCHEMA], vol.Length(max=50)),
        # Statt fester Zeitfenster einem Kalender folgen (Termin = Komfort)
        vol.Optional("calendar"): _opt(vol.All(str, vol.Match(r"^calendar\.[a-z0-9_]+$"))),
        vol.Optional("keyword"): _opt(vol.All(str, vol.Length(max=200))),
    },
    extra=vol.REMOVE_EXTRA,
)


def _ctl(hass: HomeAssistant):
    return (hass.data.get(DOMAIN) or {}).get(MODULE_HEATING)


def _haus(hass: HomeAssistant):
    return (hass.data.get(DOMAIN) or {}).get(MODULE_HOUSE)


def _rw(hass: HomeAssistant):
    return (hass.data.get(DOMAIN) or {}).get(MODULE_SHUTTER)


def _kw(hass: HomeAssistant):
    return (hass.data.get(DOMAIN) or {}).get(MODULE_POWER)


def _bw(hass: HomeAssistant):
    return (hass.data.get(DOMAIN) or {}).get(MODULE_GARDEN)


@websocket_api.websocket_command({vol.Required("type"): "hauswerk/beetwerk/water", vol.Optional("zone"): _opt(ENTITY),
                                  vol.Optional("minutes"): _opt(vol.All(vol.Coerce(float), vol.Range(min=1, max=120)))})
@websocket_api.async_response
async def ws_bw_water(hass: HomeAssistant, connection, msg) -> None:
    """Beetwerk: jetzt gießen – eine Zone (Minuten frei oder berechnete Dauer) oder alle Zonen mit Bedarf."""
    bw = _bw(hass)
    if bw is None:
        return _not_ready(connection, msg)
    res = await bw.async_water(msg.get("zone"), (msg["minutes"] * 60) if msg.get("minutes") else None, by=_who(connection))
    connection.send_result(msg["id"], {"result": res, "status": bw.status()})


@websocket_api.websocket_command({vol.Required("type"): "hauswerk/beetwerk/stop"})
@websocket_api.async_response
async def ws_bw_stop(hass: HomeAssistant, connection, msg) -> None:
    bw = _bw(hass)
    if bw is None:
        return _not_ready(connection, msg)
    await bw.async_water_stop(by=_who(connection))
    connection.send_result(msg["id"], {"status": bw.status()})


def _lw(hass: HomeAssistant):
    return (hass.data.get(DOMAIN) or {}).get(MODULE_LIGHT)


def _settings(hass: HomeAssistant) -> dict:
    """Alle Einstellungen, wie das Panel sie sieht: zentral (Kern), Heizwerk, Rollwerk (rw_…) und Kraftwerk (kw_…)."""
    haus, ctl, rw, kw, lw = _haus(hass), _ctl(hass), _rw(hass), _kw(hass), _lw(hass)
    return {**(haus.settings if haus else {}), **(ctl.settings if ctl else {}), **(rw.settings if rw else {}),
            **(kw.settings if kw else {}), **(lw.settings if lw else {}), **(_bw(hass).settings if _bw(hass) else {})}


def _log(hass: HomeAssistant):
    return (hass.data.get(DOMAIN) or {}).get(MODULE_LOG)


def _who(connection) -> str | None:
    """Name des Benutzers fürs Protokoll."""
    return getattr(connection.user, "name", None)


def _may_edit(hass: HomeAssistant, connection) -> bool:
    """Admins immer; andere Benutzer nur, wenn ein Admin es in den Einstellungen erlaubt hat."""
    if connection.user.is_admin:
        return True
    haus = _haus(hass)
    return bool(haus and haus.settings.get("allow_users"))


# Bedienen dürfen alle angemeldeten Benutzer (z. B. ein Tablet-Benutzer ohne Admin-Rechte):
# Anwesenheit, Urlaub, Gäste, Party, Eco – alles andere nur Admins bzw. mit Freigabe.
OPERATE_KEYS = {"vacation", "presence_force", "guest", "party", "eco_force"}


def require_editor(func):
    """Wie require_admin, aber mit der Freigabe „Alle Benutzer dürfen ändern“."""

    @wraps(func)
    def wrapper(hass: HomeAssistant, connection, msg):
        if not _may_edit(hass, connection):
            connection.send_error(
                msg["id"],
                "unauthorized",
                "Nur Administratoren dürfen das ändern. Ein Admin kann es unter Einstellungen › Berechtigungen für alle freigeben.",
            )
            return None
        return func(hass, connection, msg)

    return wrapper


def _not_ready(connection, msg) -> None:
    connection.send_error(msg["id"], "not_ready", "Hauswerk ist nicht eingerichtet")


@websocket_api.websocket_command({vol.Required("type"): "hauswerk/beetwerk/busy", vol.Optional("hours"): _opt(vol.All(vol.Coerce(float), vol.Range(min=0.25, max=24))),
                                  vol.Optional("until"): _opt(vol.In(["evening"]))})
@websocket_api.async_response
async def ws_bw_busy(hass: HomeAssistant, connection, msg) -> None:
    """Beetwerk: „Garten belegt“ – Mäher bleibt in der Station (… Stunden oder bis heute Abend); ohne Angabe aufheben."""
    bw = _bw(hass)
    if bw is None:
        return _not_ready(connection, msg)
    await bw.async_busy(msg.get("hours"), msg.get("until"), by=_who(connection))
    connection.send_result(msg["id"], {"status": bw.status()})


@websocket_api.websocket_command({vol.Required("type"): "hauswerk/beetwerk/timer", vol.Required("timer"): vol.All(vol.Coerce(int), vol.Range(min=1, max=14)),
                                  vol.Required("enable"): bool, vol.Required("start"): _hm, vol.Required("end"): _hm,
                                  vol.Required("days"): vol.All([vol.In(["mo", "tu", "we", "th", "fr", "sa", "su"])], vol.Length(max=7))})
@require_editor
@websocket_api.async_response
async def ws_bw_timer(hass: HomeAssistant, connection, msg) -> None:
    """Beetwerk: Zeitplan am Mäher ändern (Robonect)."""
    bw = _bw(hass)
    if bw is None:
        return _not_ready(connection, msg)
    await bw.async_timer(msg["timer"], msg["enable"], msg["start"], msg["end"], msg["days"], by=_who(connection))
    connection.send_result(msg["id"], {"status": bw.status()})


@websocket_api.websocket_command({vol.Required("type"): "hauswerk/heizen/get"})
@callback
def ws_get(hass: HomeAssistant, connection, msg) -> None:
    ctl = _ctl(hass)
    if ctl is None:
        return _not_ready(connection, msg)
    connection.send_result(
        msg["id"],
        {
            "settings": _settings(hass),
            "rooms": ctl.rooms,
            "plans": ctl.plans,
            # Soll-Sensor je Raum (für den Verlauf auf der Raumseite)
            "target_sensors": {
                room_id: er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"hauswerk_{room_id}_target")
                for room_id in ctl.rooms
            },
            "status": ctl.status(),
            "rollwerk": {"covers": _rw(hass).covers, "profiles": _rw(hass).profiles, "status": _rw(hass).status()} if _rw(hass) else None,
            "lichtwerk": {"lights": _lw(hass).lights, "profiles": _lw(hass).profiles, "status": _lw(hass).status(),
                          "automations": _lw(hass).automations()} if _lw(hass) else None,
            "defaults": TYPE_DEFAULTS,
            "modes": MODES,
            "is_admin": _may_edit(hass, connection),
            "user_admin": connection.user.is_admin,
            "user_name": getattr(connection.user, "name", None),
        },
    )


@websocket_api.websocket_command({vol.Required("type"): "hauswerk/heizen/subscribe"})
@callback
def ws_subscribe(hass: HomeAssistant, connection, msg) -> None:
    ctl = _ctl(hass)
    if ctl is None:
        return _not_ready(connection, msg)

    @callback
    def forward(status: dict) -> None:
        connection.send_message(websocket_api.event_message(msg["id"], status))

    connection.subscriptions[msg["id"]] = ctl.subscribe(forward)
    connection.send_result(msg["id"])
    forward(ctl.status())


@websocket_api.websocket_command(
    {vol.Required("type"): "hauswerk/heizen/room/save", vol.Required("room"): dict}
)
@require_editor
@websocket_api.async_response
async def ws_room_save(hass: HomeAssistant, connection, msg) -> None:
    ctl = _ctl(hass)
    if ctl is None:
        return _not_ready(connection, msg)
    try:
        room = ROOM_SCHEMA(msg["room"])
    except vol.Invalid as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    if room.get("id") and room["id"] not in ctl.rooms:
        room["id"] = None
    if _schedule_error(connection, msg, room.get("schedule")):
        return
    saved = await ctl.async_save_room(room, by=_who(connection))
    connection.send_result(msg["id"], saved)


@websocket_api.websocket_command(
    {vol.Required("type"): "hauswerk/heizen/room/delete", vol.Required("room_id"): str}
)
@require_editor
@websocket_api.async_response
async def ws_room_delete(hass: HomeAssistant, connection, msg) -> None:
    ctl = _ctl(hass)
    if ctl is None:
        return _not_ready(connection, msg)
    await ctl.async_delete_room(msg["room_id"], by=_who(connection))
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {vol.Required("type"): "hauswerk/heizen/settings/save", vol.Required("settings"): dict}
)
@websocket_api.async_response
async def ws_settings_save(hass: HomeAssistant, connection, msg) -> None:
    ctl = _ctl(hass)
    if ctl is None:
        return _not_ready(connection, msg)
    # Einstellungen nur mit Recht zum Ändern; Bedienen (Anwesenheit & Co.) dürfen alle
    if not _may_edit(hass, connection) and not set(msg["settings"]) <= OPERATE_KEYS:
        connection.send_error(
            msg["id"],
            "unauthorized",
            "Nur Administratoren dürfen das ändern. Ein Admin kann es unter Einstellungen › Berechtigungen für alle freigeben.",
        )
        return
    try:
        settings = SETTINGS_SCHEMA(msg["settings"])
    except vol.MultipleInvalid as err:
        first = err.errors[0]
        field = ".".join(str(p) for p in first.path) or "?"
        connection.send_error(msg["id"], "invalid_format", f"Ungültiger Wert bei „{field}“: {first.msg}")
        return
    except vol.Invalid as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    if not connection.user.is_admin:
        settings.pop("allow_users", None)  # die Freigabe selbst ändern nur Admins
    # Zentrale Einstellungen an den Kern, der Rest an Heizwerk
    house = {k: v for k, v in settings.items() if k in HOUSE_KEYS}
    shutter = {k: v for k, v in settings.items() if k.startswith("rw_")}
    power = {k: v for k, v in settings.items() if k.startswith("kw_")}
    light = {k: v for k, v in settings.items() if k.startswith("lw_")}
    garden = {k: v for k, v in settings.items() if k.startswith("bw_")}
    heat = {k: v for k, v in settings.items() if k not in HOUSE_KEYS and not k.startswith(("rw_", "kw_", "lw_", "bw_"))}
    if garden and _bw(hass):
        await _bw(hass).async_save_settings(garden, by=_who(connection))
        await _bw(hass).async_evaluate()
    if light and _lw(hass):
        await _lw(hass).async_save_settings(light, by=_who(connection))
    if shutter and _rw(hass):
        await _rw(hass).async_save_settings(shutter, by=_who(connection))
    if power and _kw(hass):
        await _kw(hass).async_save_settings(power, by=_who(connection))
    if house:
        await _haus(hass).async_save_settings(house, by=_who(connection))
    if heat:
        await ctl.async_save_settings(heat, by=_who(connection))
    elif house:
        await ctl.async_evaluate()
    connection.send_result(msg["id"], _settings(hass))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hauswerk/heizen/override",
        vol.Required("room_id"): str,
        vol.Optional("temp"): vol.Any(None, TEMP),
        vol.Optional("hours"): vol.Any(None, vol.All(vol.Coerce(float), vol.Range(min=0.25, max=72))),
        vol.Optional("boost", default=False): bool,
    }
)
@websocket_api.async_response
async def ws_override(hass: HomeAssistant, connection, msg) -> None:
    ctl = _ctl(hass)
    if ctl is None:
        return _not_ready(connection, msg)
    if msg["room_id"] not in ctl.rooms:
        connection.send_error(msg["id"], "not_found", "Raum nicht gefunden")
        return
    await ctl.async_set_override(msg["room_id"], msg.get("temp"), msg.get("hours"), msg["boost"], by=_who(connection))
    connection.send_result(msg["id"])


@websocket_api.websocket_command({vol.Required("type"): "hauswerk/heizen/links/refresh"})
@require_editor
@websocket_api.async_response
async def ws_links_refresh(hass: HomeAssistant, connection, msg) -> None:
    """Direktverknüpfungen der Homematic-CCU neu lesen (nur lesen)."""
    ctl = _ctl(hass)
    if ctl is None:
        return _not_ready(connection, msg)
    connection.send_result(msg["id"], await ctl.async_refresh_links(by=_who(connection)))


@websocket_api.websocket_command(
    {vol.Required("type"): "hauswerk/heizen/fireplace", vol.Required("room_id"): str, vol.Required("on"): bool}
)
@websocket_api.async_response
async def ws_fireplace(hass: HomeAssistant, connection, msg) -> None:
    """„Kamin in Betrieb“ von Hand – darf jeder (wie Temperatur von Hand)."""
    ctl = _ctl(hass)
    if ctl is None:
        return _not_ready(connection, msg)
    if not (ctl.rooms.get(msg["room_id"]) or {}).get("fireplace"):
        connection.send_error(msg["id"], "not_found", "Raum ohne Kamin")
        return
    await ctl.async_set_fireplace(msg["room_id"], msg["on"], by=_who(connection))
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hauswerk/heizen/report",
        vol.Optional("days", default=7): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
    }
)
@callback
def ws_report(hass: HomeAssistant, connection, msg) -> None:
    ctl = _ctl(hass)
    if ctl is None:
        return _not_ready(connection, msg)
    connection.send_result(msg["id"], ctl.report(msg["days"]))


@websocket_api.websocket_command(
    {vol.Required("type"): "hauswerk/heizen/preheat/reset", vol.Required("room_id"): str}
)
@require_editor
@websocket_api.async_response
async def ws_preheat_reset(hass: HomeAssistant, connection, msg) -> None:
    """Gelernte Aufheizgeschwindigkeit eines Raums vergessen (z. B. nach einem Umbau)."""
    ctl = _ctl(hass)
    if ctl is None:
        return _not_ready(connection, msg)
    ctl.heat_rates.pop(msg["room_id"], None)
    ctl._save()
    ctl.log.add("settings", "Aufheizgeschwindigkeit vergessen", f"wird neu gelernt · von {_who(connection)}",
                msg["room_id"], (ctl.rooms.get(msg["room_id"]) or {}).get("name"))
    await ctl.async_evaluate()
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {vol.Required("type"): "hauswerk/heizen/plan/save", vol.Required("plan"): dict}
)
@require_editor
@websocket_api.async_response
async def ws_plan_save(hass: HomeAssistant, connection, msg) -> None:
    """Gemeinsamen Heizplan anlegen oder ändern."""
    ctl = _ctl(hass)
    if ctl is None:
        return _not_ready(connection, msg)
    try:
        plan = PLAN_SCHEMA(msg["plan"])
    except vol.Invalid as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    if plan.get("id") and plan["id"] not in ctl.plans:
        plan["id"] = None
    if _schedule_error(connection, msg, plan.get("schedule")):
        return
    connection.send_result(msg["id"], await ctl.async_save_plan(plan, by=_who(connection)))


@websocket_api.websocket_command(
    {vol.Required("type"): "hauswerk/heizen/plan/delete", vol.Required("plan_id"): str}
)
@require_editor
@websocket_api.async_response
async def ws_plan_delete(hass: HomeAssistant, connection, msg) -> None:
    ctl = _ctl(hass)
    if ctl is None:
        return _not_ready(connection, msg)
    await ctl.async_delete_plan(msg["plan_id"], by=_who(connection))
    connection.send_result(msg["id"], {"rooms": ctl.rooms, "plans": ctl.plans})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hauswerk/heizen/calendar/import",
        vol.Required("entity_id"): vol.All(str, vol.Match(r"^calendar\.[a-z0-9_]+$")),
        vol.Optional("keyword"): _opt(vol.All(str, vol.Length(max=200))),
        vol.Optional("days", default=7): vol.All(vol.Coerce(int), vol.Range(min=1, max=14)),
    }
)
@require_editor
@websocket_api.async_response
async def ws_calendar_import(hass: HomeAssistant, connection, msg) -> None:
    """Termine eines Kalenders als Zeitfenster für einen Heizplan lesen (wird nicht gespeichert)."""
    ctl = _ctl(hass)
    if ctl is None:
        return _not_ready(connection, msg)
    try:
        blocks = await ctl.async_import_calendar(msg["entity_id"], msg.get("keyword"), msg["days"])
    except Exception as err:  # noqa: BLE001 - Fehler des Kalenders ans Panel melden
        connection.send_error(msg["id"], "calendar_error", f"Kalender nicht lesbar: {err}")
        return
    connection.send_result(msg["id"], {"blocks": blocks})


@websocket_api.websocket_command({
    vol.Required("type"): "hauswerk/kraftwerk/appliance/action",
    vol.Required("device"): str,
    vol.Required("action"): vol.In(["still_running", "finished", "no_run", "ack", "reset", "learn_history"]),
})
@websocket_api.async_response
async def ws_appliance_action(hass: HomeAssistant, connection, msg) -> None:
    """Gerät mit Fertigerkennung: Korrektur (alle Benutzer) bzw. neu lernen / aus dem Verlauf lernen (Bearbeiten)."""
    kw = _kw(hass)
    if kw is None:
        return _not_ready(connection, msg)
    if msg["action"] in ("reset", "learn_history") and not _may_edit(hass, connection):
        connection.send_error(msg["id"], "unauthorized", "Nur mit Berechtigung zum Ändern")
        return
    result = await kw.appliances.async_action(msg["device"], msg["action"], by=_who(connection))
    if not result.get("ok"):
        connection.send_error(msg["id"], "not_possible", result.get("error") or "Nicht möglich")
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): "hauswerk/notify/test", vol.Optional("channels"): CHANNELS,
                                  vol.Optional("title"): vol.All(str, vol.Length(max=80)),
                                  vol.Optional("message"): vol.All(str, vol.Length(max=300))})
@require_editor
@websocket_api.async_response
async def ws_notify_test(hass: HomeAssistant, connection, msg) -> None:
    """Testnachricht – ausdrücklich ausgelöst – an die übergebenen bzw. die Standard-Kanäle; Ergebnis je Kanal."""
    haus = _haus(hass)
    if haus is None:
        return _not_ready(connection, msg)
    channels = msg.get("channels")
    if channels is None:
        channels = haus.channels_for()
    if not channels:
        connection.send_error(msg["id"], "no_targets", "Erst einen Kanal auswählen")
        return
    result = await haus.async_test_notify(by=_who(connection), channels=channels, title=msg.get("title"), message=msg.get("message"))
    connection.send_result(msg["id"], {"results": result})


_CONTACT = _opt(vol.All(str, vol.Match(r"^(binary_sensor|input_boolean|sensor)\.[a-z0-9_]+$")))
COVER_SCHEMA = vol.Schema(
    {
        vol.Optional("profile"): vol.All(str, vol.Length(min=1, max=40)),
        vol.Optional("room"): _opt(vol.All(str, vol.Length(max=40))),
        vol.Optional("contacts"): _opt(vol.In(["none"])),
        vol.Optional("contact_open"): _CONTACT,
        vol.Optional("contact_tilted"): _CONTACT,
        vol.Optional("storm"): bool,
        vol.Optional("auto"): bool,
    },
    extra=vol.REMOVE_EXTRA,
)


def _profile_schema() -> vol.Schema:
    """Profil-Felder aus PROFILE_SPEC: Art bestimmt die Prüfung."""
    from .rollwerk import PROFILE_SPEC

    kinds = {
        "bool": bool,
        "num": _opt(vol.All(vol.Coerce(float), vol.Range(min=-100000, max=200000))),
        "time": _hm,
        "text": vol.All(str, vol.Length(max=60)),
        "entity": _opt(ENTITY),
        "list": vol.All([vol.All(str, vol.Length(max=40))], vol.Length(max=20)),
        "choice": vol.All(str, vol.Length(max=20)),
    }
    return vol.Schema({vol.Optional(k): kinds[kind] for k, (_d, kind) in PROFILE_SPEC.items()}, extra=vol.REMOVE_EXTRA)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hauswerk/rollwerk/profile/save",
        vol.Optional("profile_id"): vol.Any(None, vol.All(str, vol.Length(max=40))),
        vol.Required("profile"): dict,
    }
)
@require_editor
@websocket_api.async_response
async def ws_rw_profile_save(hass: HomeAssistant, connection, msg) -> None:
    rw = _rw(hass)
    if rw is None:
        return _not_ready(connection, msg)
    try:
        prof = _profile_schema()(msg["profile"])
    except vol.Invalid as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    pid = await rw.async_save_profile(msg.get("profile_id"), prof, by=_who(connection))
    connection.send_result(msg["id"], {"profile_id": pid, "profiles": rw.profiles})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hauswerk/rollwerk/profile/delete",
        vol.Required("profile_id"): vol.All(str, vol.Length(max=40)),
        vol.Optional("replace_with"): vol.Any(None, vol.All(str, vol.Length(max=40))),
    }
)
@require_editor
@websocket_api.async_response
async def ws_rw_profile_delete(hass: HomeAssistant, connection, msg) -> None:
    rw = _rw(hass)
    if rw is None:
        return _not_ready(connection, msg)
    await rw.async_delete_profile(msg["profile_id"], msg.get("replace_with"), by=_who(connection))
    connection.send_result(msg["id"], {"profiles": rw.profiles, "covers": rw.covers})


@websocket_api.websocket_command({vol.Required("type"): "hauswerk/rollwerk/subscribe"})
@callback
def ws_rw_subscribe(hass: HomeAssistant, connection, msg) -> None:
    rw = _rw(hass)
    if rw is None:
        return _not_ready(connection, msg)

    @callback
    def forward(status: dict) -> None:
        connection.send_message(websocket_api.event_message(msg["id"], status))

    connection.subscriptions[msg["id"]] = rw.subscribe(forward)
    connection.send_result(msg["id"])
    forward(rw.status())


@websocket_api.websocket_command(
    {vol.Required("type"): "hauswerk/rollwerk/cover/save", vol.Required("entity_id"): ENTITY, vol.Required("cover"): dict}
)
@require_editor
@websocket_api.async_response
async def ws_rw_cover_save(hass: HomeAssistant, connection, msg) -> None:
    rw = _rw(hass)
    if rw is None:
        return _not_ready(connection, msg)
    try:
        cfg = COVER_SCHEMA(msg["cover"])
    except vol.Invalid as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    await rw.async_save_cover(msg["entity_id"], cfg, by=_who(connection))
    connection.send_result(msg["id"], {"covers": rw.covers, "profiles": rw.profiles})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "hauswerk/rollwerk/command",
        vol.Required("entity_ids"): vol.All([vol.All(str, vol.Match(r"^cover\.[a-z0-9_]+$"))], vol.Length(min=1, max=60)),
        vol.Required("action"): vol.In(["open", "close", "stop", "position", "resume"]),
        vol.Optional("position"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
)
@websocket_api.async_response
async def ws_rw_command(hass: HomeAssistant, connection, msg) -> None:
    """Rollläden von Hand fahren (dürfen alle Benutzer)."""
    rw = _rw(hass)
    if rw is None:
        return _not_ready(connection, msg)
    await rw.async_command(msg["entity_ids"], msg["action"], msg.get("position"), by=_who(connection))
    connection.send_result(msg["id"])


# ---------------------------------------------------------------- Lichtwerk
def _lw_profile_schema() -> vol.Schema:
    from .light_logic import LW_PROFILE_SPEC

    kinds = {
        "bool": bool,
        "num": _opt(vol.All(vol.Coerce(float), vol.Range(min=-100000, max=200000))),
        "time": _hm,
        "text": vol.All(str, vol.Length(max=60)),
        "entity": _opt(ENTITY),
        "list": vol.All([vol.Any(vol.All(str, vol.Length(max=80)), vol.All(vol.Coerce(int), vol.Range(min=0, max=6)))], vol.Length(max=20)),
        "choice": vol.All(str, vol.Length(max=20)),
        "scenes": vol.All([vol.Schema({
            vol.Required("from"): _hm,
            vol.Optional("name"): vol.Any(None, vol.All(str, vol.Length(max=30))),
            vol.Optional("brightness"): vol.Any(None, vol.All(vol.Coerce(int), vol.Range(min=1, max=100))),
            vol.Optional("kelvin"): vol.Any(None, vol.All(vol.Coerce(int), vol.Range(min=2000, max=6500))),
        }, extra=vol.REMOVE_EXTRA)], vol.Length(max=8)),
    }
    return vol.Schema({vol.Optional(k): kinds[kind] for k, (_d, kind) in LW_PROFILE_SPEC.items()}, extra=vol.REMOVE_EXTRA)


LIGHT_ID = vol.All(str, vol.Match(r"^(light|switch|input_boolean)\.[a-z0-9_]+$"))
LIGHT_SCHEMA = vol.Schema({
    vol.Optional("profile"): vol.All(str, vol.Length(max=40)),
    vol.Optional("auto"): bool,
    vol.Optional("name"): vol.Any(None, vol.All(str, vol.Length(max=40))),
    vol.Optional("watt"): vol.Any(None, vol.All(vol.Coerce(float), vol.Range(min=0, max=5000))),
    vol.Optional("icon"): vol.Any(None, vol.All(str, vol.Match(r"^mdi:[a-z0-9-]{1,60}$"))),
}, extra=vol.REMOVE_EXTRA)


@websocket_api.websocket_command({vol.Required("type"): "hauswerk/lichtwerk/subscribe"})
@callback
def ws_lw_subscribe(hass: HomeAssistant, connection, msg) -> None:
    lw = _lw(hass)
    if lw is None:
        return _not_ready(connection, msg)

    @callback
    def forward(status: dict) -> None:
        connection.send_message(websocket_api.event_message(msg["id"], status))

    connection.subscriptions[msg["id"]] = lw.subscribe(forward)
    connection.send_result(msg["id"])
    forward(lw.status())


@websocket_api.websocket_command({
    vol.Required("type"): "hauswerk/lichtwerk/profile/save",
    vol.Optional("profile_id"): vol.Any(None, vol.All(str, vol.Length(max=40))),
    vol.Required("profile"): dict,
})
@require_editor
@websocket_api.async_response
async def ws_lw_profile_save(hass: HomeAssistant, connection, msg) -> None:
    lw = _lw(hass)
    if lw is None:
        return _not_ready(connection, msg)
    try:
        prof = _lw_profile_schema()(msg["profile"])
    except vol.Invalid as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    pid = await lw.async_save_profile(msg.get("profile_id"), prof, by=_who(connection))
    connection.send_result(msg["id"], {"profile_id": pid, "profiles": lw.profiles})


@websocket_api.websocket_command({
    vol.Required("type"): "hauswerk/lichtwerk/profile/delete",
    vol.Required("profile_id"): vol.All(str, vol.Length(max=40)),
    vol.Optional("replace_with"): vol.Any(None, vol.All(str, vol.Length(max=40))),
})
@require_editor
@websocket_api.async_response
async def ws_lw_profile_delete(hass: HomeAssistant, connection, msg) -> None:
    lw = _lw(hass)
    if lw is None:
        return _not_ready(connection, msg)
    await lw.async_delete_profile(msg["profile_id"], msg.get("replace_with"), by=_who(connection))
    connection.send_result(msg["id"], {"profiles": lw.profiles, "lights": lw.lights})


@websocket_api.websocket_command({vol.Required("type"): "hauswerk/lichtwerk/light/save", vol.Required("entity_id"): LIGHT_ID,
                                  vol.Required("light"): dict})
@require_editor
@websocket_api.async_response
async def ws_lw_light_save(hass: HomeAssistant, connection, msg) -> None:
    lw = _lw(hass)
    if lw is None:
        return _not_ready(connection, msg)
    try:
        cfg = LIGHT_SCHEMA(msg["light"])
    except vol.Invalid as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    await lw.async_save_light(msg["entity_id"], cfg, by=_who(connection))
    connection.send_result(msg["id"], {"lights": lw.lights, "settings": _settings(hass)})


@websocket_api.websocket_command({vol.Required("type"): "hauswerk/lichtwerk/light/remove", vol.Required("entity_id"): LIGHT_ID})
@require_editor
@websocket_api.async_response
async def ws_lw_light_remove(hass: HomeAssistant, connection, msg) -> None:
    lw = _lw(hass)
    if lw is None:
        return _not_ready(connection, msg)
    await lw.async_remove_light(msg["entity_id"], by=_who(connection))
    connection.send_result(msg["id"], {"lights": lw.lights, "settings": _settings(hass)})


@websocket_api.websocket_command({
    vol.Required("type"): "hauswerk/lichtwerk/command",
    vol.Required("entity_ids"): vol.All([LIGHT_ID], vol.Length(min=1, max=80)),
    vol.Required("action"): vol.In(["on", "off", "resume"]),
    vol.Optional("brightness"): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
})
@websocket_api.async_response
async def ws_lw_command(hass: HomeAssistant, connection, msg) -> None:
    """Licht von Hand schalten (dürfen alle Benutzer)."""
    lw = _lw(hass)
    if lw is None:
        return _not_ready(connection, msg)
    await lw.async_command(msg["entity_ids"], msg["action"], msg.get("brightness"), by=_who(connection))
    connection.send_result(msg["id"])


@websocket_api.websocket_command({vol.Required("type"): "hauswerk/lichtwerk/links/refresh"})
@require_editor
@websocket_api.async_response
async def ws_lw_links_refresh(hass: HomeAssistant, connection, msg) -> None:
    """Direktverknüpfungen der Leuchten aus der Homematic-CCU neu lesen (nur lesen)."""
    lw = _lw(hass)
    if lw is None:
        return _not_ready(connection, msg)
    res = await lw.async_refresh_links(by=_who(connection))
    await lw.async_evaluate()
    connection.send_result(msg["id"], res)


@websocket_api.websocket_command({vol.Required("type"): "hauswerk/lichtwerk/automation/off",
                                  vol.Required("entity_id"): vol.All(str, vol.Match(r"^automation\.[a-z0-9_]+$"))})
@require_editor
@websocket_api.async_response
async def ws_lw_automation_off(hass: HomeAssistant, connection, msg) -> None:
    lw = _lw(hass)
    if lw is None:
        return _not_ready(connection, msg)
    await lw.async_automation_off(msg["entity_id"], by=_who(connection))
    connection.send_result(msg["id"], {"automations": lw.automations()})


@websocket_api.websocket_command({vol.Required("type"): "hauswerk/log/get"})
@callback
def ws_log_get(hass: HomeAssistant, connection, msg) -> None:
    """Protokoll der letzten Tage (alle Module)."""
    log = _log(hass)
    if log is None:
        return _not_ready(connection, msg)
    connection.send_result(msg["id"], {"entries": log.entries, "days": LOG_DAYS})


@websocket_api.websocket_command({vol.Required("type"): "hauswerk/log/subscribe"})
@callback
def ws_log_subscribe(hass: HomeAssistant, connection, msg) -> None:
    """Neue Protokoll-Einträge live ans Panel schicken."""
    log = _log(hass)
    if log is None:
        return _not_ready(connection, msg)

    @callback
    def forward(entry: dict) -> None:
        connection.send_message(websocket_api.event_message(msg["id"], entry))

    connection.subscriptions[msg["id"]] = log.subscribe(forward)
    connection.send_result(msg["id"])


COMMANDS = (
    ws_get,
    ws_subscribe,
    ws_room_save,
    ws_room_delete,
    ws_settings_save,
    ws_override,
    ws_fireplace,
    ws_links_refresh,
    ws_report,
    ws_preheat_reset,
    ws_plan_save,
    ws_plan_delete,
    ws_calendar_import,
    ws_notify_test,
    ws_rw_subscribe,
    ws_rw_cover_save,
    ws_rw_command,
    ws_lw_subscribe,
    ws_lw_profile_save,
    ws_lw_profile_delete,
    ws_lw_light_save,
    ws_lw_light_remove,
    ws_lw_command,
    ws_lw_automation_off,
    ws_lw_links_refresh,
    ws_bw_water,
    ws_bw_stop,
    ws_bw_busy,
    ws_bw_timer,
    ws_rw_profile_save,
    ws_rw_profile_delete,
    ws_log_get,
    ws_log_subscribe,
    ws_appliance_action,
)


@callback
def async_register(hass: HomeAssistant) -> None:
    key = f"{DOMAIN}_ws_registered"
    if hass.data.get(key):
        return
    for command in COMMANDS:
        websocket_api.async_register_command(hass, command)
    hass.data[key] = True
