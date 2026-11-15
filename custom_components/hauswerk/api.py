"""WebSocket-Befehle für das Hauswerk-Panel."""
from __future__ import annotations

from functools import wraps
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, HOUSE_KEYS, LOG_DAYS, MODULE_HEATING, MODULE_HOUSE, MODULE_LOG
from .logic import MODES, TYPE_DEFAULTS, TYPE_FLOOR, TYPE_RADIATOR, parse_hm


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
MINUTES = vol.All(vol.Coerce(int), vol.Range(min=0, max=240))

BLOCK_SCHEMA = vol.Schema(
    {
        vol.Required("start"): _hm,
        vol.Required("end"): _hm,
        vol.Optional("days", default=[0, 1, 2, 3, 4, 5, 6]): [vol.All(vol.Coerce(int), vol.Range(min=0, max=6))],
        vol.Optional("temp"): _opt(TEMP),
    },
    extra=vol.REMOVE_EXTRA,
)

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
        vol.Optional("shower_rise"): _opt(vol.All(vol.Coerce(float), vol.Range(min=3, max=40))),
    },
    extra=vol.REMOVE_EXTRA,
)

WIDGET_TYPES = ["heat", "presence", "weather", "rooms", "shortcuts", "windows", "schedule", "report", "values", "forecast"]
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
        vol.Optional("away_mode"): vol.In(["temp", "offset"]),
        vol.Optional("away_offset"): vol.All(vol.Coerce(float), vol.Range(min=0, max=10)),
        vol.Optional("away_action"): vol.In(["lower", "off"]),
        vol.Optional("long_away_days"): vol.All(vol.Coerce(float), vol.Range(min=0, max=60)),
        vol.Optional("eco_force"): bool,
        vol.Optional("calibration_interval"): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
        vol.Optional("outside_sensor"): _opt(ENTITY),
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
        # Darstellung
        vol.Optional("look_theme"): vol.In(["auto", "light", "dark"]),
        vol.Optional("look_accent"): _opt(vol.Match(r"^#[0-9a-fA-F]{6}$")),
        vol.Optional("look_background"): vol.In(["pattern", "daytime", "plain"]),
        vol.Optional("look_header_weather"): bool,
        vol.Optional("look_header_clock"): bool,
        # Wetter-Hinweise
        vol.Optional("cold_snap_temp"): vol.All(vol.Coerce(float), vol.Range(min=-30, max=25)),
        vol.Optional("storm_kmh"): vol.All(vol.Coerce(float), vol.Range(min=20, max=200)),
        # Benachrichtigungen
        vol.Optional("notify_targets"): vol.All([vol.All(str, vol.Match(r"^[a-z0-9_]+$"))], vol.Length(max=10)),
        vol.Optional("notify_window"): bool,
        vol.Optional("notify_window_min"): vol.All(vol.Coerce(int), vol.Range(min=5, max=720)),
        vol.Optional("notify_offline"): bool,
        vol.Optional("notify_offline_min"): vol.All(vol.Coerce(int), vol.Range(min=1, max=720)),
        vol.Optional("notify_frost"): bool,
        vol.Optional("notify_battery"): bool,
        vol.Optional("notify_quiet"): bool,
        vol.Optional("notify_quiet_from"): _hm,
        vol.Optional("notify_quiet_to"): _hm,
        vol.Optional("battery_low"): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
        # Vorheizen nach Wetter, Feiertage, Lüften
        vol.Optional("preheat_weather"): bool,
        vol.Optional("workday_entity"): _opt(vol.All(str, vol.Match(r"^binary_sensor\.[a-z0-9_]+$"))),
        vol.Optional("workday_as"): vol.All(vol.Coerce(int), vol.In([5, 6])),
        vol.Optional("vent_rh"): vol.All(vol.Coerce(int), vol.Range(min=0, max=95)),
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


def _settings(hass: HomeAssistant) -> dict:
    """Alle Einstellungen, wie das Panel sie sieht: zentral (Kern) und Heizwerk."""
    haus, ctl = _haus(hass), _ctl(hass)
    return {**(haus.settings if haus else {}), **(ctl.settings if ctl else {})}


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
            "defaults": TYPE_DEFAULTS,
            "modes": MODES,
            "is_admin": _may_edit(hass, connection),
            "user_admin": connection.user.is_admin,
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
@require_editor
@websocket_api.async_response
async def ws_settings_save(hass: HomeAssistant, connection, msg) -> None:
    ctl = _ctl(hass)
    if ctl is None:
        return _not_ready(connection, msg)
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
    heat = {k: v for k, v in settings.items() if k not in HOUSE_KEYS}
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


@websocket_api.websocket_command({vol.Required("type"): "hauswerk/notify/test"})
@require_editor
@websocket_api.async_response
async def ws_notify_test(hass: HomeAssistant, connection, msg) -> None:
    """Testnachricht an die gewählten Apps."""
    haus = _haus(hass)
    if haus is None:
        return _not_ready(connection, msg)
    if not haus.settings.get("notify_targets"):
        connection.send_error(msg["id"], "no_targets", "Erst eine App auswählen und speichern")
        return
    await haus.async_test_notify(by=_who(connection))
    connection.send_result(msg["id"])


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
    ws_report,
    ws_preheat_reset,
    ws_plan_save,
    ws_plan_delete,
    ws_calendar_import,
    ws_notify_test,
    ws_log_get,
    ws_log_subscribe,
)


@callback
def async_register(hass: HomeAssistant) -> None:
    key = f"{DOMAIN}_ws_registered"
    if hass.data.get(key):
        return
    for command in COMMANDS:
        websocket_api.async_register_command(hass, command)
    hass.data[key] = True
