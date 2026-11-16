"""Konstanten für Hauswerk."""
from __future__ import annotations

DOMAIN = "hauswerk"
NAME = "Hauswerk"

# Module von Hauswerk. Jedes Modul liegt unter hass.data[DOMAIN][<modul>]
# und hat seinen eigenen Speicher.
MODULE_HEATING = "heizen"
# Hauswerk-Kern: zentrale Einstellungen und Hauszustände (Anwesenheit, Urlaub, Wetter)
MODULE_HOUSE = "haus"
HOUSE_STORAGE_KEY = f"{DOMAIN}.{MODULE_HOUSE}"
# Modul Rollwerk (Rollläden): hass.data[DOMAIN][MODULE_SHUTTER], Speicher hauswerk.rollwerk
MODULE_SHUTTER = "rollwerk"
SHUTTER_STORAGE_KEY = f"{DOMAIN}.{MODULE_SHUTTER}"

STORAGE_KEY = f"{DOMAIN}.{MODULE_HEATING}"
STORAGE_VERSION = 1
# Speicher der früheren Einzel-Integration „Heizwerk“, wird beim ersten Start übernommen
LEGACY_STORAGE_KEY = "heizwerk.data"

# Protokoll (für alle Module): hass.data[DOMAIN][MODULE_LOG]
MODULE_LOG = "log"
LOG_STORAGE_KEY = f"{DOMAIN}.protokoll"
LOG_DAYS = 14
LOG_MAX = 6000

# Namen der Einstellungen fürs Protokoll
SETTING_LABELS = {
    "persons": "Personen", "away_delay": "Abwesend nach", "arrive_delay": "Zu Hause nach",
    "proximity_sensors": "Entfernungs-Sensoren", "proximity_m": "Heimweg-Grenze", "home_zone": "Wohnung (Zone)",
    "presence_force": "Anwesenheit von Hand", "guest": "Gäste", "party": "Party", "eco_force": "Eco erzwingen",
    "vacation": "Urlaub", "vacation_source": "Urlaub-Quelle", "vacation_from": "Urlaub von", "vacation_to": "Urlaub bis",
    "vacation_calendar": "Urlaubskalender", "vacation_keywords": "Urlaub-Stichworte", "vacation_temp": "Urlaubstemperatur",
    "away_temp": "Abwesend-Temperatur", "away_mode": "Abwesend-Art", "away_offset": "Abwesend-Absenkung",
    "away_action": "Abwesend-Verhalten", "long_away_days": "Lange Abwesenheit",
    "summer_mode": "Sommerpause", "summer_temp": "Heizgrenze", "summer_action": "Sommerpause-Verhalten",
    "summer_fallback": "Ersatz bei Sensorausfall", "season_entity": "Heizperiode-Entität",
    "outside_sensor": "Außentemperatur", "weather_entity": "Wetterquelle",
    "cold_snap_temp": "Kälteeinbruch", "storm_kmh": "Sturm",
    "frost_temp": "Frostschutz", "boost_minutes": "Boost-Dauer", "liming": "Entkalken", "liming_day": "Entkalken",
    "liming_time": "Entkalken", "liming_minutes": "Entkalken", "liming_winter": "Entkalken",
    "preheat_mode": "Vorheizen", "lead_radiator": "Vorheizen", "lead_floor": "Vorheizen",
    "calibration_interval": "Kalibrierung", "allow_users": "Berechtigungen", "start_widgets": "Widgets",
    "look_theme": "Darstellung", "look_accent": "Darstellung", "look_background": "Darstellung",
    "look_header_weather": "Darstellung", "look_header_clock": "Darstellung",
    "notify_targets": "Benachrichtigungen an", "notify_window": "Benachrichtigungen", "notify_window_min": "Benachrichtigungen",
    "notify_offline": "Benachrichtigungen", "notify_offline_min": "Benachrichtigungen", "notify_frost": "Benachrichtigungen",
    "notify_battery": "Benachrichtigungen", "notify_quiet": "Ruhezeit", "notify_quiet_from": "Ruhezeit", "notify_quiet_to": "Ruhezeit",
    "battery_low": "Batterie-Warnung", "preheat_weather": "Vorheizen nach Wetter", "workday_entity": "Arbeitstag-Sensor",
    "workday_as": "Feiertage wie", "vent_rh": "Lüften-Hinweis", "sun_entity": "Sonne",
    "notify_ha": "Mitteilung in Home Assistant", "notify_cold": "Benachrichtigungen",
    "demand_entity": "Wärmeanforderung", "demand_action": "Wärmeanforderung", "demand_low": "Wärmeanforderung",
    "demand_valve": "Wärmeanforderung", "rw_covers": "Rollwerk: Rollläden", "rw_storm": "Rollwerk: Sturmschutz", "rw_wind_entity": "Rollwerk: Sturmschutz", "rw_recovery": "Rollwerk: Nach Neustart", "demand_hold": "Wärmeanforderung", "demand_preheat": "Wärmeanforderung",
    "radio_entities": "Funk-Auslastung", "radio_limit": "Funk-Grenze", "pair_mode": "Kopplung",
}

PANEL_URL = "hauswerk"
PANEL_COMPONENT = "hauswerk-panel"
PANEL_ICON = "mdi:home-automation"
STATIC_URL = "/hauswerk_static"

SIGNAL_UPDATE = f"{DOMAIN}_update"
SIGNAL_ROOMS = f"{DOMAIN}_rooms"

PLATFORMS = ["sensor", "switch"]

STATS_DAYS = 60

# Zentrale Einstellungen von Hauswerk (gelten für alle Module, Speicher hauswerk.haus)
HOUSE_DEFAULTS = {
    # Anwesenheit
    "persons": [],             # person.* / device_tracker.*
    "home_zone": "zone.home",  # Zone, in der eine Person als zu Hause gilt
    "away_delay": 10,          # Minuten, bis "abwesend" greift
    "arrive_delay": 0,         # Minuten nach dem Heimkommen, bis wieder "zu Hause" gilt
    "presence_force": None,    # None = automatisch, "away" = von Hand abwesend
    "guest": False,            # Gästemodus: nie abwesend
    "proximity_sensors": [],   # Entfernungs-Sensoren (z. B. aus der Integration „Nähe“)
    "proximity_m": 0,          # Heimweg: näher als so viele Meter = schon zu Hause (0 = aus)
    # Feiertage: Sensor „Arbeitstag“ (workday); aus an einem Werktag = Zeitpläne wie an workday_as
    "workday_entity": None,       # binary_sensor.* der Integration „Arbeitstag“
    "workday_as": 6,              # 5 = wie Samstag, 6 = wie Sonntag
    # Urlaub: der Schalter "vacation" gilt immer, dazu automatisch per Zeitraum oder Kalender
    "vacation": False,
    "vacation_source": "period",  # off | period | calendar
    "vacation_from": None,        # "YYYY-MM-DD"
    "vacation_to": None,
    "vacation_calendar": None,    # calendar.* bei vacation_source "calendar"
    "vacation_keywords": "Urlaub, Ferien",  # Termine mit diesen Wörtern im Titel zählen
    # Wetter
    "weather_entity": None,       # weather.* (leer = erste gefundene)
    "outside_sensor": None,       # eigene Außentemperatur statt Wetterdienst
    "cold_snap_temp": 0.0,        # Kälteeinbruch: Tiefstwert der nächsten 3 Tage darunter
    "storm_kmh": 70.0,            # Sturm: Böen der nächsten 24 Stunden ab dieser Stärke
    "sun_entity": "sun.sun",      # Sonnenstand (Darstellung nach Tageszeit, später Rollläden)
    # Startseite, Darstellung, Berechtigungen
    "start_widgets": None,        # Widgets der Startseite (None = Grundauswahl im Panel)
    "look_theme": "auto",         # auto = wie Home Assistant | light | dark
    "look_accent": None,          # "#rrggbb" oder None = Türkis
    "look_background": "pattern", # pattern = Muster | daytime = Kopfzeile nach Tageszeit | plain = schlicht
    "look_header_weather": True,  # Außentemperatur und Wetter oben rechts
    "look_header_clock": False,   # Uhrzeit oben rechts (z. B. für Wand-Tablets)
    "allow_users": False,         # auch Nicht-Admins dürfen Einstellungen, Räume und Pläne ändern
    # Benachrichtigungen aufs Handy (Home-Assistant-App: notify.mobile_app_…)
    # Art je Anlass: off = aus | log = nur Protokoll | normal = Push | important = wichtig (auch in der Ruhezeit,
    # durchbricht „Nicht stören“ auf dem iPhone, hohe Priorität auf Android)
    "notify_targets": [],         # Dienste ohne "notify.", z. B. "mobile_app_pixel_8"
    "notify_window": "normal",    # Fenster lange offen
    "notify_window_min": 30,      # … ab so vielen Minuten
    "notify_offline": "normal",   # Thermostat nicht erreichbar
    "notify_offline_min": 15,     # … seit so vielen Minuten
    "notify_frost": "normal",     # Frost erwartet (Grenze: cold_snap_temp)
    "notify_battery": "normal",   # Batterie schwach
    "notify_cold": "normal",      # Heizkörper bleibt kalt trotz offenem Ventil
    "notify_ha": False,           # zusätzlich als Mitteilung in Home Assistant (Glocke in der Seitenleiste)
    "notify_quiet": True,         # Ruhezeit: Nachrichten erst danach senden
    "notify_quiet_from": "22:00",
    "notify_quiet_to": "07:00",
    "battery_low": 20,            # Batterie-Warnung unter so viel Prozent
    # Funk (z. B. Homematic Duty Cycle): Sensoren (leer = automatisch) und Grenze, ab der gedrosselt wird
    "radio_entities": [],
    "radio_limit": 70,
}
HOUSE_KEYS = frozenset(HOUSE_DEFAULTS)

# Einstellungen des Moduls Heizwerk (Speicher hauswerk.heizen)
HEAT_DEFAULTS = {
    "frost_temp": 7.0,
    "away_action": "lower",    # lower = absenken | off = Thermostate aus, solange niemand da ist
    "away_mode": "temp",       # temp = höchstens away_temp | offset = um away_offset absenken
    "away_temp": 17.0,
    "away_offset": 2.0,        # °C
    "long_away_days": 0,       # nach so vielen Tagen ohne Personen auf Frostschutz (0 = nie)
    "vacation_temp": 15.0,
    "party": False,            # Party: alle Räume auf Komfort
    "eco_force": False,        # alle Räume auf Eco erzwingen
    "summer_mode": "off",      # off | auto | on | entity
    "summer_temp": 16.0,       # Heizgrenze: ab dieser Außentemperatur Sommerpause
    "summer_action": "off",    # off = Thermostate aus | frost = Frostschutz
    "summer_fallback": "keep", # Außensensor fehlt: keep | heat | summer
    "season_entity": None,     # Heizperiode aus einer Entität (an = heizen) bei summer_mode "entity"
    "liming": False,           # Entkalkungsschutz einmal pro Woche
    "liming_day": 0,           # 0 = Montag
    "liming_time": "10:00",
    "liming_minutes": 5,
    "liming_winter": False,    # auch während der Heizperiode entkalken
    "boost_minutes": 30,
    "calibration_interval": 10,  # Minuten zwischen zwei Kalibrierungen
    # Vorheizen für alle Räume (je Raum änderbar)
    "preheat_mode": "fixed",      # smart = lernend | fixed = feste Zeit | off = aus
    "lead_radiator": 15,          # Minuten bei fester Zeit, Heizkörper
    "lead_floor": 120,            # Minuten bei fester Zeit, Flächenheizung
    "preheat_weather": False,     # Vorlaufzeit nach Außentemperatur anpassen (kälter = früher)
    # Lüften: Hinweis, wenn drinnen ab dieser Luftfeuchte und draußen trockenere Luft (0 = aus)
    "vent_rh": 65,
    # Wärmeanforderung an den Wärmeerzeuger (z. B. Zone der Vaillant-Anlage); leer = aus
    "demand_entity": None,        # climate.* des Wärmeerzeugers
    "demand_action": "lower",     # lower = Soll absenken | off = Zone ausschalten, solange kein Raum Wärme braucht
    "demand_low": 17.0,           # °C bei „lower“
    "demand_valve": 15,           # ab dieser Ventilöffnung (%) braucht ein Raum Wärme
    "demand_hold": 20,            # Minuten ohne Bedarf, bis abgesenkt wird
    "demand_preheat": 0.0,        # beim Vorheizen das Soll des Wärmeerzeugers um so viel °C anheben (0 = nein)
}

# Alle Einstellungen zusammen (so sieht sie das Panel)
DEFAULT_SETTINGS = {**HOUSE_DEFAULTS, **HEAT_DEFAULTS}

FORECAST_REFRESH = 1800  # Sekunden zwischen zwei Abfragen der Wettervorhersage (Frost-Nachricht)
NOTIFY_REPEAT = 12 * 3600  # dieselbe Nachricht frühestens nach so vielen Sekunden erneut

CALENDAR_REFRESH = 300  # Sekunden zwischen zwei Abfragen des Urlaubskalenders

WINDOW_OPEN_STATES = {"on", "open", "true", "opening"}
