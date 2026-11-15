"""Rauchtest für Kern, Heizwerk und Protokoll mit nachgebauten Home-Assistant-Modulen.

Home Assistant muss dafür nicht installiert sein: die benötigten Teile werden hier durch kleine
Attrappen ersetzt. Geprüft werden Abläufe (Anwesenheit, Fenster, Ausfall, Boost, Einstellungen,
Urlaub) und die Übernahme alter Einstellungen in den Hauswerk-Kern.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import importlib
from pathlib import Path
import shutil
import sys
import types

import pytest

SRC = Path(__file__).resolve().parents[1] / "custom_components" / "hauswerk"
TZ = timezone(timedelta(hours=1))
NOW = [datetime(2026, 11, 16, 7, 0, tzinfo=timezone.utc)]
STORES: dict[str, object] = {}  # Speicher je Schlüssel (wie .storage/ in Home Assistant)


class Store:
    def __init__(self, hass, version, key):
        self.key = key

    async def async_load(self):
        return STORES.get(self.key)

    async def async_save(self, data):
        STORES[self.key] = data

    def async_delay_save(self, fn, delay=0):
        STORES[self.key] = fn()


def _mod(name, **attrs):
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    sys.modules[name] = m
    return m


def _stub_homeassistant():
    noop = lambda *a, **k: (lambda: None)  # noqa: E731
    _mod("homeassistant")
    _mod("homeassistant.config_entries", ConfigEntry=object)
    _mod("homeassistant.const", STATE_HOME="home", STATE_UNAVAILABLE="unavailable", STATE_UNKNOWN="unknown")
    _mod("homeassistant.core", Event=object, HomeAssistant=object, callback=lambda f: f)
    _mod("homeassistant.helpers")
    _mod("homeassistant.helpers.entity_registry",
         async_get=lambda hass: types.SimpleNamespace(async_get=lambda e: None),
         async_entries_for_device=lambda r, d: [])
    _mod("homeassistant.helpers.dispatcher", async_dispatcher_send=lambda *a: None)
    _mod("homeassistant.helpers.event", async_call_later=noop, async_track_state_change_event=noop,
         async_track_time_interval=noop)
    _mod("homeassistant.helpers.storage", Store=Store)
    _mod("homeassistant.util")
    dt = _mod(
        "homeassistant.util.dt",
        utcnow=lambda: NOW[0],
        now=lambda: NOW[0].astimezone(TZ),
        as_local=lambda d: d.astimezone(TZ),
        utc_from_timestamp=lambda ts: datetime.fromtimestamp(ts, timezone.utc),
        parse_datetime=lambda s: datetime.fromisoformat(s),
        parse_date=lambda s: datetime.fromisoformat(s).date(),
        start_of_local_day=lambda d=None: NOW[0].astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0),
        get_default_time_zone=lambda: TZ,
    )
    sys.modules["homeassistant.util"].dt = dt


@pytest.fixture(scope="module")
def hw(tmp_path_factory):
    """Die Module als Paket „hw“ laden (ohne __init__.py der Integration, die Home Assistant braucht)."""
    _stub_homeassistant()
    root = tmp_path_factory.mktemp("pkg")
    pkg = root / "hw"
    pkg.mkdir()
    for name in ("controller.py", "core.py", "logic.py", "const.py", "log.py"):
        shutil.copy(SRC / name, pkg / name)
    (pkg / "__init__.py").write_text("")
    sys.path.insert(0, str(root))
    return types.SimpleNamespace(
        Heizen=importlib.import_module("hw.controller").Heizen,
        Haus=importlib.import_module("hw.core").Haus,
        Protokoll=importlib.import_module("hw.log").Protokoll,
        const=importlib.import_module("hw.const"),
    )


class State:
    def __init__(self, entity_id, state, attributes=None, name=None):
        self.entity_id, self.state, self.attributes = entity_id, state, attributes or {}
        self.name = name or entity_id
        self.last_changed = NOW[0]
        self.context = types.SimpleNamespace(user_id=None)


class Hass:
    def __init__(self):
        self.data = {}
        self.st = {}
        self.calls = []
        self.states = types.SimpleNamespace(get=self.st.get)
        self.services = types.SimpleNamespace(async_call=self._call)

    async def _call(self, domain, service, data, **kw):
        self.calls.append((domain, service, data))

    def set(self, eid, state, attrs=None, name=None):
        self.st[eid] = State(eid, state, attrs, name)

    def change(self, ctl, eid, state, attrs=None, name=None):
        old = self.st.get(eid)
        self.set(eid, state, attrs, name)
        ctl._on_state_change(types.SimpleNamespace(data={"entity_id": eid, "old_state": old, "new_state": self.st[eid]}))


async def _setup(hw, hass):
    """Wie __init__.py: Protokoll, Kern, Heizwerk; Kern übernimmt alte Einstellungen."""
    log = hw.Protokoll(hass)
    await log.async_load()
    haus = hw.Haus(hass, log)
    ctl = hw.Heizen(hass, None, log, haus)
    await ctl.async_load()
    await haus.async_load(legacy=ctl.loaded_settings)
    ctl.drop_house_settings()
    return log, haus, ctl


def test_ablauf(hw):
    async def run():
        STORES.clear()
        NOW[0] = datetime(2026, 11, 16, 7, 0, tzinfo=timezone.utc)
        hass = Hass()
        hass.set("person.jens", "home", name="Jens")
        hass.set("climate.wz", "heat", {"current_temperature": 19.0, "temperature": 18.0, "target_temp_step": 0.5},
                 "Thermostat Wohnzimmer")
        hass.set("binary_sensor.fenster", "off", name="Fenster Wohnzimmer")
        log, haus, ctl = await _setup(hw, hass)
        await haus.async_save_settings({"persons": ["person.jens"], "away_delay": 0}, by="Jens")
        await ctl.async_save_room({"id": "wz", "name": "Wohnzimmer", "type": "heizkoerper", "comfort": 21, "eco": 18,
                                   "climates": ["climate.wz"], "windows": ["binary_sensor.fenster"], "enabled": True,
                                   "schedule": [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "08:00", "end": "22:00"}]},
                                  by="Jens")
        await ctl.async_evaluate()  # 08:00 lokal -> Komfort
        assert not haus.away

        # Fenster auf und wieder zu
        hass.change(ctl, "binary_sensor.fenster", "on", name="Fenster Wohnzimmer")
        NOW[0] += timedelta(seconds=90)
        await ctl.async_evaluate()
        hass.change(ctl, "binary_sensor.fenster", "off", name="Fenster Wohnzimmer")
        NOW[0] += timedelta(minutes=5)
        await ctl.async_evaluate()

        # Person geht -> abwesend (Kern), Heizwerk regelt danach
        hass.set("person.jens", "not_home", name="Jens")
        NOW[0] += timedelta(minutes=1)
        await ctl.async_evaluate()
        assert haus.away
        assert ctl.status()["away"] is True

        # Thermostat fällt aus und kommt zurück
        hass.change(ctl, "climate.wz", "unavailable", name="Thermostat Wohnzimmer")
        hass.set("climate.wz", "heat", {"current_temperature": 19.0, "temperature": 18.0}, "Thermostat Wohnzimmer")

        # Boost, Einstellungen beider Teile, Urlaub per Schalter (Kern)
        await ctl.async_set_override("wz", None, None, boost=True, by="Jens")
        await ctl.async_save_settings({"frost_temp": 8.0, "look_accent": "#f59e0b"}, by="Jens")
        assert ctl.settings["frost_temp"] == 8.0
        assert "look_accent" not in ctl.settings  # gehört zum Kern, nicht zu Heizwerk
        await haus.async_save_settings({"vacation": True})
        await ctl.async_evaluate()
        assert haus.vacation and ctl.status()["vacation"] is True
        await ctl.async_stop()
        await haus.async_stop()
        return log

    log = asyncio.run(run())
    cats = {e["cat"] for e in log.entries}
    assert {"presence", "target", "window", "manual", "health", "command", "settings"} <= cats
    titles = [e["title"] for e in log.entries]
    assert "Niemand mehr zu Hause – abwesend" in titles
    assert "Urlaub an" in titles and "Urlaub beginnt" in titles


def test_uebernahme_aus_heizwerk(hw):
    """Erster Start nach dem Update: zentrale Einstellungen wandern aus dem Heizwerk-Speicher in den Kern."""
    async def run():
        STORES.clear()
        STORES[hw.const.LEGACY_STORAGE_KEY] = {
            "settings": {"persons": ["person.jens"], "proximity_km": 0.8, "look_theme": "dark", "frost_temp": 6.0,
                         "vacation": True},
            "rooms": {},
        }
        hass = Hass()
        _, haus, ctl = await _setup(hw, hass)
        return haus, ctl

    haus, ctl = asyncio.run(run())
    assert haus.settings["persons"] == ["person.jens"]
    assert haus.settings["proximity_m"] == 800
    assert haus.settings["look_theme"] == "dark" and haus.settings["vacation"] is True
    assert "proximity_km" not in haus.settings
    assert ctl.settings["frost_temp"] == 6.0
    saved_heat = STORES[hw.const.STORAGE_KEY]["settings"]
    assert not set(saved_heat) & hw.const.HOUSE_KEYS  # Heizwerk speichert keine zentralen Einstellungen mehr
    assert STORES[hw.const.HOUSE_STORAGE_KEY]["settings"]["home_zone"] == "zone.home"


def test_einstellungen_getrennt(hw):
    assert not set(hw.const.HOUSE_DEFAULTS) & set(hw.const.HEAT_DEFAULTS)
    assert hw.const.DEFAULT_SETTINGS == {**hw.const.HOUSE_DEFAULTS, **hw.const.HEAT_DEFAULTS}
