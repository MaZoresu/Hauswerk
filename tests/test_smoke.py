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
REG: dict[str, object] = {}  # Entitäten-Register: entity_id -> Eintrag mit device_id
DEVS: dict[str, object] = {}  # Geräte-Register: device_id -> Eintrag mit model


class Context:
    _n = 0

    def __init__(self, user_id=None, parent_id=None):
        Context._n += 1
        self.id, self.user_id, self.parent_id = f"ctx{Context._n}", user_id, parent_id


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
    _mod("homeassistant.const", STATE_HOME="home", STATE_UNAVAILABLE="unavailable", STATE_UNKNOWN="unknown",
         EVENT_CALL_SERVICE="call_service")
    _mod("homeassistant.core", Event=object, HomeAssistant=object, Context=Context, callback=lambda f: f)
    helpers = _mod("homeassistant.helpers")
    helpers.device_registry = _mod("homeassistant.helpers.device_registry",
                                   async_get=lambda hass: types.SimpleNamespace(async_get=DEVS.get))
    helpers.entity_registry = _mod("homeassistant.helpers.entity_registry",
         async_get=lambda hass: types.SimpleNamespace(async_get=REG.get),
         async_entries_for_device=lambda r, d: [e for e in REG.values() if e.device_id == d])
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
        self.context = Context()


class Hass:
    def __init__(self):
        self.data = {}
        self.st = {}
        self.calls = []
        self.states = types.SimpleNamespace(
            get=self.st.get, async_entity_ids=lambda domain: [e for e in self.st if e.startswith(f"{domain}.")],
            async_all=lambda domain=None: [s for e, s in self.st.items() if domain is None or e.startswith(f"{domain}.")])
        self.services = types.SimpleNamespace(async_call=self._call)
        self.listeners = []
        self.bus = types.SimpleNamespace(async_listen=lambda ev, cb: self.listeners.append(cb) or (lambda: None))
        self.forecast = None

    async def _call(self, domain, service, data, **kw):
        self.calls.append((domain, service, data))
        ctx = kw.get("context") or Context()
        for cb in self.listeners:
            cb(types.SimpleNamespace(data={"domain": domain, "service": service, "service_data": data}, context=ctx))
        if (domain, service) == ("weather", "get_forecasts"):
            return {data["entity_id"]: {"forecast": self.forecast or []}}
        return None

    def async_create_task(self, coro):
        return asyncio.ensure_future(coro)

    def sent(self):
        """Gesendete Nachrichten (Titel)."""
        return [d["title"] for dom, _s, d in self.calls if dom == "notify"]

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


def _reg(entity_id, device_id, device_class=None):
    REG[entity_id] = types.SimpleNamespace(entity_id=entity_id, device_id=device_id, domain=entity_id.split(".")[0],
                                           disabled_by=None, device_class=device_class, original_device_class=device_class)


def test_nachrichten_batterie_ruhezeit(hw):
    """Fenster lange offen, Batterie schwach, Thermostat weg, Frost – einmal senden, Ruhezeit hält zurück."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 11, 16, 7, 0, tzinfo=timezone.utc)
        hass = Hass()
        hass.set("climate.wz", "heat", {"current_temperature": 20.0, "temperature": 21.0}, "Thermostat Wohnzimmer")
        hass.set("sensor.wz_batterie", "12", {"device_class": "battery", "unit_of_measurement": "%"}, "Thermostat Batterie")
        hass.set("binary_sensor.fenster", "on", name="Fenster Wohnzimmer")
        hass.st["binary_sensor.fenster"].last_changed = NOW[0] - timedelta(minutes=40)
        hass.set("weather.home", "cloudy", {"temperature": 3.0, "humidity": 85})
        hass.forecast = [{"datetime": "2026-11-17", "temperature": 2.0, "templow": -4.5}]
        _reg("climate.wz", "d1")
        _reg("sensor.wz_batterie", "d1", "battery")
        log, haus, ctl = await _setup(hw, hass)
        await haus.async_save_settings({"notify_targets": ["mobile_app_pixel"], "notify_quiet": False})
        await ctl.async_save_room({"id": "wz", "name": "Wohnzimmer", "type": "heizkoerper", "comfort": 21, "eco": 18,
                                   "climates": ["climate.wz"], "windows": ["binary_sensor.fenster"], "enabled": True,
                                   "schedule": []})
        await haus._async_refresh_forecast(force=True)
        await ctl.async_evaluate()
        await asyncio.sleep(0)
        first = hass.sent()
        assert "Fenster lange offen" in first and "Batterie schwach" in first and "Frost erwartet" in first
        assert ctl.status()["rooms"]["wz"]["battery_low"][0]["level"] == 12
        # nicht doppelt
        await ctl.async_evaluate()
        await asyncio.sleep(0)
        assert hass.sent() == first
        # Fenster zu -> erledigt; Thermostat fällt aus (seit 20 Min.)
        hass.set("binary_sensor.fenster", "off", name="Fenster Wohnzimmer")
        hass.set("climate.wz", "unavailable", name="Thermostat Wohnzimmer")
        hass.st["climate.wz"].last_changed = NOW[0] - timedelta(minutes=20)
        # Ruhezeit den ganzen Tag: zurückhalten
        await haus.async_save_settings({"notify_quiet": True, "notify_quiet_from": "00:00", "notify_quiet_to": "23:59"})
        await ctl.async_evaluate()
        await asyncio.sleep(0)
        assert "Thermostat nicht erreichbar" not in hass.sent()
        assert haus.status()["notify_queued"] == 1
        # Ruhezeit vorbei: senden, weil der Anlass noch besteht
        await haus.async_save_settings({"notify_quiet": False})
        haus._flush_queue()
        await asyncio.sleep(0)
        assert hass.sent().count("Thermostat nicht erreichbar") == 1
        return log

    log = asyncio.run(run())
    notes = [e for e in log.entries if e["cat"] == "notify"]
    assert any("Ruhezeit" in e.get("why", "") for e in notes)
    assert any("nach der Ruhezeit" in e.get("why", "") for e in notes)


def test_fenster_erkennung_duschen_feiertag_wetter(hw):
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 11, 18, 5, 0, tzinfo=timezone.utc)  # Mittwoch 06:00 lokal
        hass = Hass()
        hass.set("climate.bad", "heat", {"current_temperature": 21.0, "temperature": 21.0}, "Thermostat Bad")
        hass.set("sensor.bad_t", "21.0", name="Bad Temperatur")
        hass.set("sensor.bad_h", "55", name="Bad Feuchte")
        hass.set("binary_sensor.arbeitstag", "off", name="Arbeitstag")  # Feiertag
        hass.set("sensor.aussen", "-5.0", name="Außen")
        log, haus, ctl = await _setup(hw, hass)
        await haus.async_save_settings({"outside_sensor": "sensor.aussen",
                                        "workday_entity": "binary_sensor.arbeitstag", "workday_as": 6})
        await ctl.async_save_settings({"preheat_weather": True, "preheat_mode": "fixed", "lead_radiator": 20})
        # Werktags 05:30–08:00, sonntags erst ab 09:00
        await ctl.async_save_room({"id": "bad", "name": "Bad", "type": "heizkoerper", "comfort": 22, "eco": 18,
                                   "climates": ["climate.bad"], "windows": [], "temp_sensor": "sensor.bad_t",
                                   "humidity_sensor": "sensor.bad_h", "enabled": True,
                                   "window_detect": True, "shower_boost": 20,
                                   "schedule": [{"days": [0, 1, 2, 3, 4], "start": "05:30", "end": "08:00"},
                                                {"days": [5, 6], "start": "09:00", "end": "22:00"}]})
        res = ctl.status()["rooms"]["bad"]
        assert res["holiday"] is True and res["mode"] == "eco"  # Feiertag: Sonntagsplan, noch keine Komfortzeit
        assert res["preheat_factor"] == 1.4 and res["preheat_lead"] == 28  # -5 °C außen: 20 Min. × 1,4
        # Duschen: Feuchte steigt in 10 Min. um 20 Punkte
        NOW[0] += timedelta(minutes=10)
        hass.set("sensor.bad_h", "75", name="Bad Feuchte")
        await ctl.async_evaluate()
        res = ctl.status()["rooms"]["bad"]
        assert res["shower"] is True and res["target"] == 22
        # Fenster ohne Kontakt: Temperatur fällt in 3 Min. um 1,5 °C
        NOW[0] += timedelta(minutes=3)
        hass.set("sensor.bad_t", "19.5", name="Bad Temperatur")
        await ctl.async_evaluate()
        res = ctl.status()["rooms"]["bad"]
        assert res["window_virtual"] is True and res["mode"] == "fenster"
        NOW[0] += timedelta(minutes=16)
        await ctl.async_evaluate()
        assert ctl.status()["rooms"]["bad"]["window_virtual"] is False
        return log

    log = asyncio.run(run())
    titles = [e["title"] for e in log.entries]
    assert any(t.startswith("Nach dem Duschen") for t in titles)
    assert "Fensterpause beginnt" in titles and "Fensterpause endet" in titles
    assert any("vermutlich offen" in (e.get("why") or "") for e in log.entries)


def test_benachrichtigungsart(hw):
    """Nur Protokoll, Wichtig (auch in der Ruhezeit, mit Priorität) und Mitteilung in Home Assistant."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 11, 16, 7, 0, tzinfo=timezone.utc)
        hass = Hass()
        log, haus, ctl = await _setup(hw, hass)
        await haus.async_save_settings({"notify_targets": ["mobile_app_pixel"], "notify_ha": True, "notify_quiet": True,
                                        "notify_quiet_from": "00:00", "notify_quiet_to": "23:59",
                                        "notify_window": "log", "notify_frost": "important", "notify_battery": False})
        assert haus.notify_mode("battery") == "off" and haus.notify_mode("offline") == "normal"
        haus.notify("window:x", "window", "Fenster lange offen", "Bad: 31 Min.")
        haus.notify("frost", "frost", "Frost erwartet", "Tiefstwert -3,0 °C")
        haus.notify("battery:x", "battery", "Batterie schwach", "12 %")
        await asyncio.sleep(0)
        pushes = [(s, d) for dom, s, d in hass.calls if dom == "notify"]
        assert [d["title"] for _s, d in pushes] == ["Frost erwartet"]  # Fenster nur Protokoll, Batterie aus
        assert pushes[0][1]["data"]["push"]["interruption-level"] == "time-sensitive"
        created = [d for dom, s, d in hass.calls if (dom, s) == ("persistent_notification", "create")]
        assert created and created[0]["notification_id"] == "hauswerk_frost"
        haus.clear("frost")
        await asyncio.sleep(0)
        assert ("persistent_notification", "dismiss", {"notification_id": "hauswerk_frost"}) in hass.calls
        return log

    log = asyncio.run(run())
    whys = [e.get("why", "") for e in log.entries if e["cat"] == "notify"]
    assert any("nur Protokoll" in w for w in whys) and any("wichtig gesendet" in w for w in whys)


def test_feiertage_wandern_in_den_kern(hw):
    """0.19 speicherte die Feiertage bei Heizwerk; ab 0.20 gehören sie zum Kern (Anwesenheit)."""
    async def run():
        STORES.clear()
        STORES[hw.const.HOUSE_STORAGE_KEY] = {"settings": {"persons": ["person.jens"]}}
        STORES[hw.const.STORAGE_KEY] = {"settings": {"frost_temp": 6.5, "workday_entity": "binary_sensor.arbeitstag",
                                                     "workday_as": 5}, "rooms": {}}
        _, haus, ctl = await _setup(hw, Hass())
        return haus, ctl

    haus, ctl = asyncio.run(run())
    assert haus.settings["workday_entity"] == "binary_sensor.arbeitstag" and haus.settings["workday_as"] == 5
    assert haus.settings["persons"] == ["person.jens"]
    assert "workday_entity" not in ctl.settings and ctl.settings["frost_temp"] == 6.5
    assert "workday_entity" not in STORES[hw.const.STORAGE_KEY]["settings"]


def test_zweite_regelung_kopplung_und_funk(hw):
    """Andere Regelung erkennen, Wandthermostat/Heizkörper koppeln, bei vollem Funk drosseln."""
    async def run():
        STORES.clear()
        REG.clear()
        DEVS.clear()
        NOW[0] = datetime(2026, 11, 16, 7, 0, tzinfo=timezone.utc)  # 08:00 lokal
        hass = Hass()
        hass.set("climate.wth", "heat", {"current_temperature": 20.0, "temperature": 18.0, "model": "HmIP-WTH-2"}, "WTH Wohnzimmer")
        hass.set("climate.trv", "heat", {"current_temperature": 20.0, "temperature": 18.0, "model": "HMIP-eTRV"}, "Heizkörper Wohnzimmer")
        hass.set("climate.fremd", "heat", {"settings": {"trv": "climate.wth"}}, "Raumklima Wohnzimmer")
        hass.set("sensor.ccu_duty_cycle_level", "22", {"unit_of_measurement": "%"}, "CCU Duty Cycle")
        hass.set("binary_sensor.wth_duty_cycle", "off")
        REG["climate.wth"] = types.SimpleNamespace(entity_id="climate.wth", device_id="dw", domain="climate", disabled_by=None, platform="homematicip_local")
        REG["binary_sensor.wth_duty_cycle"] = types.SimpleNamespace(entity_id="binary_sensor.wth_duty_cycle", device_id="dw", domain="binary_sensor", disabled_by=None)
        REG["climate.fremd"] = types.SimpleNamespace(entity_id="climate.fremd", device_id=None, domain="climate", disabled_by=None, platform="raumklima")
        log, haus, ctl = await _setup(hw, hass)
        await ctl.async_start()
        await ctl.async_save_room({"id": "wz", "name": "Wohnzimmer", "comfort": 21, "eco": 18, "enabled": True,
                                   "climates": ["climate.wth", "climate.trv"],
                                   "schedule": [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "08:00", "end": "22:00"}]})
        await ctl.async_evaluate()
        res = ctl.status()["rooms"]["wz"]
        # 1. Andere Regelung nennt unser Wandthermostat
        assert res["conflicts"] and "raumklima" in res["conflicts"][0]["by"][0]
        # 2. Nur das Wandthermostat wird gestellt
        assert res["followers"] == ["climate.trv"]
        temps = [d["entity_id"] for dom, s, d in hass.calls if s == "set_temperature"]
        assert set(temps) == {"climate.wth"}
        # eigene Befehle zählen nicht als fremd
        assert not ctl._foreign.get("climate.wth")
        # fremde Befehle (Automation/Integration) werden gezählt
        for _ in range(3):
            ctl._on_service_call(types.SimpleNamespace(
                data={"domain": "climate", "service": "set_temperature", "service_data": {"entity_id": "climate.trv", "temperature": 19}},
                context=Context()))
        await ctl.async_evaluate()
        res = ctl.status()["rooms"]["wz"]
        assert any(c["id"] == "climate.trv" and "andere Integration" in c["by"] for c in res["conflicts"])
        # Heizkörper folgt nicht: nach 15 Min. stellt Hauswerk es wieder selbst
        hass.set("climate.wth", "heat", {"current_temperature": 20.0, "temperature": 21.0, "model": "HmIP-WTH-2"}, "WTH Wohnzimmer")
        hass.set("climate.trv", "heat", {"current_temperature": 20.0, "temperature": 18.0, "model": "HMIP-eTRV"}, "Heizkörper Wohnzimmer")
        await ctl.async_evaluate()
        NOW[0] += timedelta(minutes=16)
        await ctl.async_evaluate()
        res = ctl.status()["rooms"]["wz"]
        assert res["followers"] == [] and res["pair_broken"] == ["climate.trv"]
        assert any(d.get("entity_id") == "climate.trv" for dom, s, d in hass.calls if s == "set_temperature")
        # 3. Funk ausgelastet: kleine Änderungen werden nicht gesendet; Gerät mit Duty-Cycle-Sperre gar nicht
        hass.set("sensor.ccu_duty_cycle_level", "85", {"unit_of_measurement": "%"}, "CCU Duty Cycle")
        await ctl.async_evaluate()
        assert haus.radio_busy and ctl.status()["radio"]["level"] == 85
        hass.set("binary_sensor.wth_duty_cycle", "on")
        n = len(hass.calls)
        hass.set("climate.wth", "heat", {"current_temperature": 20.0, "temperature": 18.0, "model": "HmIP-WTH-2"}, "WTH Wohnzimmer")
        await ctl.async_evaluate()
        assert not [d for dom, s, d in hass.calls[n:] if d.get("entity_id") == "climate.wth"]
        assert ctl.status()["rooms"]["wz"]["duty_blocked"] == ["climate.wth"]
        await ctl.async_stop()
        return log

    log = asyncio.run(run())
    titles = [e["title"] for e in log.entries]
    assert "Funk ausgelastet – Befehle werden gedrosselt" in titles
    assert any(t.startswith("Zweite Regelung") for t in titles)
    assert "Wandthermostat stellt die Heizkörper" in titles
    assert "Heizkörper Wohnzimmer folgt dem Wandthermostat nicht" in titles
