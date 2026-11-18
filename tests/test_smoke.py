"""Rauchtest für Kern, Heizwerk und Protokoll mit nachgebauten Home-Assistant-Modulen.

Home Assistant muss dafür nicht installiert sein: die benötigten Teile werden hier durch kleine
Attrappen ersetzt. Geprüft werden Abläufe (Anwesenheit, Fenster, Ausfall, Boost, Einstellungen,
Urlaub) und die Übernahme alter Einstellungen in den Hauswerk-Kern.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
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
         async_get=lambda hass: types.SimpleNamespace(async_get=REG.get), EVENT_ENTITY_REGISTRY_UPDATED="entity_registry_updated",
         async_entries_for_device=lambda r, d: [e for e in REG.values() if e.device_id == d],
         async_entries_for_config_entry=lambda r, c: [e for e in REG.values() if getattr(e, "config_entry_id", None) == c])
    helpers.area_registry = _mod("homeassistant.helpers.area_registry",
                                 async_get=lambda hass: types.SimpleNamespace(async_get_area=lambda a: None))
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
        start_of_local_day=lambda d=None: (datetime(d.year, d.month, d.day, tzinfo=TZ) if d else NOW[0].astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)),
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
    _mod("homeassistant.config_entries", ConfigEntry=object)
    for name in ("controller.py", "core.py", "logic.py", "const.py", "log.py", "rollwerk.py", "kraftwerk.py", "rename.py"):
        shutil.copy(SRC / name, pkg / name)
    (pkg / "__init__.py").write_text("")
    sys.path.insert(0, str(root))
    return types.SimpleNamespace(
        Heizen=importlib.import_module("hw.controller").Heizen,
        Haus=importlib.import_module("hw.core").Haus,
        Protokoll=importlib.import_module("hw.log").Protokoll,
        Rollwerk=importlib.import_module("hw.rollwerk").Rollwerk,
        rename=importlib.import_module("hw.rename"),
        Kraftwerk=importlib.import_module("hw.kraftwerk").Kraftwerk,
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
        if (domain, service) == ("calendar", "get_events"):
            return {data["entity_id"]: {"events": getattr(self, "events", {}).get(data["entity_id"], [])}}
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


def test_heimweg_nur_wer_naeher_kommt(hw):
    """Steht jemand in der Nähe (Arbeit um die Ecke), greift die Abwesenheit trotzdem; nur wer näher kommt, zählt."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 11, 17, 7, 0, tzinfo=timezone.utc)
        hass = Hass()
        hass.set("person.julia", "not_home", name="Julia")
        hass.set("sensor.home_2_entfernung_von_julia", "322", {"unit_of_measurement": "m"}, "Entfernung Julia")
        hass.set("sensor.home_entfernung_von_jens", "60806", {"unit_of_measurement": "m"}, "Entfernung Jens")
        log, haus, ctl = await _setup(hw, hass)
        await haus.async_save_settings({"persons": ["person.julia"], "away_delay": 0, "proximity_m": 1000,
                                        "proximity_sensors": ["sensor.home_2_entfernung_von_julia", "sensor.home_entfernung_von_jens"]})
        out = {}
        # 1) ohne Bewegungs-Sensor: Abstand bleibt gleich -> abwesend
        NOW[0] += timedelta(minutes=1)
        haus.update()
        haus.update()
        out["steht"] = (haus.away, haus.approaching)
        # 2) Abstand wird kleiner -> auf dem Heimweg, nach 15 Minuten ohne Annäherung wieder abwesend
        hass.set("sensor.home_2_entfernung_von_julia", "200", {"unit_of_measurement": "m"}, "Entfernung Julia")
        haus.update()
        out["kommt"] = (haus.away, haus.approaching)
        NOW[0] += timedelta(minutes=16)
        haus.update()
        out["steht_wieder"] = (haus.away, haus.approaching)
        # 3) mit Bewegungs-Sensor der Integration „Nähe“ (gleiches Gerät)
        REG["sensor.home_2_entfernung_von_julia"] = types.SimpleNamespace(
            entity_id="sensor.home_2_entfernung_von_julia", device_id="prox2", unique_id="abc_person.julia_dist_to_zone")
        REG["sensor.home_2_bewegung_von_julia"] = types.SimpleNamespace(
            entity_id="sensor.home_2_bewegung_von_julia", device_id="prox2", unique_id="abc_person.julia_dir_of_travel")
        haus._dir_ids.clear()
        hass.set("sensor.home_2_bewegung_von_julia", "stationary")
        hass.set("sensor.home_2_entfernung_von_julia", "150", {"unit_of_measurement": "m"}, "Entfernung Julia")
        haus.update()
        out["richtung_steht"] = (haus.away, haus.approaching)
        hass.set("sensor.home_2_bewegung_von_julia", "towards")
        haus.update()
        out["richtung_kommt"] = (haus.away, haus.approaching)
        return out

    out = asyncio.run(run())
    assert out["steht"] == (True, False)
    assert out["kommt"] == (False, True)
    assert out["steht_wieder"] == (True, False)
    assert out["richtung_steht"] == (True, False), "näher geworden, aber Nähe sagt „stationär“"
    assert out["richtung_kommt"] == (False, True)


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


def test_mischbetrieb(hw):
    """Fußbodenheizung über das Wandthermostat, ein Heizkörper in der Gruppe, einer als Zusatzheizung."""
    async def run():
        STORES.clear()
        REG.clear()
        DEVS.clear()
        NOW[0] = datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc)  # 10:00 lokal, Komfort
        hass = Hass()
        hass.set("climate.wth", "heat", {"current_temperature": 20.8, "temperature": 21.0, "model": "HmIP-WTH-2"}, "WTH Bad")
        hass.set("climate.trv_gruppe", "heat", {"current_temperature": 23.0, "temperature": 21.0, "model": "HMIP-eTRV"}, "Heizkörper Gruppe")
        hass.set("climate.trv_zusatz", "heat", {"current_temperature": 22.5, "temperature": 21.0, "model": "HMIP-eTRV"}, "Heizkörper Zusatz")
        log, haus, ctl = await _setup(hw, hass)
        await ctl.async_save_room({"id": "bad", "name": "Bad", "comfort": 21, "eco": 18, "enabled": True, "type": "flaeche",
                                   "climates": ["climate.wth", "climate.trv_gruppe", "climate.trv_zusatz"],
                                   "assist_entities": ["climate.trv_zusatz"], "assist_diff": 0.5,
                                   "schedule": [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "06:00", "end": "22:00"}]})
        res = ctl.status()["rooms"]["bad"]
        # Raumtemperatur ohne die Heizkörper (nur Wandthermostat)
        assert res["room_temp"] == 20.8
        # Heizkörper in der Gruppe folgt, Zusatz-Heizkörper ist zu (nur 0,2 °C unter Soll)
        assert res["followers"] == ["climate.trv_gruppe"]
        assert res["assist"]["on"] is False
        sent = {d["entity_id"]: d["temperature"] for dom, s, d in hass.calls if s == "set_temperature"}
        assert sent == {"climate.trv_zusatz": 7.0}
        # Raum kühlt aus: Zusatz-Heizkörper hilft, um seinen Messfehler höher gestellt
        hass.set("climate.wth", "heat", {"current_temperature": 20.4, "temperature": 21.0, "model": "HmIP-WTH-2"}, "WTH Bad")
        hass.set("climate.trv_zusatz", "heat", {"current_temperature": 21.4, "temperature": 7.0, "model": "HMIP-eTRV"}, "Heizkörper Zusatz")
        await ctl.async_evaluate()
        res = ctl.status()["rooms"]["bad"]
        assert res["assist"]["on"] is True
        assert hass.calls[-1][2] == {"entity_id": "climate.trv_zusatz", "temperature": 22.0}
        # bis kurz vor Soll an, dann wieder zu
        hass.set("climate.wth", "heat", {"current_temperature": 20.95, "temperature": 21.0, "model": "HmIP-WTH-2"}, "WTH Bad")
        hass.set("climate.trv_zusatz", "heat", {"current_temperature": 22.0, "temperature": 22.0, "model": "HMIP-eTRV"}, "Heizkörper Zusatz")
        await ctl.async_evaluate()
        assert ctl.status()["rooms"]["bad"]["assist"]["on"] is False
        assert hass.calls[-1][2] == {"entity_id": "climate.trv_zusatz", "temperature": 7.0}
        return log

    log = asyncio.run(run())
    titles = [e["title"] for e in log.entries]
    assert "Heizkörper hilft nach" in titles and "Heizkörper aus – Fußbodenheizung allein" in titles


def test_rolle_selbst(hw):
    """Heizkörper mit Rolle „Selbst“ folgt nicht dem Wandthermostat, sondern wird direkt gestellt."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc)
        hass = Hass()
        hass.set("climate.wth", "heat", {"current_temperature": 20.0, "temperature": 18.0, "model": "HmIP-WTH-2"}, "WTH")
        hass.set("climate.trv", "heat", {"current_temperature": 20.0, "temperature": 18.0, "model": "HMIP-eTRV"}, "TRV")
        log, haus, ctl = await _setup(hw, hass)
        await ctl.async_save_room({"id": "k", "name": "Küche", "comfort": 21, "eco": 18, "enabled": True,
                                   "climates": ["climate.wth", "climate.trv"], "pair_exclude": ["climate.trv"],
                                   "schedule": [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "06:00", "end": "22:00"}]})
        assert ctl.status()["rooms"]["k"]["followers"] == []
        assert {d["entity_id"] for dom, s, d in hass.calls if s == "set_temperature"} == {"climate.wth", "climate.trv"}

    asyncio.run(run())


def test_ventil_kalt_und_waermeanforderung(hw):
    """Ventil aus Nachbar-Sensor, kalter Heizkörper, Wärmeanforderung an den Wärmeerzeuger, Ventil-Statistik."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc)  # Komfort
        hass = Hass()
        hass.set("climate.trv", "heat", {"current_temperature": 19.0, "temperature": 21.0}, "Heizkörper Küche")
        hass.set("sensor.trv_ventil_offnungsgrad", "100", {"unit_of_measurement": "%"}, "Ventil")
        hass.set("climate.vaillant", "auto", {"temperature": 22.5}, "Vaillant Zone")
        REG["climate.trv"] = types.SimpleNamespace(entity_id="climate.trv", device_id="dt", domain="climate", disabled_by=None)
        REG["sensor.trv_ventil_offnungsgrad"] = types.SimpleNamespace(entity_id="sensor.trv_ventil_offnungsgrad", device_id="dt", domain="sensor", disabled_by=None)
        log, haus, ctl = await _setup(hw, hass)
        await ctl.async_start()
        await ctl.async_save_settings({"demand_entity": "climate.vaillant", "demand_hold": 20})
        await ctl.async_save_room({"id": "k", "name": "Küche", "comfort": 21, "eco": 18, "enabled": True,
                                   "climates": ["climate.trv"],
                                   "schedule": [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "06:00", "end": "22:00"}]})
        res = ctl.status()["rooms"]["k"]
        assert res["valve"] == 100 and res["cold_radiator"] is None
        assert ctl.status()["demand"]["need"] == ["Küche"]
        # eine Stunde später: kaum wärmer -> kalt
        NOW[0] += timedelta(minutes=61)
        hass.set("climate.trv", "heat", {"current_temperature": 19.1, "temperature": 21.0}, "Heizkörper Küche")
        await ctl.async_evaluate()
        res = ctl.status()["rooms"]["k"]
        assert res["cold_radiator"]["minutes"] >= 60
        assert ctl.status()["cold_rooms"] == ["k"]
        ctl._record_stats()
        # Raum warm, Ventil zu: nach 20 Min. ohne Bedarf wird die Vaillant abgesenkt
        hass.set("climate.trv", "heat", {"current_temperature": 21.2, "temperature": 21.0}, "Heizkörper Küche")
        hass.set("sensor.trv_ventil_offnungsgrad", "0", {"unit_of_measurement": "%"}, "Ventil")
        await ctl.async_evaluate()
        assert ctl.status()["demand"].get("state") in (None, "normal")
        NOW[0] += timedelta(minutes=21)
        await ctl.async_evaluate()
        assert ctl.status()["demand"]["state"] == "low"
        assert ("climate", "set_temperature", {"entity_id": "climate.vaillant", "temperature": 17.0}) in hass.calls
        # wieder Bedarf: zurück auf die gemerkten 22,5 °C
        hass.set("climate.vaillant", "auto", {"temperature": 17.0}, "Vaillant Zone")
        hass.set("sensor.trv_ventil_offnungsgrad", "60", {"unit_of_measurement": "%"}, "Ventil")
        await ctl.async_evaluate()
        assert ctl.status()["demand"]["state"] == "normal"
        assert hass.calls[-1] == ("climate", "set_temperature", {"entity_id": "climate.vaillant", "temperature": 22.5})
        rep = ctl.report(1)["k"][0]
        assert rep["valve_avg"] == 100 and rep["valve_hours"][11] == 100
        await ctl.async_stop()
        return log

    log = asyncio.run(run())
    titles = [e["title"] for e in log.entries]
    assert "Heizkörper bleibt kalt" in titles
    assert any(t.startswith("Wärmeanforderung: keine") for t in titles)


def test_rollwerk(hw):
    """Profil wie CCA: Beschattung, abends zu, Aussperrschutz, Handbetrieb gesperrt, Sturm."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 7, 16, 18, 0, tzinfo=timezone.utc)  # 20:00 lokal, Donnerstag
        hass = Hass()
        feat = {"supported_features": 15}
        hass.set("cover.wz", "open", {"current_position": 100, **feat}, "Wohnzimmer")
        hass.set("cover.tuer", "open", {"current_position": 100, **feat}, "Terrassentür")
        hass.set("binary_sensor.tuer", "on", {}, "Terrassentür Kontakt")
        hass.set("weather.home", "sunny", {"temperature": 29, "wind_gust_speed": 20, "wind_speed_unit": "km/h"}, "Wetter")
        hass.set("sun.sun", "above_horizon", {"azimuth": 200, "elevation": 30}, "Sonne")
        log, haus, ctl = await _setup(hw, hass)
        rw = hw.Rollwerk(hass, log, haus)
        await rw.async_load()
        assert "standard" in rw.profiles
        await rw.async_start()  # Start: nichts fahren
        assert not [c for c in hass.calls if c[0] == "cover"]
        prof = dict(rw.profiles["standard"], features=["up", "down", "time", "shading", "ventilate"],
                    down_early="21:00", down_late="21:00", shade_start_and=["azimuth", "elevation", "temp2"],
                    shade_end_or=["azimuth", "elevation", "temp2"], temp2_min=25, shade_wait_start=0, delay_random=0,
                    pos_shading=30, manual_block=["opening", "closing", "shading"])
        await rw.async_save_profile("standard", prof)
        await rw.async_save_cover("cover.tuer", {"profile": "standard", "contact_open": "binary_sensor.tuer"})
        await rw.async_save_settings({"rw_covers": ["cover.wz", "cover.tuer"]})
        # 20:00, Sonne auf der Südseite, 29 °C: Wohnzimmer beschattet, Tür bleibt offen
        assert ("cover", "set_cover_position", {"entity_id": "cover.wz", "position": 30}) in hass.calls
        st = rw.status()["covers"]
        assert st["cover.wz"]["reason"] == "Beschattung" and st["cover.wz"]["shading"]
        assert ("cover", "set_cover_position", {"entity_id": "cover.tuer", "position": 30}) not in hass.calls
        # 21:01 Abend: Wohnzimmer zu; Tür offen -> Rollladen bleibt oben
        NOW[0] = datetime(2026, 7, 16, 20, 1, tzinfo=timezone.utc)
        hass.set("cover.wz", "open", {"current_position": 30, **feat}, "Wohnzimmer")
        await rw.async_evaluate()
        assert hass.calls[-1] == ("cover", "set_cover_position", {"entity_id": "cover.wz", "position": 0})
        assert "offen – nicht herunterfahren" in rw.status()["covers"]["cover.tuer"]["reason"]
        # Tür zu: jetzt fährt er
        hass.set("binary_sensor.tuer", "off", {}, "Terrassentür Kontakt")
        await rw.async_evaluate()
        assert hass.calls[-1] == ("cover", "set_cover_position", {"entity_id": "cover.tuer", "position": 0})
        # von Hand hochgefahren: bleibt so, Status zeigt Übersteuerung
        hass.set("cover.wz", "open", {"current_position": 100, **feat}, "Wohnzimmer")
        n = len(hass.calls)
        await rw.async_evaluate()
        assert len(hass.calls) == n and rw.status()["covers"]["cover.wz"]["manual"]
        # Automatik übernimmt wieder (Panel) -> mit manual_recover zurück auf zu
        await rw.async_save_profile("standard", dict(prof, manual_recover=True))
        await rw.async_command(["cover.wz"], "resume")
        assert hass.calls[-1] == ("cover", "set_cover_position", {"entity_id": "cover.wz", "position": 0})
        # Sturm: alle hoch
        hass.set("cover.tuer", "closed", {"current_position": 0, **feat}, "Terrassentür")
        hass.set("weather.home", "sunny", {"temperature": 20, "wind_gust_speed": 90, "wind_speed_unit": "km/h"}, "Wetter")
        await rw.async_evaluate()
        st = rw.status()
        assert st["storm"] and st["covers"]["cover.wz"]["target"] == 100
        assert hass.calls[-1] == ("cover", "set_cover_position", {"entity_id": "cover.tuer", "position": 100})
        # Profil löschen -> Rollläden fallen auf Standard zurück
        pid = await rw.async_save_profile(None, dict(prof, name="Süd"))
        await rw.async_save_cover("cover.wz", {"profile": pid})
        await rw.async_delete_profile(pid)
        assert rw.covers["cover.wz"]["profile"] == "standard"
        # auch „Standard“ ist löschbar, solange ein anderes Profil bleibt – Rollläden bekommen das Ersatzprofil
        pid = await rw.async_save_profile(None, dict(prof, name="Süd"))
        await rw.async_delete_profile("standard", pid)
        assert "standard" not in rw.profiles and rw.covers["cover.wz"]["profile"] == pid
        assert rw.profile("cover.wz")["name"] == "Süd"
        await rw.async_delete_profile(pid)  # das letzte Profil bleibt
        assert pid in rw.profiles
        return log

    log = asyncio.run(run())
    titles = [e["title"] for e in log.entries]
    assert "Sturmschutz: Rollläden hoch" in titles


def test_rollwerk_migration(hw):
    """Einstellungen aus 0.24 werden zu Profilen (je Fassade eins)."""
    async def run():
        STORES.clear()
        STORES["hauswerk.rollwerk"] = {"settings": {"rw_covers": ["cover.wz"], "rw_open_mode": "time", "rw_open_time": "06:45",
                                                    "rw_close_mode": "sun", "rw_shade": True, "rw_shade_temp": 26},
                                       "covers": {"cover.wz": {"facade": "S", "door": "binary_sensor.tuer", "storm": False}}}
        hass = Hass()
        log, haus, ctl = await _setup(hw, hass)
        rw = hw.Rollwerk(hass, log, haus)
        await rw.async_load()
        return rw

    rw = asyncio.run(run())
    assert rw.covers["cover.wz"] == {"profile": "fassade_s", "contact_open": "binary_sensor.tuer", "contact_tilted": None,
                                     "auto": True, "storm": False}
    p = rw.profiles["fassade_s"]
    assert p["azimuth_start"] == 120 and p["azimuth_end"] == 240 and p["temp2_min"] == 26
    assert "shading" in p["features"] and "sun" in p["features"] and p["up_early"] == "06:45"


def test_rollwerk_anwesenheit_und_tagesleiste(hw):
    """Niemand zu Hause (Hauswerk › Anwesenheit): tagsüber zu; Tagesleiste und „Als Nächstes“ ohne Sonnenbahn."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 7, 16, 9, 0, tzinfo=timezone.utc)  # 10:00 lokal, Donnerstag
        hass = Hass()
        hass.set("cover.wz", "open", {"current_position": 100, "supported_features": 15}, "Wohnzimmer")
        hass.set("sun.sun", "above_horizon", {"azimuth": 120, "elevation": 30}, "Sonne")
        log, haus, ctl = await _setup(hw, hass)
        rw = hw.Rollwerk(hass, log, haus)
        await rw.async_load()
        await rw.async_start()
        await rw.async_save_profile("standard", dict(rw.profiles["standard"], away_mode="closed", delay_random=0))
        await rw.async_save_settings({"rw_covers": ["cover.wz"]})
        haus.away = True
        await rw.async_evaluate()
        return rw, hass

    rw, hass = asyncio.run(run())
    assert hass.calls[-1] == ("cover", "set_cover_position", {"entity_id": "cover.wz", "position": 0})
    st = rw.status()
    assert st["covers"]["cover.wz"]["reason"] == "Niemand zu Hause – bleibt zu"
    tl = st["timelines"]["standard"]
    assert tl["open"] == "06:00" and tl["close"] == "16:00" and tl["shade"] == []
    assert st["covers"]["cover.wz"]["next"] == "16:00 schließt"


def test_rollwerk_raum_aus_heizwerk(hw):
    """Rollladen im selben Bereich wie ein Heizwerk-Raum: Fenster und Raumtemperatur kommen von dort."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 7, 16, 20, 1, tzinfo=timezone.utc)  # 21:01 lokal
        hass = Hass()
        for eid in ("cover.wz", "climate.wz", "binary_sensor.wz_fenster", "binary_sensor.wz_tuer"):
            REG[eid] = types.SimpleNamespace(entity_id=eid, device_id=None, area_id="wohnen", domain=eid.split(".")[0], disabled_by=None)
        hass.set("cover.wz", "open", {"current_position": 100, "supported_features": 15}, "Rollladen Wohnzimmer")
        hass.set("climate.wz", "heat", {"current_temperature": 23.5, "temperature": 21}, "Wandthermostat")
        hass.set("binary_sensor.wz_fenster", "on", {"device_class": "window"}, "Fenster Wohnzimmer")
        hass.set("binary_sensor.wz_tuer", "off", {"device_class": "door"}, "Terrassentür")
        hass.set("sun.sun", "below_horizon", {"azimuth": 300, "elevation": -5}, "Sonne")
        log, haus, ctl = await _setup(hw, hass)
        hass.data["hauswerk"] = {"heizen": ctl}
        await ctl.async_save_room({"id": "wz", "name": "Wohnzimmer", "type": "heizkoerper", "comfort": 21, "eco": 18,
                                   "climates": ["climate.wz"], "windows": ["binary_sensor.wz_fenster", "binary_sensor.wz_tuer"]})
        rw = hw.Rollwerk(hass, log, haus)
        await rw.async_load()
        await rw.async_start()
        await rw.async_save_profile("standard", dict(rw.profiles["standard"], features=["up", "down", "time", "ventilate"],
                                                     down_early="21:00", down_late="21:00", delay_random=0))
        await rw.async_save_settings({"rw_covers": ["cover.wz"]})
        return rw, hass

    rw, hass = asyncio.run(run())
    st = rw.status()["covers"]["cover.wz"]
    assert st["room"]["name"] == "Wohnzimmer" and st["room"]["auto"]
    assert st["contacts"] == {"open": ["binary_sensor.wz_tuer"], "tilted": ["binary_sensor.wz_fenster"], "src": "heizwerk"}
    assert st["room_temp"] == 23.5
    # Fenster (gekippt) offen beim Schließen -> Lüftungsstellung statt zu
    assert hass.calls[-1] == ("cover", "set_cover_position", {"entity_id": "cover.wz", "position": 30})
    assert "gekippt – lüften" in st["reason"]


def test_rollwerk_zwei_stufen(hw):
    """Abends: Stufe 1 (50 %) sobald die Sonne im Westen steht, Stufe 2 (zu) zur spätesten Zeit."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 7, 16, 17, 0, tzinfo=timezone.utc)  # 18:00 lokal
        hass = Hass()
        feat = {"supported_features": 15}
        hass.set("cover.wz", "open", {"current_position": 100, **feat}, "Wohnzimmer")
        hass.set("sun.sun", "above_horizon", {"azimuth": 240, "elevation": 25}, "Sonne")
        log, haus, ctl = await _setup(hw, hass)
        rw = hw.Rollwerk(hass, log, haus)
        await rw.async_load()
        await rw.async_start()
        await rw.async_save_profile("standard", dict(rw.profiles["standard"], features=["up", "down", "time"], delay_random=0,
                                                     close_stage1=True, stage1_trigger="azimuth", stage1_azimuth=250, pos_stage1=50,
                                                     down_early="16:00", down_late="22:00"))
        await rw.async_save_settings({"rw_covers": ["cover.wz"]})
        steps = [rw.status()["covers"]["cover.wz"]["target"]]
        # Sonne im Westen: Stufe 1
        hass.set("sun.sun", "above_horizon", {"azimuth": 262, "elevation": 15}, "Sonne")
        NOW[0] = datetime(2026, 7, 16, 18, 0, tzinfo=timezone.utc)
        await rw.async_evaluate()
        steps.append(hass.calls[-1][2]["position"])
        reason1 = rw.status()["covers"]["cover.wz"]["reason"]
        hass.set("cover.wz", "open", {"current_position": 50, **feat}, "Wohnzimmer")
        # 22:01: Stufe 2
        NOW[0] = datetime(2026, 7, 16, 21, 1, tzinfo=timezone.utc)
        await rw.async_evaluate()
        steps.append(hass.calls[-1][2]["position"])
        reason2 = rw.status()["covers"]["cover.wz"]["reason"]
        # Stufe 2 aus: bleibt nachts auf Stufe 1
        hass.set("cover.wz", "closed", {"current_position": 0, **feat}, "Wohnzimmer")
        await rw.async_evaluate()
        await rw.async_save_profile("standard", dict(rw.profiles["standard"], close_stage2=False))
        steps.append(hass.calls[-1][2]["position"])
        return steps, reason1, reason2, rw

    steps, reason1, reason2, rw = asyncio.run(run())
    assert steps == [100, 50, 0, 50]
    assert reason1 == "Abends Stufe 1 (Sonne ab 250°)" and reason2 == "Abends Stufe 2 (späteste Zeit)"


def test_rollwerk_protokoll(hw):
    """Profil-Änderungen mit Vorher/Nachher, Fahrten als „Rollwerk“ im Protokoll."""
    rwmod = importlib.import_module("hw.rollwerk")
    text = rwmod.profile_changes({"temp2_min": 22, "pos_stage1": 50}, {"temp2_min": 24, "pos_stage1": 50, "close_stage1": True})
    assert text == "Zwei Stufen aus → an, Beschatten ab außen 22 °C → 24 °C"

    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 7, 16, 20, 1, tzinfo=timezone.utc)
        hass = Hass()
        hass.set("cover.wz", "open", {"current_position": 100, "supported_features": 15}, "Wohnzimmer")
        hass.set("sun.sun", "below_horizon", {"azimuth": 300, "elevation": -5}, "Sonne")
        log, haus, ctl = await _setup(hw, hass)
        rw = hw.Rollwerk(hass, log, haus)
        await rw.async_load()
        await rw.async_start()
        await rw.async_save_profile("standard", dict(rw.profiles["standard"], down_early="21:00", down_late="21:00", delay_random=0), by="Jens")
        await rw.async_save_settings({"rw_covers": ["cover.wz"]}, by="Jens")
        hass.set("sensor.lux", "500", {}, "Lux Terrasse")
        prof = dict(rw.profiles["standard"])
        await rw.async_save_profile("standard", dict(prof, features=[f for f in prof["features"] if f != "ventilate"] + ["shading"],
                                                     brightness_sensor="sensor.lux"), by="Jens")
        n = len(log.entries)
        await rw.async_save_profile("standard", dict(rw.profiles["standard"]), by="Jens")
        await rw.async_save_cover("cover.wz", dict(rw.covers["cover.wz"]), by="Jens")
        assert len(log.entries) == n, "Speichern ohne Änderung erzeugt keinen Eintrag"
        await rw.async_save_cover("cover.wz", dict(rw.covers["cover.wz"], storm=False), by="Jens")
        await rw.async_save_settings({"rw_recovery": "always"}, by="Jens")
        return log

    log = asyncio.run(run())
    rw_entries = [e for e in log.entries if e.get("mod") == "rollwerk"]
    titles = [e["title"] for e in rw_entries]
    assert "Profil „Standard“ geändert" in titles and "Wohnzimmer zu" in titles
    prof = next(e for e in rw_entries if e["title"] == "Profil „Standard“ geändert")
    assert "Schließen frühestens 16:00 → 21:00" in prof["why"] and "von Jens" in prof["why"]
    feat = [e for e in rw_entries if e["title"] == "Profil „Standard“ geändert"][-1]["why"]
    assert "Funktionen: + Beschattung, − Lüften" in feat and "Helligkeitssensor – → Lux Terrasse" in feat
    assert "für Wohnzimmer" in feat and "gewählt" not in feat
    assert not any("ohne Änderung" in (e.get("why") or "") for e in rw_entries)
    storm = [e for e in rw_entries if e["title"] == "Rollladen Wohnzimmer geändert"]
    assert len(storm) == 1 and storm[0]["why"].startswith("Sturmschutz an → aus")
    assert any(e["why"].startswith("Nach Neustart nachholen nie → immer") or "→ immer" in e["why"] for e in rw_entries if e["cat"] == "settings")
    move = next(e for e in rw_entries if e["title"] == "Wohnzimmer zu")
    assert move["cat"] == "shutter" and "vorher 100 %" in move["why"]


def test_rollwerk_neustart(hw):
    """Neustart abends: Rollladen beim Start noch nicht erreichbar, Sonne schon unten – nichts fährt hoch."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 11, 16, 19, 42, tzinfo=timezone.utc)  # 20:42 lokal
        hass = Hass()
        hass.set("cover.wz", "closed", {"current_position": 0, "supported_features": 15}, "Wohnzimmer")
        hass.set("sun.sun", "below_horizon", {"azimuth": 290, "elevation": -25}, "Sonne")
        log, haus, ctl = await _setup(hw, hass)
        rw = hw.Rollwerk(hass, log, haus)
        await rw.async_load()
        await rw.async_start()
        await rw.async_save_profile("standard", dict(rw.profiles["standard"], features=["up", "down", "time", "sun"], delay_random=0))
        await rw.async_save_settings({"rw_covers": ["cover.wz"]})
        await rw.async_stop()
        calls_before = len([c for c in hass.calls if c[0] == "cover"])
        # Neustart: neue Instanz, Rollladen anfangs nicht erreichbar
        hass2 = Hass()
        hass2.set("cover.wz", "unavailable", {}, "Wohnzimmer")
        hass2.set("sun.sun", "below_horizon", {"azimuth": 290, "elevation": -25}, "Sonne")
        log2, haus2, ctl2 = await _setup(hw, hass2)
        rw2 = hw.Rollwerk(hass2, log2, haus2)
        await rw2.async_load()
        restored = dict(rw2._rt.get("cover.wz") or {})
        await rw2.async_start()
        hass2.set("cover.wz", "closed", {"current_position": 0, "supported_features": 15}, "Wohnzimmer")
        await rw2.async_evaluate()
        NOW[0] = datetime(2026, 11, 16, 19, 50, tzinfo=timezone.utc)
        await rw2.async_evaluate()
        return calls_before, hass2, rw2, restored

    calls_before, hass2, rw2, restored = asyncio.run(run())
    assert restored.get("closed_on") == "2026-11-16"
    assert not [c for c in hass2.calls if c[0] == "cover"]
    assert rw2.status()["covers"]["cover.wz"]["target"] == 0


def test_kraftwerk(hw):
    """Kraftwerk: nur kw_-Einstellungen, Protokoll mit Modul, bleibt nach Neustart erhalten."""
    async def run():
        STORES.clear()
        REG.clear()
        hass = Hass()
        log, haus, ctl = await _setup(hw, hass)
        kw = hw.Kraftwerk(hass, log, haus)
        await kw.async_load()
        assert kw.settings["kw_solar"] == [] and kw.settings["kw_grid"] is None
        await kw.async_save_settings({"kw_solar": ["sensor.pv"], "kw_grid": "sensor.netz", "rw_covers": ["cover.x"], "kw_names": {"sensor.wp": "Wärmepumpe"}}, by="Jens")
        assert kw.settings["kw_names"] == {"sensor.wp": "Wärmepumpe"}
        assert "rw_covers" not in kw.settings
        e = log.entries[-1]
        assert e["mod"] == "kraftwerk" and "Kraftwerk: Solar" in e["why"] and "Jens" in e["why"]
        n = len(log.entries)
        await kw.async_save_settings({"kw_grid": "sensor.netz"})  # unverändert: kein Eintrag
        assert len(log.entries) == n
        assert sorted(kw.entities()) == ["sensor.netz", "sensor.pv"]
        kw2 = hw.Kraftwerk(hass, log, haus)
        await kw2.async_load()
        assert kw2.settings["kw_solar"] == ["sensor.pv"]
    asyncio.run(run())


def test_rollwerk_fenster_in_jedem_fall(hw):
    """Gekippt lüftet auch im Standard-Profil; eine offene Tür sperrt nie aus – auch nicht beim Erzwingen."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 7, 16, 20, 1, tzinfo=timezone.utc)  # 21:01 lokal, nach dem Schließen
        hass = Hass()
        for eid in ("cover.wz", "climate.wz", "binary_sensor.wz_fenster", "binary_sensor.wz_tuer"):
            REG[eid] = types.SimpleNamespace(entity_id=eid, device_id=None, area_id="wohnen", domain=eid.split(".")[0], disabled_by=None)
        hass.set("cover.wz", "open", {"current_position": 100, "supported_features": 15}, "Rollladen Wohnzimmer")
        hass.set("climate.wz", "heat", {"current_temperature": 21, "temperature": 21}, "Wandthermostat")
        hass.set("binary_sensor.wz_fenster", "on", {"device_class": "window"}, "Fenster Wohnzimmer")
        hass.set("binary_sensor.wz_tuer", "off", {"device_class": "door"}, "Terrassentür")
        hass.set("input_boolean.zu", "off", {}, "Alle zu")
        hass.set("sun.sun", "below_horizon", {"azimuth": 300, "elevation": -5}, "Sonne")
        log, haus, ctl = await _setup(hw, hass)
        hass.data["hauswerk"] = {"heizen": ctl}
        await ctl.async_save_room({"id": "wz", "name": "Wohnzimmer", "type": "heizkoerper", "comfort": 21, "eco": 18,
                                   "climates": ["climate.wz"], "windows": ["binary_sensor.wz_fenster", "binary_sensor.wz_tuer"]})
        # Profil wie aus 0.37 gespeichert: ohne „ventilate“
        STORES["hauswerk.rollwerk"] = {"settings": {"rw_covers": ["cover.wz"]}, "covers": {},
                                       "profiles": {"standard": dict(hw.Rollwerk.__init__.__globals__["PROFILE_DEFAULTS"],
                                                                     features=["up", "down", "time"], down_early="21:00",
                                                                     down_late="21:00", delay_random=0, force_down="input_boolean.zu")}}
        rw = hw.Rollwerk(hass, log, haus)
        await rw.async_load()
        assert "ventilate" in rw.profiles["standard"]["features"]
        assert any("gekippte Fenster lüften" in e["title"] for e in log.entries)
        await rw.async_start()
        # nach dem Start nur Stand übernehmen (kein Fahren) – das Ziel zählt
        out = {"tilted": (rw.status()["covers"]["cover.wz"]["target"], rw.status()["covers"]["cover.wz"]["reason"])}
        # Tür auf, Fenster zu, „Alle zu“ erzwungen -> nicht herunterfahren
        hass.set("cover.wz", "open", {"current_position": 30, "supported_features": 15}, "Rollladen Wohnzimmer")
        hass.set("binary_sensor.wz_fenster", "off", {"device_class": "window"}, "Fenster Wohnzimmer")
        hass.set("binary_sensor.wz_tuer", "on", {"device_class": "door"}, "Terrassentür")
        hass.set("input_boolean.zu", "on", {}, "Alle zu")
        n = len(hass.calls)
        await rw.async_evaluate()
        out["door"] = (hass.calls[n:], rw.status()["covers"]["cover.wz"])
        # Tür zu -> Erzwingen greift
        hass.set("binary_sensor.wz_tuer", "off", {"device_class": "door"}, "Terrassentür")
        await rw.async_evaluate()
        out["closed"] = hass.calls[-1][2].get("position")
        return out

    out = asyncio.run(run())
    assert out["tilted"][0] == 30 and "gekippt" in out["tilted"][1]
    calls, st = out["door"]
    assert not any(c[2].get("position", 100) < 30 for c in calls), calls
    assert "nicht herunterfahren" in st["reason"] and "Erzwingen" in st["reason"]
    assert out["closed"] == 0


def test_entitaet_umbenannt(hw):
    """Umbenannte Entität: überall ersetzt (Werte und Schlüssel), sofort gespeichert, im Protokoll."""
    async def run():
        STORES.clear()
        NOW[0] = datetime(2026, 11, 18, 7, 0, tzinfo=timezone.utc)
        hass = Hass()
        hass.set("climate.wz", "heat", {"current_temperature": 20.0, "temperature": 21.0}, "Thermostat")
        hass.set("cover.wz", "open", {"current_position": 100}, "Rollladen")
        log, haus, ctl = await _setup(hw, hass)
        rw = hw.Rollwerk(hass, log, haus)
        await rw.async_load()
        await ctl.async_save_room({"id": "wz", "name": "Wohnzimmer", "type": "heizkoerper", "comfort": 21, "eco": 18,
                                   "climates": ["climate.wz"], "windows": [], "enabled": True,
                                   "schedule": [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "08:00", "end": "22:00"}]}, by="Jens")
        await rw.async_save_settings({"rw_covers": ["cover.wz"]}, by="Jens")
        await haus.async_save_settings({"start_widgets": [{"id": "a", "type": "values", "size": "m", "entities": ["climate.wz"]}]}, by="Jens")
        hass.data = {"hauswerk": {"log": log, "haus": haus, "heizen": ctl, "rollwerk": rw}}
        touched = await hw.rename.async_rename_entity(hass, None, "climate.wz", "climate.wohnzimmer")
        touched2 = await hw.rename.async_rename_entity(hass, None, "cover.wz", "cover.wohnzimmer")
        nothing = await hw.rename.async_rename_entity(hass, None, "sensor.gibtsnicht", "sensor.x")
        return ctl, haus, rw, log, touched, touched2, nothing

    ctl, haus, rw, log, touched, touched2, nothing = asyncio.run(run())
    assert ctl.rooms["wz"]["climates"] == ["climate.wohnzimmer"]
    assert haus.settings["start_widgets"][0]["entities"] == ["climate.wohnzimmer"]
    assert set(touched) == {"heizen", "haus"} and touched2 == ["rollwerk"] and nothing == []
    assert rw.settings["rw_covers"] == ["cover.wohnzimmer"] and "cover.wohnzimmer" in rw.covers and "cover.wz" not in rw.covers
    assert any(e["title"] == "Entität umbenannt – übernommen" and "climate.wz → climate.wohnzimmer" in e["why"] for e in log.entries)


def test_sommerpause_nach_tagesmittel(hw):
    """Kalter Morgen mitten im warmen Zeitraum: nach Tagesmittel bleibt Sommerpause, nach „jetzt“ nicht."""
    async def run():
        STORES.clear()
        NOW[0] = datetime(2026, 6, 10, 6, 0, tzinfo=timezone.utc)
        hass = Hass()
        hass.set("sensor.aussen", "10.0", {"unit_of_measurement": "°C"}, "Außen")
        log, haus, ctl = await _setup(hw, hass)
        await haus.async_save_settings({"outside_sensor": "sensor.aussen"}, by="Jens")
        hour = int(NOW[0].timestamp() // 3600)
        ctl.outside_hours = {str(hour - i): [22.0, 1] for i in range(1, 24)}
        await ctl.async_save_settings({"summer_mode": "auto", "summer_temp": 16, "summer_basis": "day"}, by="Jens")
        await ctl.async_evaluate()
        day = (ctl._summer, ctl.status()["outside_mean"])
        await ctl.async_save_settings({"summer_basis": "now"}, by="Jens")
        await ctl.async_evaluate()
        return day, ctl._summer, ctl.outside_hours.get(str(hour))

    day, now_summer, cur = asyncio.run(run())
    assert day[0] is True and day[1] is not None and day[1] > 16
    assert now_summer is False
    assert cur is not None and cur[1] >= 1  # aktueller Wert wurde mitgezählt


def test_arbeitstage_aus_dem_kalender(hw):
    """Zentraler Arbeitstage-Kalender: übernommen vom Sensor derselben Integration, kennt auch künftige Feiertage;
    Heizwerk fährt an einem freien Werktag den Wochenend-Plan, Rollwerk schließt am Vorabend wie vor einem freien Tag."""
    async def run():
        STORES.clear()
        NOW[0] = datetime(2026, 11, 16, 7, 0, tzinfo=timezone.utc)  # Montag
        hass = Hass()
        hass.set("binary_sensor.arbeitstag", "on", name="Arbeitstag")
        hass.set("calendar.arbeitstag", "on", name="Arbeitstag Kalender")
        REG["binary_sensor.arbeitstag"] = types.SimpleNamespace(entity_id="binary_sensor.arbeitstag", domain="binary_sensor",
                                                                 config_entry_id="wd", disabled_by=None, device_id=None)
        REG["calendar.arbeitstag"] = types.SimpleNamespace(entity_id="calendar.arbeitstag", domain="calendar",
                                                            config_entry_id="wd", disabled_by=None, device_id=None)
        # Arbeitstage Mo–Fr, aber Mittwoch 18.11. (Buß- und Bettag) frei
        days = [date(2026, 11, 16) + timedelta(days=k) for k in range(15)]
        hass.events = {"calendar.arbeitstag": [
            {"summary": "Arbeitstag", "start": d.isoformat(), "end": (d + timedelta(days=1)).isoformat()}
            for d in days if d.weekday() < 5 and d != date(2026, 11, 18)]}
        log, haus, ctl = await _setup(hw, hass)
        await haus.async_save_settings({"workday_entity": "binary_sensor.arbeitstag", "workday_as": 6})
        await haus.async_start()
        assert haus.settings["workday_calendar"] == "calendar.arbeitstag", "Kalender nicht übernommen"
        assert haus.is_workday(date(2026, 11, 16)) is True
        assert haus.is_workday(date(2026, 11, 18)) is False
        assert haus.free_days()[0] == "2026-11-18" and haus.status()["workday_source"] == "Arbeitstag Kalender"
        # Mittwoch: Sensor sagt noch „Arbeitstag“, der Kalender weiß es besser – Plan wie Sonntag
        NOW[0] = datetime(2026, 11, 18, 6, 0, tzinfo=timezone.utc)
        await ctl.async_save_room({"id": "bad", "name": "Bad", "type": "heizkoerper", "comfort": 22, "eco": 18,
                                   "climates": [], "windows": [], "enabled": True,
                                   "schedule": [{"days": [0, 1, 2, 3, 4], "start": "05:30", "end": "08:00"},
                                                {"days": [5, 6], "start": "09:00", "end": "22:00"}]})
        hass.set("climate.bad", "heat", {"current_temperature": 20.0, "temperature": 18.0}, "Thermostat Bad")
        await ctl.async_save_room({**ctl.rooms["bad"], "climates": ["climate.bad"]})
        await ctl.async_evaluate()
        res = ctl.status()["rooms"]["bad"]
        assert res["holiday"] is True and res["mode"] == "eco", res  # 07:00: werktags Komfort, sonntags noch nicht
        # Donnerstag wieder Arbeitstag
        NOW[0] = datetime(2026, 11, 19, 6, 0, tzinfo=timezone.utc)
        await ctl.async_evaluate()
        assert ctl.status()["rooms"]["bad"]["holiday"] is False
        return haus

    asyncio.run(run())


def test_muellabholung(hw):
    """Müllabholung: Kalender von Waste Collection Schedule wird erkannt (und aus den Terminen genommen),
    Abholungen ohne ausgeblendete Arten, Hinweis am Vorabend ab der Erinnerungszeit und Nachricht einmal je Abholtag."""
    async def run():
        STORES.clear()
        NOW[0] = datetime(2026, 11, 18, 15, 0, tzinfo=timezone.utc)  # 16:00 Ortszeit
        hass = Hass()
        hass.set("calendar.abfall", "off", name="Waste Collection Schedule Landkreis")
        hass.set("calendar.familie", "off", name="Familie")
        REG["calendar.abfall"] = types.SimpleNamespace(entity_id="calendar.abfall", domain="calendar", platform="waste_collection_schedule",
                                                        config_entry_id="w", disabled_by=None, device_id=None)
        hass.events = {"calendar.abfall": [
            {"summary": "Restabfall", "start": "2026-11-19", "end": "2026-11-20"},
            {"summary": "Sperrmüll", "start": "2026-11-19", "end": "2026-11-20"},
            {"summary": "Papier", "start": "2026-11-24", "end": "2026-11-25"}]}
        log, haus, ctl = await _setup(hw, hass)
        haus.settings.pop("waste_calendars", None)
        haus._waste_new = True
        haus.settings["calendars"] = ["calendar.familie", "calendar.abfall"]
        await haus.async_start()
        assert haus.settings["waste_calendars"] == ["calendar.abfall"] and haus.settings["calendars"] == ["calendar.familie"]
        await haus.async_save_settings({"waste_hidden": ["Sperrmüll"], "notify_waste": "normal",
                                        "notify_targets": ["mobile_app_pixel"], "notify_quiet": False})
        st = haus.status()
        assert [e["type"] for e in st["waste"]] == ["Restabfall", "Papier"] and "Sperrmüll" in st["waste_types"]
        assert st["waste_due"] is None  # 16 Uhr: noch nicht
        NOW[0] = datetime(2026, 11, 18, 17, 5, tzinfo=timezone.utc)  # 18:05
        await haus._async_tick()
        assert haus.status()["waste_due"] == {"date": "2026-11-19", "when": "morgen", "types": ["Restabfall"]}
        await haus._async_tick()
        await asyncio.sleep(0)
        sent = [c for c in hass.calls if c[0] == "notify"]
        assert len(sent) == 1 and "Restabfall" in sent[0][2]["message"], sent
        NOW[0] = datetime(2026, 11, 19, 7, 0, tzinfo=timezone.utc)  # Abholtag 8 Uhr
        await haus._async_tick()
        assert haus.status()["waste_due"]["when"] == "heute"
        NOW[0] = datetime(2026, 11, 19, 10, 0, tzinfo=timezone.utc)  # 11 Uhr: vorbei
        await haus._async_tick()
        assert haus.status()["waste_due"] is None

    asyncio.run(run())


def test_lueften_ausgebaut(hw):
    """Lüften: Empfehlung mit Dauer nach Außentemperatur und Grenze je Raumart, Schimmel-Ampel, Lüft-Timer mit
    „Fenster schließen“, Bilanz nach dem Schließen, Dauerkippen mit Wärmeverlust."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 11, 18, 11, 0, tzinfo=timezone.utc)
        hass = Hass()
        hass.set("climate.bad", "heat", {"current_temperature": 21.0, "temperature": 21.0}, "Thermostat Bad")
        hass.set("sensor.bad_t", "21.0", name="Bad Temperatur")
        hass.set("sensor.bad_h", "72", name="Bad Feuchte")
        hass.set("binary_sensor.bad_fenster", "off", name="Bad Fenster")
        hass.set("weather.home", "cloudy", {"temperature": 2.0, "humidity": 80})
        log, haus, ctl = await _setup(hw, hass)
        await haus.async_save_settings({"weather_entity": "weather.home", "notify_targets": ["mobile_app_pixel"], "notify_quiet": False})
        await ctl.async_save_settings({"vent_rh": 65})
        await ctl.async_save_room({"id": "bad", "name": "Bad", "type": "heizkoerper", "comfort": 22, "eco": 18,
                                   "climates": ["climate.bad"], "windows": ["binary_sensor.bad_fenster"],
                                   "temp_sensor": "sensor.bad_t", "humidity_sensor": "sensor.bad_h", "enabled": True, "schedule": []})
        res = ctl.status()["rooms"]["bad"]
        # Bad: Grenze 70 % (Raumart), 72 % → lüften; draußen 2 °C → 10 Min.
        assert res["air"]["limit"] == 70 and res["vent"]["minutes"] == 10 and "Luftfeuchte 72 %" in res["vent"]["reasons"]
        assert res["air"]["mold"]["level"] in ("warn", "bad") and res["air"]["mold"]["wall_temp"] == 15.3
        # Fenster auf: Timer läuft, nach 10 Min. „Fenster schließen“
        hass.set("binary_sensor.bad_fenster", "on", name="Bad Fenster")
        await ctl.async_evaluate()
        assert ctl.status()["rooms"]["bad"]["vent"] is None and ctl.status()["rooms"]["bad"]["air"]["open"]["target"] == 10
        NOW[0] += timedelta(minutes=11)
        hass.set("sensor.bad_h", "60", name="Bad Feuchte")
        await ctl.async_evaluate()
        await asyncio.sleep(0)
        air = ctl.status()["rooms"]["bad"]["air"]
        assert air["open"]["done"] and "Fenster schließen" in hass.sent()
        assert any(e["title"].startswith("Genug gelüftet") for e in log.entries)
        # lange offen in der Heizzeit: Hinweis mit Wärmeverlust
        NOW[0] += timedelta(minutes=25)
        await ctl.async_evaluate()
        long = ctl.status()["rooms"]["bad"]["air"]["long"]
        assert long["minutes"] >= 30 and long["kwh"] > 0
        # Fenster zu: Bilanz
        hass.set("binary_sensor.bad_fenster", "off", name="Bad Fenster")
        await ctl.async_evaluate()
        week = ctl.status()["rooms"]["bad"]["air"]["week"]
        assert week["count"] == 1 and week["minutes"] >= 35 and week["rh_drop"] == 12
        assert ctl._data()["vent_log"]["bad"][0]["rh0"] == 72

    asyncio.run(run())
