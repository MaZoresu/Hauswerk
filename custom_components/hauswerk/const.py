"""Konstanten für Hauswerk."""
from __future__ import annotations

DOMAIN = "hauswerk"
NAME = "Hauswerk"

# Module von Hauswerk. Jedes Modul liegt unter hass.data[DOMAIN][<modul>]
# und hat seinen eigenen Speicher.
MODULE_HEATING = "heizen"

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
    "proximity_sensors": "Entfernungs-Sensoren", "proximity_km": "Heimweg-Grenze",
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
}

PANEL_URL = "hauswerk"
PANEL_COMPONENT = "hauswerk-panel"
PANEL_ICON = "mdi:home-automation"
STATIC_URL = "/hauswerk_static"

SIGNAL_UPDATE = f"{DOMAIN}_update"
SIGNAL_ROOMS = f"{DOMAIN}_rooms"

PLATFORMS = ["sensor", "switch"]

STATS_DAYS = 60

DEFAULT_SETTINGS = {
    "frost_temp": 7.0,
    "away_temp": 17.0,
    "away_delay": 10,          # Minuten, bis "abwesend" greift
    "vacation_temp": 15.0,
    "vacation": False,
    "vacation_from": None,     # "YYYY-MM-DD"
    "vacation_to": None,
    "persons": [],             # person.* / device_tracker.*
    "presence_force": None,    # None = automatisch, "away" = von Hand abwesend
    "arrive_delay": 0,         # Minuten nach dem Heimkommen, bis wieder normal geheizt wird
    "guest": False,            # Gästemodus: nie abwesend
    "party": False,            # Party: alle Räume auf Komfort
    "proximity_sensors": [],   # Entfernungs-Sensoren (z. B. aus der Proximity-Integration)
    "proximity_km": 0,         # Unterwegs nach Hause ab dieser Entfernung = schon zu Hause (0 = aus)
    "summer_mode": "off",      # off | auto | on
    "outside_sensor": None,    # Außentemperatur für die Sommerpause
    "summer_temp": 16.0,       # Ab dieser Außentemperatur Sommerpause
    "summer_action": "off",    # off = Thermostate aus | frost = Frostschutz
    "liming": False,           # Entkalkungsschutz einmal pro Woche
    "liming_day": 0,           # 0 = Montag
    "liming_time": "10:00",
    "liming_minutes": 5,
    "liming_winter": False,    # auch während der Heizperiode entkalken
    "boost_minutes": 30,
    "away_mode": "temp",       # temp = höchstens away_temp | offset = um away_offset absenken
    "away_offset": 2.0,        # K
    "away_action": "lower",    # lower = absenken | off = Thermostate aus, solange niemand da ist
    "long_away_days": 0,       # nach so vielen Tagen ohne Personen auf Frostschutz (0 = nie)
    "eco_force": False,        # alle Räume auf Eco erzwingen
    "season_entity": None,     # Heizperiode aus einer Entität (an = heizen) bei summer_mode "entity"
    "summer_fallback": "keep", # Außensensor fehlt: keep | heat | summer
    "calibration_interval": 10,  # Minuten zwischen zwei Kalibrierungen
    # Urlaub: Quelle für den automatischen Urlaub (der Schalter "vacation" gilt immer)
    "vacation_source": "period",  # off | period | calendar
    "vacation_calendar": None,    # calendar.* bei vacation_source "calendar"
    "vacation_keywords": "Urlaub, Ferien",  # Termine mit diesen Wörtern im Titel zählen
    # Vorheizen für alle Räume (je Raum änderbar)
    "preheat_mode": "fixed",      # smart = lernend | fixed = feste Zeit | off = aus
    "lead_radiator": 15,          # Minuten bei fester Zeit, Heizkörper
    "lead_floor": 120,            # Minuten bei fester Zeit, Flächenheizung
    "allow_users": False,         # auch Nicht-Admins dürfen Einstellungen, Räume und Pläne ändern
    "weather_entity": None,       # weather.* für das Banner (leer = erste gefundene)
    "start_widgets": None,        # Widgets der Startseite (None = Grundauswahl im Panel)
    # Darstellung des Panels (für alle Benutzer; die Größe merkt sich jedes Gerät selbst)
    "look_theme": "auto",         # auto = wie Home Assistant | light | dark
    "look_accent": None,          # "#rrggbb" oder None = Türkis
    "look_background": "pattern", # pattern = Muster | daytime = Kopfzeile nach Tageszeit | plain = schlicht
    "look_header_weather": True,  # Außentemperatur und Wetter oben rechts
    "look_header_clock": False,   # Uhrzeit oben rechts (z. B. für Wand-Tablets)
    # Wetter-Hinweise
    "cold_snap_temp": 0.0,        # Kälteeinbruch: Tiefstwert der nächsten 3 Tage darunter
    "storm_kmh": 70.0,            # Sturm: Böen der nächsten 24 Stunden ab dieser Stärke
}

CALENDAR_REFRESH = 300  # Sekunden zwischen zwei Abfragen des Urlaubskalenders

WINDOW_OPEN_STATES = {"on", "open", "true", "opening"}
