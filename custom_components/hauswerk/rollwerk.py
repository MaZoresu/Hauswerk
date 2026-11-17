"""Hauswerk-Modul Rollwerk: Rollläden nach dem Vorbild der „Cover Control Automation“ (CCA).

Einstellungen stehen in **Profilen** (wie eine CCA-Instanz): Funktionen, Positionen, Zeitsteuerung,
Helligkeit, Sonnenhöhe, Lüften, Beschattung, Bewohner, manuelle Übersteuerung, Verzögerung, Erzwingen und
Verhalten. Jeder Rollladen nutzt ein Profil und hat eigene Fensterkontakte (offen/gekippt).

Rollwerk fährt nur bei einem Wechsel (Öffnen, Schließen, Beschattung an/aus, Lüften, Sturm …). Verstellt
jemand einen Rollladen von Hand, gilt das als manuelle Übersteuerung: je nach Profil bleibt er so, bis sie
zurückgesetzt wird, oder der nächste automatische Wechsel übernimmt wieder.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
import random
from typing import Any

from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MODULE_HEATING, SHUTTER_STORAGE_KEY, WINDOW_OPEN_STATES
from .core import Haus, async_calendar_events, parse_when
from .log import Protokoll, log_settings
from .logic import FACADES, parse_hm, shade_conditions, shade_wanted

_LOGGER = logging.getLogger(__name__)

BAD = {"unavailable", "unknown", None}
STARTUP_GRACE = 180  # Sekunden nach dem Start: Wartezeiten gelten noch nicht, es wird nur der Stand übernommen
DAY_KEYS = ("opened_on", "closed_on", "stage1_on", "shaded_on", "shade_ended_on", "auto_opened_on", "auto_closed_on", "shading", "day")
STORM_RELEASE = 15 * 60  # Sekunden unter 80 % der Sturmgrenze, bis der Sturmschutz endet

# Einstellungen für alle Rollläden (rw_…)
RW_DEFAULTS: dict[str, Any] = {
    "rw_covers": [],          # Rollläden, die Rollwerk fährt
    "rw_storm": True,         # Sturmschutz: hochfahren ab Sturmgrenze (Hauswerk › Wetter)
    "rw_wind_entity": None,   # Böen-Sensor (leer = Wetterdienst)
    "rw_recovery": "never",   # nach Neustart nachholen: never | outage (nur verpasste Wechsel) | always
}
RW_KEYS = frozenset(RW_DEFAULTS)

# Profil: (Standardwert, Art). Arten: bool, num, time, text, entity, list, choice
PROFILE_SPEC: dict[str, tuple[Any, str]] = {
    "name": ("Standard", "text"),
    # Funktionen (auto_options) und Verknüpfung Helligkeit/Sonne
    "features": (["up", "down", "time", "ventilate"], "list"),  # up, down, time, brightness, sun, ventilate, shading
    "time_mode": ("times", "choice"),                       # times | calendar
    "bs_operator": ("or", "choice"),                        # or | and
    "behavior": ([], "list"),                               # Verhalten (individual_config)
    # Positionen
    "pos_open": (100, "num"),
    "pos_close": (0, "num"),
    "pos_ventilate": (30, "num"),
    "pos_lockout": (None, "num"),                           # Fenster ganz offen (leer = nicht herunterfahren)
    "pos_shading": (25, "num"),
    "pos_shading_alt": (None, "num"),
    "shading_alt_entity": (None, "entity"),                 # an = andere Beschattungs-Stellung
    "tolerance": (0, "num"),
    "drive_time": (90, "num"),                              # Sekunden Fahrzeit (eigene Fahrten ≠ von Hand)
    # Zeitsteuerung (früh/spät, Werktag/frei)
    "up_early": ("06:00", "time"), "up_early_we": ("07:00", "time"),
    "up_late": ("08:00", "time"), "up_late_we": ("08:00", "time"),
    "down_early": ("16:00", "time"), "down_early_we": ("16:00", "time"),
    "down_late": ("22:00", "time"), "down_late_we": ("22:00", "time"),
    "workday_tomorrow": (None, "entity"),
    # Abends in zwei Stufen: Stufe 1 (halb) bei Sonnenrichtung/-höhe/Uhrzeit, Stufe 2 (ganz zu) zur spätesten Zeit
    "close_stage1": (False, "bool"),
    "stage1_trigger": ("azimuth", "choice"),   # azimuth | elevation | time
    "stage1_azimuth": (250, "num"),
    "stage1_elevation": (10, "num"),
    "stage1_time": ("18:00", "time"),
    "pos_stage1": (50, "num"),
    "close_stage2": (True, "bool"),                   # Arbeitstag morgen (nur fürs Schließen)
    "calendar": (None, "entity"),
    "cal_open": ("Rollladen auf", "text"),
    "cal_close": ("Rollladen zu", "text"),
    # Helligkeit
    "brightness_sensor": (None, "entity"),
    "brightness_up": (0, "num"), "brightness_down": (0, "num"), "brightness_hyst": (0, "num"),
    "brightness_duration": (30, "num"),                     # Sekunden
    # Sonnenhöhe
    "sun_up": (0, "num"), "sun_down": (0, "num"), "sun_duration": (30, "num"),
    # Lüften
    "vent_options": ([], "list"),
    "lockout_tilted": ([], "list"),                         # lockout_tilted_closing/_shading_start/_shading_end
    # Beschattung
    "shade_start_and": (["azimuth", "elevation", "brightness", "temp1", "temp2"], "list"),
    "shade_start_or": ([], "list"),
    "shade_end_and": ([], "list"),
    "shade_end_or": (["azimuth", "elevation", "brightness", "temp1", "temp2"], "list"),
    "azimuth_start": (95, "num"), "azimuth_end": (265, "num"),
    "elevation_min": (25, "num"), "elevation_max": (90, "num"),
    "shade_brightness_sensor": (None, "entity"),
    "shade_bright_start": (35000, "num"), "shade_bright_end": (25000, "num"),
    "temp1_sensor": (None, "entity"), "temp1_min": (18, "num"), "temp1_hyst": (0.2, "num"),
    "temp2_sensor": (None, "entity"), "temp2_min": (18, "num"), "temp2_hyst": (0.2, "num"),
    "forecast_entity": (None, "entity"), "forecast_temp": (None, "num"),
    "weather_conditions": ([], "list"),
    "shade_custom": (None, "entity"),
    "shade_wait_start": (300, "num"), "shade_wait_end": (300, "num"),
    "shade_end_immediate": (False, "bool"),
    # Bewohner
    "resident_sensor": (None, "entity"),
    "resident_config": ([], "list"),   # opening, closing, allow_shading, allow_opening, allow_ventilation
    # Anwesenheit und Urlaub kommen aus Hauswerk › Anwesenheit / Urlaub
    "away_mode": ("normal", "choice"),  # normal | closed (tagsüber zu) | shade (tagsüber Beschattungsstellung)
    "vacation_random": (0, "num"),      # Urlaub: Öffnen/Schließen zufällig bis zu X Minuten später
    "window_dir": (None, "num"),        # Himmelsrichtung des Fensters (Kompass), daraus Richtung von/bis
    # Manuelle Übersteuerung
    "manual_block": ([], "list"),      # opening, closing, ventilation, shading
    "manual_reset": ([], "list"),      # fixed, timeout, in_position
    "manual_recover": (False, "bool"),
    "reset_time": ("00:01", "time"), "reset_timeout": (5, "num"), "reset_position": (100, "num"),
    # Verzögerung (Sekunden)
    "delay_fix": (0, "num"), "delay_random": (5, "num"),
    # Erzwingen
    "force_pause": (None, "entity"), "force_up": (None, "entity"), "force_down": (None, "entity"),
    "force_ventilate": (None, "entity"), "force_shading": (None, "entity"),
}
PROFILE_DEFAULTS = {k: (list(v) if isinstance(v, list) else v) for k, (v, _kind) in PROFILE_SPEC.items()}
# Für das Protokoll: was im Profil geändert wurde (Bezeichnung, Einheit)
PROFILE_LABELS: dict[str, tuple[str, str]] = {
    "name": ("Name", ""), "features": ("Funktionen", ""), "time_mode": ("Zeiten aus", ""),
    "pos_open": ("Offen", " %"), "pos_close": ("Geschlossen", " %"), "pos_ventilate": ("Lüften", " %"),
    "pos_lockout": ("Tür offen höchstens", " %"), "pos_shading": ("Beschattung", " %"), "pos_shading_alt": ("Beschattung anders", " %"),
    "up_early": ("Öffnen frühestens", ""), "up_late": ("Öffnen spätestens", ""), "up_early_we": ("Öffnen frühestens (frei)", ""),
    "up_late_we": ("Öffnen spätestens (frei)", ""), "down_early": ("Schließen frühestens", ""), "down_late": ("Schließen spätestens", ""),
    "down_early_we": ("Schließen frühestens (frei)", ""), "down_late_we": ("Schließen spätestens (frei)", ""),
    "close_stage1": ("Zwei Stufen", ""), "stage1_trigger": ("Stufe 1 nach", ""), "stage1_azimuth": ("Stufe 1 ab Richtung", "°"),
    "stage1_elevation": ("Stufe 1 unter Sonnenhöhe", "°"), "stage1_time": ("Stufe 1 um", ""), "pos_stage1": ("Stufe 1", " %"),
    "close_stage2": ("Stufe 2", ""), "sun_up": ("Öffnen ab Sonnenhöhe", "°"), "sun_down": ("Schließen ab Sonnenhöhe", "°"),
    "window_dir": ("Fensterrichtung", "°"), "azimuth_start": ("Sonne von", "°"), "azimuth_end": ("Sonne bis", "°"),
    "elevation_min": ("Sonnenhöhe mind.", "°"), "elevation_max": ("Sonnenhöhe höchstens", "°"), "temp2_min": ("Beschatten ab außen", " °C"),
    "temp1_min": ("Beschatten ab innen", " °C"), "shade_wait_start": ("Warten vor Beschattung", " s"), "shade_wait_end": ("Warten vor Ende", " s"),
    "away_mode": ("Niemand zu Hause", ""), "vacation_random": ("Urlaub verschieben", " Min."), "manual_block": ("Hand-Stellung bleibt bei", ""),
    "resident_sensor": ("Schlaf-Schalter", ""), "delay_random": ("Verzögerung zufällig", " s"),
    "bs_operator": ("Helligkeit/Sonne verknüpft mit", ""), "behavior": ("Verhalten", ""), "shading_alt_entity": ("Schalter andere Beschattung", ""),
    "tolerance": ("Toleranz", " %"), "drive_time": ("Fahrzeit", " s"), "workday_tomorrow": ("Arbeitstag-Sensor", ""),
    "calendar": ("Kalender", ""), "cal_open": ("Kalender-Termin öffnen", ""), "cal_close": ("Kalender-Termin schließen", ""),
    "brightness_sensor": ("Helligkeitssensor", ""), "brightness_up": ("Öffnen ab Helligkeit", " lx"), "brightness_down": ("Schließen unter Helligkeit", " lx"),
    "brightness_hyst": ("Helligkeit Abstand", " lx"), "brightness_duration": ("Helligkeit Dauer", " s"), "sun_duration": ("Sonnenhöhe Dauer", " s"),
    "vent_options": ("Lüften", ""), "lockout_tilted": ("Aussperrschutz gekippt", ""),
    "shade_start_and": ("Beschattung beginnt (alle)", ""), "shade_start_or": ("Beschattung beginnt (eins)", ""),
    "shade_end_and": ("Beschattung endet (alle)", ""), "shade_end_or": ("Beschattung endet (eins)", ""),
    "shade_brightness_sensor": ("Beschattung Helligkeitssensor", ""), "shade_bright_start": ("Beschatten ab Helligkeit", " lx"),
    "shade_bright_end": ("Beschattung endet unter", " lx"), "temp1_sensor": ("Temperatur innen", ""), "temp1_hyst": ("Temp. innen Abstand", " °C"),
    "temp2_sensor": ("Temperatur außen", ""), "temp2_hyst": ("Temp. außen Abstand", " °C"), "forecast_entity": ("Wettervorhersage", ""),
    "forecast_temp": ("Beschatten ab Vorhersage", " °C"), "weather_conditions": ("Wetterlage", ""), "shade_custom": ("Eigene Bedingung", ""),
    "shade_end_immediate": ("Beschattung sofort beenden", ""), "resident_config": ("Bewohner", ""), "manual_reset": ("Zurücksetzen", ""),
    "manual_recover": ("Nach Hand-Stellung nachholen", ""), "reset_time": ("Zurücksetzen um", ""), "reset_timeout": ("Zurücksetzen nach", " Std."),
    "reset_position": ("Zurücksetzen in Stellung", " %"), "delay_fix": ("Verzögerung fest", " s"),
    "force_pause": ("Pause-Schalter", ""), "force_up": ("Öffnen erzwingen", ""), "force_down": ("Schließen erzwingen", ""),
    "force_ventilate": ("Lüften erzwingen", ""), "force_shading": ("Beschattung erzwingen", ""),
}
# Einträge in Listen-Einstellungen (Kurzform fürs Protokoll)
LIST_ITEM_LABEL: dict[str, str] = {
    "up": "Morgens öffnen", "down": "Abends schließen", "time": "Zeitsteuerung", "brightness": "Helligkeit", "sun": "Sonnenhöhe",
    "ventilate": "Lüften", "shading": "Beschattung",
    "azimuth": "Richtung", "elevation": "Sonnenhöhe", "temp1": "Temp. innen", "temp2": "Temp. außen", "forecast_temp": "Vorhersage",
    "forecast_weather": "Wetterlage", "custom": "Eigene",
    "sunny": "Sonnig", "partlycloudy": "Teils bewölkt", "cloudy": "Bewölkt", "fog": "Nebel", "rainy": "Regen", "windy": "Windig", "exceptional": "Extrem",
    "ventilation_start_no_delay": "ohne Verzögerung beim Kippen", "ventilation_if_lower_enabled": "auch herunter auf Lüftungsstellung",
    "ventilation_after_shading_end": "nach Beschattung auf Lüftungsstellung", "shading_over_ventilation": "Beschattung vor Lüften",
    "lockout_tilted_closing": "beim Schließen", "lockout_tilted_shading_start": "bei Beschattungsbeginn", "lockout_tilted_shading_end": "bei Beschattungsende",
    "closing": "Schließen", "opening": "Öffnen", "allow_shading": "Beschattung im Schlaf", "allow_opening": "Öffnen im Schlaf", "ventilation": "Lüften",
    "fixed": "feste Uhrzeit", "timeout": "nach einiger Zeit", "in_position": "in Stellung",
    "prevent_higher_position_closing": "abends nicht höher fahren", "prevent_lowering_when_closing_if_shaded": "abends in Beschattungsstellung bleiben",
    "prevent_shading_end_if_closed": "Beschattung nicht beenden, wenn zu", "prevent_opening_after_shading_end": "nach Beschattung nicht öffnen",
    "prevent_opening_after_ventilation_end": "nach Lüften nicht öffnen", "prevent_opening_multiple_times": "nur einmal am Tag öffnen",
    "prevent_closing_multiple_times": "nur einmal am Tag schließen", "prevent_shading_multiple_times": "nur einmal am Tag beschatten",
}
CHOICE_LABEL = {"azimuth": "Sonnenrichtung", "elevation": "Sonnenhöhe", "time": "Uhrzeit", "times": "Uhrzeiten", "calendar": "Kalender",
                "normal": "wie immer", "closed": "tagsüber zu", "shade": "beschattet", "or": "oder", "and": "und"}


def _fmt_value(value: Any, unit: str) -> str:
    if value is None or value == "" or value == []:
        return "–"
    if isinstance(value, bool):
        return "an" if value else "aus"
    if isinstance(value, list):
        return f"{len(value)} gewählt"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, str):
        return CHOICE_LABEL.get(value, value)
    return f"{value:g}{unit}" if isinstance(value, float) else f"{value}{unit}"


def list_changes(label: str, old: Any, new: Any) -> str:
    """„Funktionen: + Beschattung, − Lüften“ statt nur der Anzahl."""
    a, b = list(old or []), list(new or [])
    added = [LIST_ITEM_LABEL.get(x, str(x)) for x in b if x not in a]
    removed = [LIST_ITEM_LABEL.get(x, str(x)) for x in a if x not in b]
    parts = [f"+ {x}" for x in added] + [f"− {x}" for x in removed]
    return f"{label}: {', '.join(parts) if parts else 'Reihenfolge'}"


def profile_changes(old: dict, new: dict, name: Callable[[str], str] | None = None) -> str:
    """Kurzer Text, was sich geändert hat: „Beschatten ab außen 22 → 24 °C, Funktionen: − Lüften“."""
    parts = []
    for key, (_default, kind) in PROFILE_SPEC.items():
        a, b = old.get(key, PROFILE_DEFAULTS.get(key)), new.get(key, PROFILE_DEFAULTS.get(key))
        if a == b or (isinstance(a, (int, float)) and isinstance(b, (int, float)) and float(a) == float(b)):
            continue
        label, unit = PROFILE_LABELS.get(key, (key, ""))
        if kind == "list" or isinstance(a, list) or isinstance(b, list):
            parts.append(list_changes(label, a, b))
        elif kind == "entity" and name:
            parts.append(f"{label} {name(a) if a else '–'} → {name(b) if b else '–'}")
        else:
            parts.append(f"{label} {_fmt_value(a, unit)} → {_fmt_value(b, unit)}")
    return ", ".join(parts[:8]) + (f" (+{len(parts) - 8} weitere)" if len(parts) > 8 else "")


CATEGORY_LABEL = {"open": "Öffnen", "close": "Schließen", "shading": "Beschattung", "ventilation": "Lüften",
                  "storm": "Sturmschutz", "force": "Erzwungen", "resident": "Bewohner"}


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _hm(value: Any, default: str) -> int:
    try:
        return parse_hm(value or default)
    except (TypeError, ValueError):
        return parse_hm(default)


class Rollwerk:
    """Modul Rollwerk: Profile, Rollladen-Zuordnung und Steuerung."""

    def __init__(self, hass: HomeAssistant, log: Protokoll, haus: Haus) -> None:
        self.hass = hass
        self.log = log
        self.haus = haus
        self._store: Store = Store(hass, 1, SHUTTER_STORAGE_KEY)
        self.settings: dict[str, Any] = dict(RW_DEFAULTS)
        self.profiles: dict[str, dict[str, Any]] = {}
        # je Rollladen: profile, contact_open, contact_tilted, auto, storm
        self.covers: dict[str, dict[str, Any]] = {}
        self._rt: dict[str, dict[str, Any]] = {}
        self._persist: dict[str, Any] = {}   # zuletzt gesendet je Rollladen, letzter Lauf (für „nachholen“)
        self._storm = False
        self._storm_low_since: float | None = None
        self._gust: float | None = None
        self._fc: dict[str, dict[str, Any]] = {}
        self._fc_at = 0.0
        self._cal: dict[str, list[dict[str, Any]]] = {}
        self._cal_at = 0.0
        self._started_at = 0.0
        self._track_cache: tuple | None = None
        self._seed: set[str] = set()
        self._tl_cache: dict = {}
        self._unsubs: list[Callable[[], None]] = []
        self._state_unsub: Callable[[], None] | None = None
        self._pending: Callable[[], None] | None = None
        self._subscribers: set[Callable[[dict], None]] = set()

    # ------------------------------------------------------------ Speicher
    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        old = dict(stored.get("settings") or {})
        self.settings.update({k: v for k, v in old.items() if k in RW_KEYS})
        self.covers = stored.get("covers") or {}
        self.profiles = stored.get("profiles") or {}
        self._persist = stored.get("persist") or {}
        # Tagesstand (heute schon geöffnet/geschlossen, Stufe 1 …) über einen Neustart retten
        if self._persist.get("day_date") == dt_util.now().date().isoformat():
            for entity_id, flags in (self._persist.get("day") or {}).items():
                self._rt.setdefault(entity_id, {}).update(flags)
        if not self.profiles:
            self._migrate(old)
        # 0.38: gekippte Fenster (seit 0.29 automatisch aus Heizwerk) lüften in allen Profilen – bisher war das
        # Lüften standardmäßig aus, ein gekipptes Fenster wurde also abends ganz zugefahren.
        if not self._persist.get("vent_default"):
            changed = []
            for prof in self.profiles.values():
                feats = list(prof.get("features") or [])
                if "ventilate" not in feats:
                    prof["features"] = feats + ["ventilate"]
                    changed.append(prof.get("name") or "?")
            self._persist["vent_default"] = True
            if changed:
                self.log.add("settings", "Rollwerk: gekippte Fenster lüften jetzt",
                             f"Lüftungsstellung bei gekipptem Fenster eingeschaltet in: {', '.join(changed)}. "
                             "Abschalten je Profil unter Fenster & Lüften.", module="rollwerk")
            self._save()
        # Böen-Sensor gehört jetzt zu Hauswerk › Wetter (gilt für alle Module)
        if self.settings.get("rw_wind_entity") and not self.haus.settings.get("wind_sensor"):
            self.haus.settings["wind_sensor"] = self.settings["rw_wind_entity"]
            self.haus._save()

    def _migrate(self, old: dict[str, Any]) -> None:
        """Aus den Einstellungen von 0.24 (eine Einstellung für alle, Fassade je Rollladen) Profile machen."""
        base = dict(PROFILE_DEFAULTS)
        features = ["up", "down", "time", "ventilate"]
        if (old.get("rw_open_mode") or "sun") == "sun" or (old.get("rw_close_mode") or "sun") == "sun":
            features.append("sun")
        if old.get("rw_open_mode") == "off":
            features.remove("up")
        if old.get("rw_close_mode") == "off":
            features.remove("down")
        if old.get("rw_shade"):
            features.append("shading")
        base.update(features=features)
        for key, new in (("rw_open_not_before", "up_early"), ("rw_open_not_before_we", "up_early_we"),
                         ("rw_close_not_after", "down_late")):
            if old.get(key):
                base[new] = old[key]
        if old.get("rw_open_mode") == "time":
            base.update(up_early=old.get("rw_open_time") or "07:00", up_late=old.get("rw_open_time") or "07:00",
                        up_early_we=old.get("rw_open_time_we") or "08:30", up_late_we=old.get("rw_open_time_we") or "08:30")
        if old.get("rw_close_mode") == "time":
            t = old.get("rw_close_time") or "21:00"
            base.update(down_early=t, down_late=t, down_early_we=t, down_late_we=t)
        if old.get("rw_shade_pos") is not None:
            base["pos_shading"] = old["rw_shade_pos"]
        if old.get("rw_shade_temp") is not None:
            base["temp2_min"] = old["rw_shade_temp"]
        if old.get("rw_shade_elev") is not None:
            base["elevation_min"] = old["rw_shade_elev"]
        base["shade_start_and"] = ["azimuth", "elevation", "temp2"]
        base["shade_end_or"] = ["azimuth", "elevation", "temp2"]
        self.profiles = {"standard": dict(base, name="Standard")}
        for entity_id, cfg in list(self.covers.items()):
            facade = cfg.get("facade")
            profile = "standard"
            if facade in FACADES:
                profile = f"fassade_{facade.lower()}"
                if profile not in self.profiles:
                    az = FACADES[facade]
                    self.profiles[profile] = dict(base, name=f"Fassade {facade}",
                                                  azimuth_start=(az - 60) % 360, azimuth_end=(az + 60) % 360)
            self.covers[entity_id] = {"profile": profile, "contact_open": cfg.get("door"), "contact_tilted": None,
                                      "auto": cfg.get("auto", True), "storm": cfg.get("storm", True)}
        if old:
            _LOGGER.info("Rollwerk: Einstellungen in %d Profile übernommen", len(self.profiles))

    def _data(self) -> dict[str, Any]:
        return {"settings": self.settings, "covers": self.covers, "profiles": self.profiles, "persist": self._persist}

    def _save(self, delay: float = 2) -> None:
        self._store.async_delay_save(self._data, delay)

    async def async_start(self) -> None:
        self._started_at = dt_util.utcnow().timestamp()
        self._seed = set(self.settings.get("rw_covers") or [])  # beim Start vorhandene Rollläden: erst Stand übernehmen
        self._unsubs.append(async_track_time_interval(self.hass, self._async_tick, timedelta(minutes=1)))
        self._unsubs.append(self.haus.subscribe(self._on_house))
        self._track()
        await self.async_evaluate(initial=True)

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None
        await self._store.async_save(self._data())

    def _track(self) -> None:
        """Kontakte, Bewohner und Erzwingen-Schalter sofort beachten (nicht erst zur nächsten Minute)."""
        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None
        ids: set[str] = set()
        for entity_id in self.settings.get("rw_covers") or []:
            cfg = self.covers.get(entity_id) or {}
            ids.update(e for e in (cfg.get("contact_open"), cfg.get("contact_tilted")) if e)
            opens, tilted, _src = self.contacts(entity_id)
            ids.update(opens + tilted)
            prof = self.profile(entity_id)
            ids.update(prof.get(k) for k in ("resident_sensor", "force_pause", "force_up", "force_down",
                                              "force_ventilate", "force_shading", "shading_alt_entity") if prof.get(k))
        if ids:
            self._state_unsub = async_track_state_change_event(self.hass, sorted(ids), self._on_change)

    @callback
    def _on_change(self, _event: Event) -> None:
        if self._pending is None:
            self._pending = async_call_later(self.hass, 2, self._async_later)

    async def _async_later(self, _now=None) -> None:
        self._pending = None
        await self.async_evaluate()

    @callback
    def _on_house(self) -> None:
        self.hass.async_create_task(self.async_evaluate())

    async def _async_tick(self, _now=None) -> None:
        self._track()  # Fenster der Heizwerk-Räume können sich geändert haben
        await self._async_refresh()
        await self.async_evaluate()

    @callback
    def subscribe(self, cb: Callable[[dict], None]) -> Callable[[], None]:
        self._subscribers.add(cb)

        @callback
        def unsub() -> None:
            self._subscribers.discard(cb)

        return unsub

    # ------------------------------------------------------------ Änderungen
    def profile(self, entity_id: str) -> dict[str, Any]:
        pid = (self.covers.get(entity_id) or {}).get("profile") or "standard"
        prof = self.profiles.get(pid) or self.profiles.get("standard") or next(iter(self.profiles.values()), {})
        return {**PROFILE_DEFAULTS, **prof}

    async def async_save_settings(self, settings: dict[str, Any], by: str | None = None) -> None:
        settings = {k: v for k, v in settings.items() if k in RW_KEYS}
        changed = [k for k, v in settings.items() if self.settings.get(k) != v]
        if not changed:
            return
        log_settings(self.log, settings, changed, by, module="rollwerk", old=self.settings)
        self.settings.update(settings)
        for entity_id in self.settings.get("rw_covers") or []:
            self.covers.setdefault(entity_id, {"profile": "standard"})
        self._save()
        self._track()
        await self.async_evaluate()

    async def async_save_cover(self, entity_id: str, cfg: dict[str, Any], by: str | None = None) -> None:
        old = self.covers.get(entity_id) or {}
        self.covers[entity_id] = cfg
        self._save()
        self._track()
        names = {"profile": "Profil", "contact_open": "Kontakt offen", "contact_tilted": "Kontakt gekippt", "auto": "Automatik",
                 "storm": "Sturmschutz", "room": "Raum", "contacts": "Kontakte"}
        diff = []
        for key, label in names.items():
            a, b = old.get(key), cfg.get(key)
            if a == b or (key in ("auto", "storm") and (a is None or a is True) and (b is None or b is True)):
                continue
            if key in ("auto", "storm"):
                a, b = a is not False, b is not False
            elif key == "room":
                a, b = (self._room_label(a) if a else "automatisch"), (self._room_label(b) if b else "automatisch")
            if key == "profile":
                a, b = (self.profiles.get(a or "standard") or {}).get("name", a), (self.profiles.get(b or "standard") or {}).get("name", b)
            elif key.startswith("contact_"):
                a, b = (self._name(a) if a else None), (self._name(b) if b else None)
            elif key == "contacts":
                a, b = ("keine" if a == "none" else "aus Heizwerk"), ("keine" if b == "none" else "aus Heizwerk")
            diff.append(f"{label} {_fmt_value(a, '')} → {_fmt_value(b, '')}")
        if diff:
            self._log("settings", f"Rollladen {self._name(entity_id)} geändert",
                      f"{', '.join(diff)} · Panel{f' · von {by}' if by else ''}", entity_id)
        await self.async_evaluate()

    async def async_save_profile(self, pid: str | None, profile: dict[str, Any], by: str | None = None) -> str:
        if not pid:
            base = "".join(c if c.isalnum() else "_" for c in (profile.get("name") or "profil").lower())[:20] or "profil"
            pid, n = base, 2
            while pid in self.profiles:
                pid, n = f"{base}_{n}", n + 1
        new = pid not in self.profiles
        old = dict(self.profiles.get(pid) or {})
        self.profiles[pid] = {k: v for k, v in profile.items() if k in PROFILE_SPEC}
        self._save()
        self._track()
        users = [e for e, c in self.covers.items() if (c.get("profile") or "standard") == pid and e in (self.settings.get("rw_covers") or [])]
        what = "" if new else profile_changes(old, self.profiles[pid], self._name)
        if new or what:
            where = ("für " + ", ".join(self._name(e) for e in users[:3]) + (f" und {len(users) - 3} weitere" if len(users) > 3 else "")
                     if users else "noch kein Rollladen")
            self._log("settings", f"Profil „{profile.get('name')}“ {'angelegt' if new else 'geändert'}",
                      f"{what + ' · ' if what else ''}{where} · Panel{f' · von {by}' if by else ''}")
        await self.async_evaluate()
        return pid

    async def async_delete_profile(self, pid: str, replace_with: str | None = None, by: str | None = None) -> None:
        """Profil löschen (auch „Standard“) – ein Profil bleibt immer. Rollläden bekommen das Ersatzprofil."""
        if pid not in self.profiles or len(self.profiles) < 2:
            return
        name = self.profiles.pop(pid).get("name")
        if replace_with not in self.profiles:
            replace_with = "standard" if "standard" in self.profiles else next(iter(self.profiles))
        moved = 0
        for cfg in self.covers.values():
            if (cfg.get("profile") or "standard") == pid:
                cfg["profile"] = replace_with
                moved += 1
        self._save()
        self._track()
        new_name = self.profiles[replace_with].get("name")
        self._log("settings", f"Profil „{name}“ gelöscht",
                     f"{moved} Rollläden nutzen jetzt „{new_name}“{f' · von {by}' if by else ''}" if moved else (f"von {by}" if by else None))
        await self.async_evaluate()

    async def async_command(self, entity_ids: list[str], action: str, position: int | None = None, by: str | None = None) -> None:
        """Von Hand aus dem Panel: hoch, runter, stopp, Stellung – oder Übersteuerung zurücksetzen."""
        now = dt_util.utcnow().timestamp()
        for entity_id in entity_ids:
            rt = self._rt.setdefault(entity_id, {})
            if action == "resume":
                rt["manual_at"] = None
                if self.profile(entity_id).get("manual_recover"):
                    rt["sent"] = None
                continue
            if action == "stop":
                await self._call("cover", "stop_cover", {"entity_id": entity_id})
            else:
                target = int(position) if action == "position" and position is not None else 100 if action == "open" else 0
                await self._move(entity_id, target)
                rt["manual_at"] = now  # Panel = von Hand
                rt["moved_at"] = None
        names = ", ".join(self._name(e) for e in entity_ids[:4]) + (" …" if len(entity_ids) > 4 else "")
        what = {"open": "hoch", "close": "runter", "stop": "Stopp", "resume": "Automatik übernimmt wieder"}.get(action, f"auf {position} %")
        self._log("manual", f"Rollladen {what}", f"{names} · im Panel{f' · von {by}' if by else ''}",
                  entity_ids[0] if len(entity_ids) == 1 else None)
        if action == "resume":
            await self.async_evaluate()

    # ------------------------------------------------------------ Helfer
    def _log(self, cat: str, title: str, why: str | None = None, entity_id: str | None = None) -> None:
        """Protokoll-Eintrag von Rollwerk – mit Heizwerk-Raum des Rollladens (für den Raumfilter)."""
        room_id = room_name = None
        if entity_id:
            room_id, room, _auto = self.room_of(entity_id)
            room_name = (room or {}).get("name") or self._area(entity_id)
        self.log.add(cat, title, why, room=room_id, room_name=room_name, module="rollwerk")

    def _room_label(self, room_id: str) -> str:
        """Name eines Heizwerk-Raums für das Protokoll."""
        ctl = (self.hass.data.get(DOMAIN) or {}).get(MODULE_HEATING)
        room = (getattr(ctl, "rooms", None) or {}).get(room_id) or {}
        return room.get("name") or room_id

    def _name(self, entity_id: str | None) -> str:
        state = self.hass.states.get(entity_id) if entity_id else None
        return state.name if state is not None else str(entity_id)

    def _area(self, entity_id: str) -> str | None:
        try:
            entry = er.async_get(self.hass).async_get(entity_id)
            if entry is None:
                return None
            area_id = entry.area_id
            if not area_id and entry.device_id:
                device = dr.async_get(self.hass).async_get(entry.device_id)
                area_id = getattr(device, "area_id", None)
            area = ar.async_get(self.hass).async_get_area(area_id) if area_id else None
            return area.name if area else None
        except Exception:  # noqa: BLE001
            return None

    def _area_id(self, entity_id: str) -> str | None:
        try:
            entry = er.async_get(self.hass).async_get(entity_id)
            if entry is None:
                return None
            if entry.area_id:
                return entry.area_id
            device = dr.async_get(self.hass).async_get(entry.device_id) if entry.device_id else None
            return getattr(device, "area_id", None)
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------ Raum aus Heizwerk
    def _heizwerk(self):
        return (self.hass.data.get(DOMAIN) or {}).get(MODULE_HEATING)

    def room_of(self, entity_id: str) -> tuple[str | None, dict | None, bool]:
        """Heizwerk-Raum eines Rollladens: gewählt, sonst über den Bereich gefunden. (id, Raum, automatisch?)"""
        ctl = self._heizwerk()
        rooms = getattr(ctl, "rooms", None) or {}
        choice = (self.covers.get(entity_id) or {}).get("room")
        if choice == "none" or not rooms:
            return None, None, False
        if choice and choice in rooms:
            return choice, rooms[choice], False
        area_id = self._area_id(entity_id)
        area_name = (self._area(entity_id) or "").strip().lower()
        for room_id, room in rooms.items():
            if area_id and any(self._area_id(e) == area_id for e in (room.get("climates") or []) + (room.get("windows") or [])):
                return room_id, room, True
        for room_id, room in rooms.items():
            if area_name and str(room.get("name") or "").strip().lower() == area_name:
                return room_id, room, True
        return None, None, False

    def contacts(self, entity_id: str) -> tuple[list[str], list[str], str | None]:
        """Kontakte „ganz offen“ und „gekippt“: eigene am Rollladen, sonst die Fenster des Heizwerk-Raums.

        Aus Heizwerk: Türkontakte zählen als „ganz offen“ (Aussperrschutz), Fensterkontakte als „gekippt“
        (Lüftungsstellung) – ein offenes Fenster sperrt niemanden aus.
        """
        cfg = self.covers.get(entity_id) or {}
        own_open, own_tilted = cfg.get("contact_open"), cfg.get("contact_tilted")
        if own_open or own_tilted or cfg.get("contacts") == "none":
            return [e for e in [own_open] if e], [e for e in [own_tilted] if e], "own" if own_open or own_tilted else None
        _rid, room, _auto = self.room_of(entity_id)
        if not room:
            return [], [], None
        opens, tilted = [], []
        for e in room.get("windows") or []:
            if not e.startswith(("binary_sensor.", "input_boolean.")):
                continue
            state = self.hass.states.get(e)
            text = f"{e} {state.name if state is not None else ''}".lower()
            dc = state.attributes.get("device_class") if state is not None else None
            if "kipp" in text or "tilt" in text:
                tilted.append(e)
            elif dc in ("door", "garage_door") or "tür" in text or "tuer" in text or "door" in text:
                opens.append(e)
            else:
                tilted.append(e)
        return opens, tilted, "heizwerk" if opens or tilted else None

    def room_temp(self, entity_id: str) -> float | None:
        """Raumtemperatur aus Heizwerk (Raumsensor, sonst Wandthermostat)."""
        ctl = self._heizwerk()
        _rid, room, _auto = self.room_of(entity_id)
        if not room or ctl is None or not hasattr(ctl, "_room_values"):
            return None
        try:
            return ctl._room_values(room)[0]
        except Exception:  # noqa: BLE001
            return None

    def _on(self, entity_id: str | None) -> bool:
        state = self.hass.states.get(entity_id) if entity_id else None
        return state is not None and str(state.state).lower() in ("on", "true", "home", "open", "opening", "tilted")

    def _contact(self, entity_id: str | None) -> bool:
        state = self.hass.states.get(entity_id) if entity_id else None
        return state is not None and str(state.state).lower() in WINDOW_OPEN_STATES

    def _num(self, entity_id: str | None) -> float | None:
        state = self.hass.states.get(entity_id) if entity_id else None
        return _float(state.state) if state is not None and state.state not in BAD else None

    def _pos(self, entity_id: str) -> float | None:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in BAD:
            return None
        pos = _float(state.attributes.get("current_position"))
        if pos is None:
            pos = 100.0 if state.state == "open" else 0.0 if state.state == "closed" else None
        return pos

    async def _call(self, domain: str, service: str, data: dict[str, Any]) -> None:
        await self.hass.services.async_call(domain, service, data, context=Context())

    async def _move(self, entity_id: str, position: int) -> None:
        state = self.hass.states.get(entity_id)
        features = int((state.attributes.get("supported_features") if state else 0) or 0)
        if features & 4:  # Stellung anfahrbar
            await self._call("cover", "set_cover_position", {"entity_id": entity_id, "position": position})
        else:
            await self._call("cover", "open_cover" if position >= 50 else "close_cover", {"entity_id": entity_id})

    def _sun(self) -> tuple[float | None, float | None]:
        state = self.hass.states.get(self.haus.settings.get("sun_entity") or "sun.sun")
        if state is None:
            return None, None
        return _float(state.attributes.get("azimuth")), _float(state.attributes.get("elevation"))

    def _wind(self) -> float | None:
        """Aktuelle Böen in km/h: eigener Sensor, sonst Wetterdienst (Böen, sonst Wind)."""
        entity_id = self.haus.settings.get("wind_sensor") or self.settings.get("rw_wind_entity")
        if entity_id:
            state = self.hass.states.get(entity_id)
            value = _float(state.state) if state is not None else None
            unit = (state.attributes.get("unit_of_measurement") or "km/h") if state is not None else "km/h"
        else:
            weather = self.haus.weather_entity()
            state = self.hass.states.get(weather) if weather else None
            if state is None:
                return None
            attrs = state.attributes
            value = _float(attrs.get("wind_gust_speed"))
            if value is None:
                value = _float(attrs.get("wind_speed"))
            unit = attrs.get("wind_speed_unit") or "km/h"
        if value is None:
            return None
        return round(value * 3.6, 1) if unit == "m/s" else round(value * 1.609, 1) if unit == "mph" else value

    def _free_day(self, tomorrow_entity: str | None = None) -> bool:
        """Heute frei (Wochenende/Feiertag)? Mit tomorrow_entity: ist morgen frei (fürs Schließen)?"""
        if tomorrow_entity:
            state = self.hass.states.get(tomorrow_entity)
            if state is not None and state.state in ("on", "off"):
                return state.state == "off"
        now = dt_util.now()
        if now.weekday() >= 5:
            return True
        workday = self.hass.states.get(self.haus.settings.get("workday_entity") or "")
        return workday is not None and workday.state == "off"

    async def _async_refresh(self, force: bool = False) -> None:
        """Wettervorhersage (Höchstwert, Wetterlage) und Kalender-Termine alle 30 bzw. 5 Minuten."""
        now = dt_util.utcnow().timestamp()
        covers = self.settings.get("rw_covers") or []
        if force or now - self._fc_at >= 1800:
            self._fc_at = now
            for entity_id in {self.profile(c).get("forecast_entity") or self.haus.weather_entity() for c in covers} - {None}:
                try:
                    response = await self.hass.services.async_call(
                        "weather", "get_forecasts", {"entity_id": entity_id, "type": "daily"}, blocking=True, return_response=True)
                    day = (((response or {}).get(entity_id) or {}).get("forecast") or [{}])[0]
                    self._fc[entity_id] = {"tmax": _float(day.get("temperature")), "condition": day.get("condition")}
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Keine Vorhersage von %s: %s", entity_id, err)
        if force or now - self._cal_at >= 300:
            self._cal_at = now
            start = dt_util.start_of_local_day()
            for cal in {self.profile(c).get("calendar") for c in covers if self.profile(c).get("time_mode") == "calendar"} - {None}:
                try:
                    events = await async_calendar_events(self.hass, cal, start, start + timedelta(days=1))
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Kalender %s nicht lesbar: %s", cal, err)
                    continue
                out = []
                for ev in events:
                    begin, _ = parse_when(ev.get("start"))
                    end, _ = parse_when(ev.get("end"))
                    if begin is not None and end is not None:
                        out.append({"summary": str(ev.get("summary") or ""), "start": begin.hour * 60 + begin.minute,
                                    "end": end.hour * 60 + end.minute if end.date() == begin.date() else 1439})
                self._cal[cal] = out

    def _hold(self, rt: dict, key: str, cond: bool, seconds: float, now: float) -> bool:
        """Bedingung erst nach seconds Sekunden am Stück als erfüllt werten.

        In den ersten Minuten nach dem Start zählt der Zustand sofort – sonst hielte Rollwerk z. B. abends
        „noch nicht dunkel genug“ für wahr und wollte die Rollläden nach einem Neustart öffnen.
        """
        if not cond:
            rt.pop(key, None)
            return False
        since = rt.setdefault(key, now)
        if now - self._started_at < STARTUP_GRACE:
            return True
        return now - since >= seconds

    # ------------------------------------------------------------ Steuerung
    def _windows(self, prof: dict) -> tuple[tuple[int, int] | None, tuple[int, int] | None]:
        """Zeitfenster heute (früheste/späteste Minute) fürs Öffnen und Schließen."""
        if prof.get("time_mode") == "calendar":
            events = self._cal.get(prof.get("calendar") or "") or []
            def window(title: str):
                hits = [e for e in events if title and title.lower() in e["summary"].lower()]
                return (min(e["start"] for e in hits), max(e["end"] for e in hits)) if hits else None
            return window(prof.get("cal_open") or ""), window(prof.get("cal_close") or "")
        free = self._free_day()
        free_tomorrow = self._free_day(prof.get("workday_tomorrow")) if prof.get("workday_tomorrow") else free
        up = (_hm(prof.get("up_early_we" if free else "up_early"), "07:00"), _hm(prof.get("up_late_we" if free else "up_late"), "08:00"))
        down = (_hm(prof.get("down_early_we" if free_tomorrow else "down_early"), "16:00"),
                _hm(prof.get("down_late_we" if free_tomorrow else "down_late"), "22:00"))
        return up, down

    def _day_phase(self, entity_id: str, prof: dict, rt: dict, now: float, now_min: int, elevation: float | None) -> tuple[bool | None, str]:
        """Tag (True) oder Nacht (False) nach Zeit, Sonnenhöhe und Helligkeit – wie CCA. None = unbestimmt."""
        feats = set(prof.get("features") or [])
        today = dt_util.now().date().isoformat()
        sun_on, br_on = "sun" in feats, "brightness" in feats
        bright = self._num(prof.get("brightness_sensor"))
        hyst = float(prof.get("brightness_hyst") or 0)
        conds_up, conds_down = [], []
        if sun_on and elevation is not None:
            conds_up.append(self._hold(rt, "h_sun_up", elevation >= float(prof.get("sun_up") or 0), float(prof.get("sun_duration") or 0), now))
            conds_down.append(self._hold(rt, "h_sun_dn", elevation <= float(prof.get("sun_down") or 0), float(prof.get("sun_duration") or 0), now))
        if br_on and bright is not None:
            dur = float(prof.get("brightness_duration") or 0)
            conds_up.append(self._hold(rt, "h_br_up", bright >= float(prof.get("brightness_up") or 0) + hyst, dur, now))
            conds_down.append(self._hold(rt, "h_br_dn", bright <= float(prof.get("brightness_down") or 0) - hyst, dur, now))
        both_and = prof.get("bs_operator") == "and"
        def combine(conds: list[bool]) -> bool | None:
            if not conds:
                return None
            return all(conds) if both_and else any(conds)
        ok_up, ok_down = combine(conds_up), combine(conds_down)
        if "time" not in feats:
            # ohne Zeitsteuerung: nur Sonne/Helligkeit entscheiden
            if ok_up is None and ok_down is None:
                return rt.get("day"), "keine Auslöser gewählt"
            if rt.get("day") is not False and ok_down:
                rt["day"] = False
            elif rt.get("day") is not True and ok_up and not ok_down:
                rt["day"] = True
            return rt.get("day"), "Sonne/Helligkeit"
        up, down = self._windows(prof)
        if prof.get("close_stage1") and down:
            down = (down[1], down[1]) if prof.get("close_stage2", True) else None
        if up and rt.get("opened_on") != today and now_min >= up[0] and (ok_up is not False or now_min >= up[1]):
            rt["opened_on"] = today
            rt["why_day"] = "späteste Zeit" if ok_up is False else "Sonne/Helligkeit" if ok_up else "Zeit"
        if down and rt.get("closed_on") != today and now_min >= down[0] and (ok_down is not False or now_min >= down[1]):
            rt["closed_on"] = today
            rt["why_night"] = "späteste Zeit" if ok_down is False else "Sonne/Helligkeit" if ok_down else "Zeit"
        day = rt.get("opened_on") == today and rt.get("closed_on") != today
        if not up:
            day = rt.get("closed_on") != today and now_min < (down[0] if down else 1440) and rt.get("day") is not False
        rt["day"] = day
        return day, rt.get("why_day" if day else "why_night") or "Zeit"

    def _stage1(self, prof: dict, rt: dict, now_min: int, azimuth: float | None, elevation: float | None, today: str) -> bool:
        """Stufe 1 erreicht? Einmal erreicht, gilt sie bis zum nächsten Morgen."""
        if rt.get("stage1_on") == today:
            return True
        trig = prof.get("stage1_trigger") or "azimuth"
        hit = False
        if trig == "time":
            hit = now_min >= _hm(prof.get("stage1_time"), "18:00")
        elif trig == "azimuth":
            hit = azimuth is not None and now_min >= 720 and azimuth >= float(prof.get("stage1_azimuth") or 250)
        elif trig == "elevation":
            hit = elevation is not None and now_min >= 720 and elevation <= float(prof.get("stage1_elevation") or 10)
        if hit:
            rt["stage1_on"] = today
        return hit

    @staticmethod
    def _stage1_why(prof: dict) -> str:
        trig = prof.get("stage1_trigger") or "azimuth"
        if trig == "time":
            return f"ab {prof.get('stage1_time') or '18:00'}"
        if trig == "elevation":
            return f"Sonne unter {float(prof.get('stage1_elevation') or 10):g}°"
        return f"Sonne ab {float(prof.get('stage1_azimuth') or 250):g}°"

    def _shading(self, prof: dict, rt: dict, now: float, azimuth: float | None, elevation: float | None,
                 room_temp: float | None = None) -> tuple[bool, dict]:
        """Beschattung an/aus nach den Bedingungen des Profils, mit Wartezeiten."""
        fc = self._fc.get(prof.get("forecast_entity") or self.haus.weather_entity() or "") or {}
        weather = self.hass.states.get(prof.get("forecast_entity") or self.haus.weather_entity() or "")
        temp2 = self._num(prof.get("temp2_sensor"))
        if temp2 is None and not prof.get("temp2_sensor"):
            temp2, _rh = self.haus.outside_air()
        values = {
            "azimuth": azimuth, "elevation": elevation,
            "brightness": self._num(prof.get("shade_brightness_sensor")),
            "temp1": self._num(prof.get("temp1_sensor")) if prof.get("temp1_sensor") else room_temp, "temp2": temp2,
            "forecast_temp": fc.get("tmax"),
            "forecast_weather": fc.get("condition") or (weather.state if weather is not None else None),
            "custom": self._on(prof.get("shade_custom")) if prof.get("shade_custom") else None,
        }
        start, end = shade_conditions(values, prof, active=bool(rt.get("shading")))
        want = shade_wanted(prof, start, end, bool(rt.get("shading")))
        if rt.get("shading"):
            out_of_range = end.get("azimuth") or end.get("elevation")
            if not want:
                rt.pop("h_shade_end", None)
            elif prof.get("shade_end_immediate") and out_of_range:
                rt["shading"] = False
            elif self._hold(rt, "h_shade_end", True, float(prof.get("shade_wait_end") or 0), now):
                rt["shading"] = False
        else:
            if self._hold(rt, "h_shade_start", want, float(prof.get("shade_wait_start") or 0), now):
                rt["shading"] = True
                rt.pop("h_shade_start", None)
        return bool(rt.get("shading")), {"start": start, "end": end, "values": values}

    def _decide(self, entity_id: str, cfg: dict, prof: dict, rt: dict, now: float, now_min: int,
                azimuth: float | None, elevation: float | None, pos: float | None) -> tuple[int | None, str, str]:
        """Sollstellung, Begründung und Art (open/close/shading/ventilation/storm/force/resident)."""
        feats = set(prof.get("features") or [])
        behavior = set(prof.get("behavior") or [])
        vent_opts = set(prof.get("vent_options") or [])
        p_open, p_close = int(prof.get("pos_open") or 100), int(prof.get("pos_close") or 0)
        p_vent = int(prof.get("pos_ventilate") if prof.get("pos_ventilate") is not None else 30)
        p_shade = int(prof.get("pos_shading") if prof.get("pos_shading") is not None else 25)
        if prof.get("pos_shading_alt") is not None and self._on(prof.get("shading_alt_entity")):
            p_shade = int(prof["pos_shading_alt"])
        today = dt_util.now().date().isoformat()
        if cfg.get("auto") is False:
            return None, "Automatik aus", "none"
        if self._on(prof.get("force_pause")):
            return None, f"Pause ({self._name(prof['force_pause'])})", "none"
        if self._storm and cfg.get("storm", True):
            return 100, "Sturmschutz", "storm"
        if self._on(prof.get("force_up")):
            return p_open, f"Erzwungen: auf ({self._name(prof['force_up'])})", "force"
        for key, p_forced, label in (("force_down", p_close, "zu"), ("force_ventilate", p_vent, "lüften"), ("force_shading", p_shade, "Beschattung")):
            if self._on(prof.get(key)):
                return self._door_floor(entity_id, prof, feats, pos, p_forced, f"Erzwungen: {label} ({self._name(prof[key])})", "force")

        day, why = self._day_phase(entity_id, prof, rt, now, now_min, elevation)
        shading, info = (False, {})
        if "shading" in feats and day:
            shading, info = self._shading(prof, rt, now, azimuth, elevation, self.room_temp(entity_id))
        elif rt.get("shading"):
            rt["shading"] = False
        rt["shade_info"] = info
        was_shading = rt.get("was_shading", False)
        if was_shading and not shading:
            rt["shade_ended_on"] = today
        rt["was_shading"] = shading
        if shading:
            rt["shaded_on"] = today

        resident = self._on(prof.get("resident_sensor"))
        rconf = set(prof.get("resident_config") or [])
        # Grundstellung aus Tag/Nacht/Beschattung
        target, reason, cat = None, "", "none"
        if day is False and "down" in feats:
            target, reason, cat = p_close, f"Abends schließen ({why})", "close"
            if "prevent_lowering_when_closing_if_shaded" in behavior and pos is not None and abs(pos - p_shade) <= 2:
                target, reason = p_shade, "Abends: bleibt in Beschattung"
        elif day:
            if shading and not ("prevent_shading_multiple_times" in behavior and rt.get("shaded_on") == today and not was_shading and rt.get("shade_ended_on") == today):
                target, reason, cat = p_shade, "Beschattung", "shading"
            elif "up" in feats:
                if rt.get("shade_ended_on") == today and "prevent_opening_after_shading_end" in behavior:
                    target, reason, cat = None, "nach Beschattung: bleibt so", "none"
                elif rt.get("shade_ended_on") == today and "ventilation_after_shading_end" in vent_opts:
                    target, reason, cat = p_vent, "nach Beschattung: Lüftungsstellung", "open"
                else:
                    target, reason, cat = p_open, f"Morgens öffnen ({why})", "open"
            if (cat == "shading" or rt.get("shade_ended_on") == today) and "prevent_shading_end_if_closed" in behavior \
                    and pos is not None and pos <= p_close + 2 and cat != "shading":
                target, reason, cat = None, "Beschattung endet – Rollladen bleibt zu", "none"
        # Abends in zwei Stufen
        if prof.get("close_stage1") and "down" in feats:
            p_st1 = int(prof.get("pos_stage1") if prof.get("pos_stage1") is not None else 50)
            if day and self._stage1(prof, rt, now_min, azimuth, elevation, today) and (target is None or target > p_st1 or cat == "open"):
                if not (cat == "shading" and target is not None and target <= p_st1):
                    target, reason, cat = p_st1, f"Abends Stufe 1 ({self._stage1_why(prof)})", "close"
            elif day is False and not prof.get("close_stage2", True):
                target, reason, cat = p_st1, "Nacht: bleibt auf Stufe 1", "close"
            elif day is False and cat == "close":
                reason = "Abends Stufe 2 (späteste Zeit)"
        # Bewohner (z. B. schläft): nicht öffnen; auf Wunsch schließen
        if resident and prof.get("resident_sensor"):
            if "closing" in rconf:
                target, reason, cat = p_close, f"Bewohner schläft ({self._name(prof['resident_sensor'])})", "resident"
            elif cat == "open" and "allow_opening" not in rconf:
                target, reason, cat = None, "Bewohner schläft – nicht öffnen", "none"
            elif cat == "shading" and "allow_shading" not in rconf:
                target, reason, cat = None, "Bewohner schläft – keine Beschattung", "none"
        elif rt.get("resident_was") and not resident and "opening" in rconf and day and "up" in feats:
            target, reason, cat = p_open, "Bewohner ist wach", "resident"
        rt["resident_was"] = resident
        # Anwesenheit aus Hauswerk: niemand zu Hause (oder Urlaub) -> tagsüber zu bzw. beschattet
        away = bool(getattr(self.haus, "away", False) or getattr(self.haus, "vacation", False))
        if away and day and cat in ("open", "shading", "none") and prof.get("away_mode") in ("closed", "shade"):
            if prof["away_mode"] == "closed":
                target, reason, cat = p_close, "Niemand zu Hause – bleibt zu", "away"
            else:
                target, reason, cat = p_shade, "Niemand zu Hause – Beschattung", "away"
        if "prevent_higher_position_closing" in behavior and cat == "close" and pos is not None and target is not None and target > pos:
            target, reason = None, "Abends: nicht höher fahren"
        if "prevent_opening_multiple_times" in behavior and cat == "open" and rt.get("auto_opened_on") == today and rt.get("sent_cat") != "open":
            target, reason, cat = None, "heute schon einmal geöffnet", "none"
        if "prevent_closing_multiple_times" in behavior and cat == "close" and rt.get("auto_closed_on") == today and rt.get("sent_cat") != "close":
            target, reason, cat = None, "heute schon einmal geschlossen", "none"

        # Fenster/Tür: offen = Aussperrschutz (nicht herunter) bzw. volle Lüftung, gekippt = Lüftungsstellung
        opens, tilts, _src = self.contacts(entity_id)
        open_now = [e for e in opens if self._contact(e)]
        tilt_now = [e for e in tilts if self._contact(e)]
        is_open = bool(open_now)
        tilted = bool(tilt_now) and not is_open
        lock_tilted = set(prof.get("lockout_tilted") or [])
        base_target = target
        if is_open:
            lock = prof.get("pos_lockout")
            if "ventilate" in feats and lock is not None:
                floor = int(lock)
            else:
                floor = int(pos) if pos is not None else p_open
            if target is None or target < floor:
                target, reason, cat = floor, f"{self._name(open_now[0])} offen – nicht herunterfahren", "ventilation"
        elif tilted and "ventilate" in feats and not (cat == "shading" and "shading_over_ventilation" in vent_opts):
            lock_here = (cat == "close" and "lockout_tilted_closing" in lock_tilted) or (
                cat == "shading" and "lockout_tilted_shading_start" in lock_tilted) or (
                cat == "open" and rt.get("shade_ended_on") == today and "lockout_tilted_shading_end" in lock_tilted)
            if lock_here and pos is not None and (target is None or target < pos):
                target, reason, cat = int(pos), f"{self._name(tilt_now[0])} gekippt – Aussperrschutz", "ventilation"
            elif target is None or target < p_vent or ("ventilation_if_lower_enabled" in vent_opts and (target or 0) > p_vent and cat != "open"):
                target, reason, cat = p_vent, f"{self._name(tilt_now[0])} gekippt – lüften", "ventilation"
        rt["vent_active"] = is_open or tilted
        if rt.get("vent_was") and not rt["vent_active"] and "prevent_opening_after_ventilation_end" in behavior and base_target is not None \
                and pos is not None and base_target > pos:
            target, reason, cat = None, "Lüften beendet – bleibt so", "none"
        rt["vent_was"] = rt["vent_active"]
        return target, reason, cat

    def _door_floor(self, entity_id: str, prof: dict, feats: set, pos: float | None, target: int | None,
                    reason: str, cat: str) -> tuple[int | None, str, str]:
        """Aussperrschutz auch beim Erzwingen: bei offener Tür nicht unter die Sperrstellung fahren."""
        opens, _tilts, _src = self.contacts(entity_id)
        open_now = [e for e in opens if self._contact(e)]
        if not open_now:
            return target, reason, cat
        lock = prof.get("pos_lockout")
        floor = int(lock) if ("ventilate" in feats and lock is not None) else (int(pos) if pos is not None else int(prof.get("pos_open") or 100))
        if target is None or target < floor:
            return floor, f"{self._name(open_now[0])} offen – nicht herunterfahren (trotz Erzwingen)", "ventilation"
        return target, reason, cat

    async def async_evaluate(self, initial: bool = False) -> None:
        now = dt_util.utcnow().timestamp()
        local = dt_util.now()
        now_min = local.hour * 60 + local.minute
        azimuth, elevation = self._sun()
        if initial:
            await self._async_refresh(force=True)
        # Sturm: ab der Grenze aus Hauswerk › Wetter, Ende erst nach 15 Min. unter 80 %
        gust = self._wind()
        limit = float(self.haus.settings.get("storm_kmh") or 70)
        storm_before = self._storm
        if self.settings.get("rw_storm", True) and gust is not None and gust >= limit:
            self._storm, self._storm_low_since = True, None
        elif self._storm and (gust is None or gust < limit * 0.8):
            self._storm_low_since = self._storm_low_since or now
            if now - self._storm_low_since >= STORM_RELEASE:
                self._storm = False
        elif not self.settings.get("rw_storm", True):
            self._storm = False
        if self._storm != storm_before:
            self._log("shutter", "Sturmschutz: Rollläden hoch" if self._storm else "Sturmschutz beendet",
                         f"Böen {gust:.0f} km/h · Grenze {limit:.0f} km/h" if gust is not None else None)
        self._gust = gust
        last_run = float(self._persist.get("last_run") or 0)
        recovery = self.settings.get("rw_recovery") or "never"
        for entity_id in self.settings.get("rw_covers") or []:
            state = self.hass.states.get(entity_id)
            cfg = self.covers.get(entity_id) or {}
            prof = self.profile(entity_id)
            rt = self._rt.setdefault(entity_id, {})
            if state is None or state.state in BAD:
                rt["unavailable"] = True
                continue
            rt["unavailable"] = False
            pos = self._pos(entity_id)
            # Von Hand verstellt? (Stellung ändert sich, ohne dass Rollwerk gerade fährt)
            drive = float(prof.get("drive_time") or 90)
            tol = float(prof.get("tolerance") or 0)
            last = rt.get("last_pos")
            sent = rt.get("sent")
            toward = sent is not None and last is not None and pos is not None and min(last, sent) - 2 <= pos <= max(last, sent) + 2
            ours = (sent is not None and pos is not None and abs(pos - sent) <= max(tol, 2)) or (
                bool(rt.get("moved_at")) and now - rt["moved_at"] <= drive + 30 and toward)
            if last is not None and pos is not None and abs(pos - last) > max(tol, 1) and not ours and not initial:
                rt["manual_at"] = now
                rt["manual_pos"] = pos
                self._log("manual", f"{self._name(entity_id)} von Hand auf {pos:.0f} %",
                          "Taster, App oder Automation – Rollwerk merkt sich das als Übersteuerung", entity_id)
            rt["last_pos"] = pos
            self._manual_reset(entity_id, prof, rt, now, local, pos)
            target, reason, cat = self._decide(entity_id, cfg, prof, rt, now, now_min, azimuth, elevation, pos)
            rt.update(target=target, reason=reason, cat=cat)
            if "sent" not in rt and (initial or entity_id in self._seed):
                self._seed.discard(entity_id)
                # erster Blick auf diesen Rollladen seit dem Start (auch wenn er beim Start noch nicht erreichbar war):
                # Stand übernehmen, nichts fahren – außer „Nach Neustart“ verlangt es
                stored = (self._persist.get("sent") or {}).get(entity_id)
                missed = recovery == "always" or (recovery == "outage" and stored is not None and stored != target and now - last_run > 120)
                if not missed:
                    rt["sent"], rt["sent_cat"] = target, cat  # nach dem Start nichts fahren, erst beim nächsten Wechsel
                    continue
            if target is None or target == rt.get("sent"):
                rt["blocked"] = None
                continue
            # Manuelle Übersteuerung: gesperrte Arten fahren nicht
            block = set(prof.get("manual_block") or [])
            cat_block = {"open": "opening", "close": "closing", "shading": "shading", "ventilation": "ventilation"}.get(cat)
            if rt.get("manual_at") and cat_block in block:
                if rt.get("blocked") != "von Hand übersteuert" or rt.get("blocked_target") != target:
                    self._log("shutter", f"{self._name(entity_id)}: Automatik wartet",
                              f"wollte {target} % ({reason}) – bleibt, weil von Hand verstellt", entity_id)
                rt["blocked_target"] = target
                rt["blocked"] = "von Hand übersteuert"
                continue
            rt["blocked"] = None
            rt["sent"], rt["sent_cat"] = target, cat
            self._persist.setdefault("sent", {})[entity_id] = target
            if cat == "open":
                rt["auto_opened_on"] = local.date().isoformat()
            if cat == "close":
                rt["auto_closed_on"] = local.date().isoformat()
            if pos is not None and abs(pos - target) <= max(tol, 1):
                continue
            rt["manual_at"] = None  # eine automatische Fahrt beendet die Übersteuerung
            delay = float(prof.get("delay_fix") or 0) + random.uniform(0, float(prof.get("delay_random") or 0))
            if cat in ("open", "close") and getattr(self.haus, "vacation", False) and prof.get("vacation_random"):
                delay += random.uniform(0, float(prof["vacation_random"]) * 60)  # Urlaub: wirkt bewohnt
            if cat == "ventilation" and "ventilation_start_no_delay" in set(prof.get("vent_options") or []):
                delay = 0
            await self._schedule_move(entity_id, target, reason, delay)
        self._persist["last_run"] = now
        today = local.date().isoformat()
        self._persist["day"] = {e: {k: v for k, v in (self._rt.get(e) or {}).items() if k in DAY_KEYS}
                                for e in self.settings.get("rw_covers") or [] if (self._rt.get(e) or {}).get("opened_on") in (today, None)}
        self._persist["day_date"] = today
        self._save(30)
        status = self.status()
        for cb in list(self._subscribers):
            cb(status)

    def _manual_reset(self, entity_id: str, prof: dict, rt: dict, now: float, local, pos: float | None) -> None:
        """Manuelle Übersteuerung zurücksetzen: feste Uhrzeit, nach Minuten oder in einer Stellung."""
        since = rt.get("manual_at")
        if not since:
            return
        how = set(prof.get("manual_reset") or [])
        done = None
        if "timeout" in how and now - since >= float(prof.get("reset_timeout") or 5) * 60:
            done = "Zeit abgelaufen"
        if "in_position" in how and pos is not None and abs(pos - float(prof.get("reset_position") or 100)) <= 2:
            done = "Stellung erreicht"
        if "fixed" in how:
            reset_min = _hm(prof.get("reset_time"), "00:01")
            since_local = dt_util.as_local(dt_util.utc_from_timestamp(since))
            reset_dt = local.replace(hour=reset_min // 60, minute=reset_min % 60, second=0, microsecond=0)
            if since_local < reset_dt <= local:
                done = "feste Uhrzeit"
        if done:
            rt["manual_at"] = None
            if prof.get("manual_recover"):
                rt["sent"] = None  # zurück zur aktuellen Sollstellung
            self._log("manual", f"{self._name(entity_id)}: Übersteuerung zurückgesetzt", done, entity_id)

    async def _schedule_move(self, entity_id: str, target: int, reason: str, delay: float) -> None:
        async def go(_now=None) -> None:
            self._rt.setdefault(entity_id, {})["moved_at"] = dt_util.utcnow().timestamp()
            await self._move(entity_id, target)
            pos_now = self._pos(entity_id)
            self._log("shutter", f"{self._name(entity_id)} {'auf' if target >= 100 else 'zu' if target == 0 else f'auf {target} %'}",
                      f"{reason}{f' · vorher {pos_now:.0f} %' if pos_now is not None else ''}", entity_id)
        if delay <= 0:
            await go()
        else:
            async_call_later(self.hass, delay, go)

    # ------------------------------------------------------------ Tagesleiste
    def _sun_track(self) -> list[tuple[int, float, float]] | None:
        """Sonnenstand heute alle 10 Minuten (Minute, Azimut, Höhe) – aus dem Standort von Home Assistant."""
        today = dt_util.now().date()
        if self._track_cache and self._track_cache[0] == today:
            return self._track_cache[1]
        track = None
        try:
            from homeassistant.helpers.sun import get_astral_location  # noqa: PLC0415

            location, elevation = get_astral_location(self.hass)
            start = dt_util.start_of_local_day()
            track = []
            for m in range(0, 1440, 10):
                when = start + timedelta(minutes=m)
                track.append((m, float(location.solar_azimuth(when, elevation)), float(location.solar_elevation(when, elevation))))
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Sonnenbahn nicht berechenbar: %s", err)
        self._track_cache = (today, track)
        return track

    def timeline(self, pid: str) -> dict[str, Any]:
        """Voraussichtlicher Tag eines Profils: öffnen, Beschattung (möglich), schließen."""
        prof = {**PROFILE_DEFAULTS, **(self.profiles.get(pid) or {})}
        key = (pid, dt_util.now().date().isoformat(), repr(sorted(prof.items(), key=lambda kv: kv[0])), self._free_day())
        if key in self._tl_cache:
            return self._tl_cache[key]
        feats = set(prof.get("features") or [])
        track = self._sun_track()
        up, down = self._windows(prof)
        sun_on = "sun" in feats and track is not None
        approx = "brightness" in feats

        def first(lo: int, hi: int, test) -> int | None:
            for m, az, el in track or []:
                if lo <= m <= hi and test(el):
                    return m
            return None

        open_at = close_at = None
        if "up" in feats:
            if "time" in feats and up:
                hit = first(up[0], up[1], lambda el: el >= float(prof.get("sun_up") or 0)) if sun_on else None
                open_at = hit if hit is not None else (up[1] if sun_on else up[0])
            elif sun_on:
                open_at = first(0, 1439, lambda el: el >= float(prof.get("sun_up") or 0))
        two = bool(prof.get("close_stage1")) and "down" in feats
        if two and down:
            down = (down[1], down[1]) if prof.get("close_stage2", True) else None
        if "down" in feats and not (two and down is None):
            if two and down:
                close_at = down[1]
            elif "time" in feats and down:
                hit = first(down[0], down[1], lambda el: el <= float(prof.get("sun_down") or 0)) if sun_on else None
                close_at = hit if hit is not None else (down[1] if sun_on else down[0])
            elif sun_on:
                close_at = first(max(open_at or 0, 720), 1439, lambda el: el <= float(prof.get("sun_down") or 0))
        stage1 = None
        if two:
            trig = prof.get("stage1_trigger") or "azimuth"
            if trig == "time":
                stage1 = _hm(prof.get("stage1_time"), "18:00")
            elif track:
                if trig == "azimuth":
                    stage1 = next((m for m, az, _el in track if m >= 720 and az >= float(prof.get("stage1_azimuth") or 250)), None)
                else:
                    stage1 = next((m for m, _az, el in track if m >= 720 and el <= float(prof.get("stage1_elevation") or 10)), None)
            if stage1 is not None and close_at is not None and stage1 >= close_at:
                stage1 = None
        shade: list[list[int]] = []
        if "shading" in feats and track:
            lo, hi = open_at if open_at is not None else 0, close_at if close_at is not None else 1440
            seg = None
            for m, az, el in track:
                cond = shade_conditions({"azimuth": az, "elevation": el}, prof)[0]
                ok = lo <= m < hi and cond.get("azimuth") and cond.get("elevation")
                if ok and seg is None:
                    seg = [m, m + 10]
                elif ok:
                    seg[1] = m + 10
                elif seg is not None:
                    shade.append(seg)
                    seg = None
            if seg is not None:
                shade.append(seg)

        def hm(m: int | None) -> str | None:
            return None if m is None else f"{min(m, 1439) // 60:02d}:{min(m, 1439) % 60:02d}"

        out = {"open": hm(open_at), "close": hm(close_at), "shade": [[hm(a), hm(b)] for a, b in shade], "approx": approx,
               "stage1": hm(stage1), "stage1_min": stage1, "stage1_pos": prof.get("pos_stage1") if two else None,
               "open_min": open_at, "close_min": close_at, "shade_min": shade, "sun": track is not None}
        if len(self._tl_cache) > 50:
            self._tl_cache.clear()
        self._tl_cache[key] = out
        return out

    @staticmethod
    def next_event(tl: dict[str, Any], now_min: int) -> str | None:
        events = []
        if tl.get("open_min") is not None:
            events.append((tl["open_min"], "öffnet"))
        for a, b in tl.get("shade_min") or []:
            events += [(a, "Beschattung möglich"), (b, "Beschattung endet")]
        if tl.get("stage1_min") is not None:
            events.append((tl["stage1_min"], f"Stufe 1 auf {int(tl.get('stage1_pos') or 50)} %"))
        if tl.get("close_min") is not None:
            events.append((tl["close_min"], "schließt"))
        for m, what in sorted(events):
            if m > now_min:
                return f"{'ca. ' if tl.get('approx') else ''}{m // 60:02d}:{m % 60:02d} {what}"
        return None

    # ------------------------------------------------------------ Fürs Panel
    def status(self) -> dict[str, Any]:
        def hm(minutes: int | None) -> str | None:
            return None if minutes is None else f"{minutes // 60:02d}:{minutes % 60:02d}"

        azimuth, elevation = self._sun()
        covers = {}
        local = dt_util.now()
        now_min = local.hour * 60 + local.minute
        timelines = {pid: self.timeline(pid) for pid in self.profiles}
        for entity_id in self.settings.get("rw_covers") or []:
            rt = self._rt.get(entity_id) or {}
            cfg = self.covers.get(entity_id) or {}
            prof = self.profile(entity_id)
            up, down = self._windows(prof)
            info = rt.get("shade_info") or {}
            contacts = self.contacts(entity_id)
            room = self.room_of(entity_id)
            covers[entity_id] = {
                "area": self._area(entity_id),
                "profile": cfg.get("profile") or "standard",
                "target": rt.get("target"), "reason": rt.get("reason"), "cat": rt.get("cat"),
                "day": rt.get("day"), "shading": bool(rt.get("shading")),
                "shade_start": info.get("start"), "shade_end": info.get("end"),
                "blocked": rt.get("blocked"),
                "manual": bool(rt.get("manual_at")),
                "contact_open": any(self._contact(e) for e in contacts[0]),
                "contact_tilted": any(self._contact(e) for e in contacts[1]),
                "contacts": {"open": contacts[0], "tilted": contacts[1], "src": contacts[2]},
                "room": {"id": room[0], "name": (room[1] or {}).get("name"), "auto": room[2]} if room[0] else None,
                "room_temp": self.room_temp(entity_id),
                "resident": self._on(prof.get("resident_sensor")) if prof.get("resident_sensor") else None,
                "up": [hm(up[0]), hm(up[1])] if up else None,
                "down": [hm(down[0]), hm(down[1])] if down else None,
                "opened_today": rt.get("opened_on") == dt_util.now().date().isoformat(),
                "next": self.next_event(timelines.get(cfg.get("profile") or "standard") or {}, now_min) if cfg.get("auto", True) else None,
            }
        return {
            "covers": covers,
            "sun": {"azimuth": azimuth, "elevation": elevation},
            "gust": self._gust, "storm": self._storm,
            "storm_kmh": self.haus.settings.get("storm_kmh") or 70,
            "free_day": self._free_day(),
            "forecast": self._fc,
            "timelines": {pid: {k: v for k, v in tl.items() if not k.endswith("_min")} for pid, tl in timelines.items()},
            "away": bool(getattr(self.haus, "away", False)), "vacation": bool(getattr(self.haus, "vacation", False)),
        }
