"""Konstanten für Heizwerk."""
from __future__ import annotations

DOMAIN = "heizwerk"
NAME = "Heizwerk"

STORAGE_KEY = f"{DOMAIN}.data"
STORAGE_VERSION = 1

PANEL_URL = "heizwerk"
PANEL_COMPONENT = "heizwerk-panel"
PANEL_ICON = "mdi:radiator"
STATIC_URL = "/heizwerk_static"

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
}

CALENDAR_REFRESH = 300  # Sekunden zwischen zwei Abfragen des Urlaubskalenders

WINDOW_OPEN_STATES = {"on", "open", "true", "opening"}
