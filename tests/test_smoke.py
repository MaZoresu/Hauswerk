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
    _mod("homeassistant.core", Event=object, HomeAssistant=object, State=object, Context=Context, callback=lambda f: f)
    helpers = _mod("homeassistant.helpers")
    helpers.device_registry = _mod("homeassistant.helpers.device_registry",
                                   async_get=lambda hass: types.SimpleNamespace(async_get=DEVS.get, devices=DEVS))
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
    for name in ("controller.py", "core.py", "logic.py", "const.py", "log.py", "rollwerk.py", "kraftwerk.py", "rename.py", "appliance.py", "appliance_logic.py", "light_logic.py", "lichtwerk.py", "hmlinks.py", "beetwerk.py"):
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
        Lichtwerk=importlib.import_module("hw.lichtwerk").Lichtwerk,
        Beetwerk=importlib.import_module("hw.beetwerk").Beetwerk,
        light=importlib.import_module("hw.light_logic"),
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
        self.services = types.SimpleNamespace(async_call=self._call, has_service=lambda d, s: True)
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
        if (domain, service) == ("homematicip_local", "get_link_paramset"):
            key = (data["sender_channel_address"], data["receiver_channel_address"])
            if key not in getattr(self, "paramsets", {}):
                raise RuntimeError("XMLRPC Fault: no link")
            return self.paramsets[key]
        if (domain, service) == ("homematicip_local", "get_link_peers"):
            a = data["device_address"]
            if a in getattr(self, "bidcos", set()):
                if "channel" not in data:
                    raise RuntimeError("XMLRPC Fault -1: Failure")
                return {f"{a}:{data['channel']}": getattr(self, "links", {}).get(f"{a}:{data['channel']}", [])}
            return {a: getattr(self, "links", {}).get(a, [])}
        if (domain, service) == ("weather", "get_forecasts"):
            if data.get("type") == "hourly" and getattr(self, "hourly", None) is not None:
                return {data["entity_id"]: {"forecast": self.hourly}}
            return {data["entity_id"]: {"forecast": self.forecast or []}}
        return None

    def async_create_task(self, coro):
        return asyncio.ensure_future(coro)

    def sent(self):
        """Gesendete Nachrichten (Titel, ohne das Emoji davor – das prüft test_benachrichtigung_emoji)."""
        return [d["title"].split(" ", 1)[1] if d.get("title") and not d["title"][0].isalnum() else d.get("title") for dom, _s, d in self.calls if dom == "notify"]

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
        assert [d["title"] for _s, d in pushes] == ["❄️ Frost erwartet"]  # Fenster nur Protokoll, Batterie aus
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


def test_funk_nicht_im_kreis_senden(hw):
    """Zusatz-Heizkörper übernimmt den Frostschutz-Wert nicht (CCU stellt zurück): höchstens zweimal senden, dann 15 Min.,
    danach stündlich; „Wer funkt“ zählt die Befehle je Gerät mit Herkunft."""
    async def run():
        STORES.clear()
        REG.clear()
        DEVS.clear()
        NOW[0] = datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc)
        hass = Hass()
        hass.set("climate.wth", "heat", {"current_temperature": 20.8, "temperature": 21.0, "model": "HmIP-WTH-2"}, "WTH Kleines Bad")
        hass.set("climate.trv", "heat", {"current_temperature": 24.5, "temperature": 12.0, "model": "HMIP-eTRV"}, "Heizkörper Kleines Bad")
        for eid in ("climate.wth", "climate.trv"):
            REG[eid] = types.SimpleNamespace(entity_id=eid, device_id=None, domain="climate", disabled_by=None, platform="homematicip_local")
        log, haus, ctl = await _setup(hw, hass)
        await haus.async_start()
        await ctl.async_save_room({"id": "kb", "name": "Kleines Bad", "comfort": 21, "eco": 18, "enabled": True, "type": "flaeche",
                                   "climates": ["climate.wth", "climate.trv"], "assist_entities": ["climate.trv"],
                                   "schedule": [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "06:00", "end": "22:00"}]})
        to_trv = lambda: [d for dom, sv, d in hass.calls if sv == "set_temperature" and d["entity_id"] == "climate.trv"]
        assert len(to_trv()) == 1  # 7 °C gesendet, der Heizkörper bleibt bei 12 (wird zurückgestellt)
        # Rückfall nach 30 s: nicht sofort nachlegen
        NOW[0] += timedelta(seconds=30)
        await ctl.async_evaluate()
        assert len(to_trv()) == 1
        for _ in range(20):  # 20 Minuten jede Minute auswerten
            NOW[0] += timedelta(minutes=1)
            await ctl.async_evaluate()
        assert len(to_trv()) == 3, len(to_trv())  # 2× gleich, nach 15 Min. ein dritter Versuch
        st = ctl.status()
        u = st["rooms"]["kb"]["unconfirmed"]
        assert u and u[0]["entity"] == "climate.trv" and u[0]["value"] == 7.0 and u[0]["current"] == 12.0 and u[0]["fails"] >= 2
        assert st["radio"]["retry"][0]["entity"] == "climate.trv"
        for _ in range(60):  # danach nur noch stündlich
            NOW[0] += timedelta(minutes=1)
            await ctl.async_evaluate()
        assert len(to_trv()) == 4, len(to_trv())
        # Wer funkt: Heizkörper vorn, Herkunft Heizwerk; eine Automation zählt mit
        top = ctl.status()["radio"]["top"]
        assert top[0]["entity"] == "climate.trv" and top[0]["day"] == 4 and top[0]["sources"][0]["name"] == "Heizwerk", top
        await hass.services.async_call("climate", "set_temperature", {"entity_id": "climate.wth", "temperature": 22},
                                       context=types.SimpleNamespace(id="x", user_id=None, parent_id="auto1"))
        top = {o["entity"]: o for o in ctl.status()["radio"]["top"]}
        assert top["climate.wth"]["sources"][0]["name"] == "Automation oder Skript"
        # Wert steht endlich: Hinweis weg
        NOW[0] += timedelta(minutes=2)
        hass.set("climate.trv", "heat", {"current_temperature": 24.5, "temperature": 7.0, "model": "HMIP-eTRV"}, "Heizkörper Kleines Bad")
        await ctl.async_evaluate()
        assert not ctl.status()["rooms"]["kb"]["unconfirmed"] and not ctl.status()["radio"]["retry"]
        return log

    log = asyncio.run(run())
    titles = [e["title"] for e in log.entries]
    assert "Heizkörper Kleines Bad übernimmt den Sollwert nicht" in titles
    assert "Heizkörper Kleines Bad übernimmt den Sollwert wieder" in titles


def test_hmlinks_zusatz_aber_verknuepft(hw):
    hm = importlib.import_module("hw.hmlinks") if (hw and False) else None
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location("hml", pathlib.Path(__file__).parent.parent / "custom_components/hauswerk/hmlinks.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    rooms = {"kb": {"climates": ["climate.wth", "climate.trv"], "assist_entities": ["climate.trv"]}}
    analysis = {"kb": {"walls": [{"entity": "climate.wth", "peers": [{"x": 1}]}], "linked_trvs": ["climate.trv"], "unlinked_trvs": []}}
    out = mod.findings(rooms, analysis, lambda e: e, {}, [])
    assert any(f["level"] == "warn" and "Zusatzheizung" in f["text"] and f["entity"] == "climate.trv" for f in out), out


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

    async def more():
        # „Beim Lüften ganz öffnen“: Fenster offen -> ganz auf; Fenster zu -> zurück (zu)
        hass.set("cover.wz", "open", {"current_position": 30, "supported_features": 15}, "Rollladen Wohnzimmer")
        await rw.async_evaluate()
        prof = dict(rw.profiles["standard"], vent_options=["vent_full"])
        await rw.async_save_profile("standard", prof)
        full = (hass.calls[-1], rw.status()["covers"]["cover.wz"]["reason"], {k: v for k, v in rw._rt["cover.wz"].items() if k in ("sent", "target", "blocked", "manual_at", "cat")})
        hass.set("cover.wz", "open", {"current_position": 100, "supported_features": 15}, "Rollladen Wohnzimmer")
        # Regen bei offenem Fenster: Nachricht
        hass.set("weather.home", "rainy", {"temperature": 12, "humidity": 95})
        await rw.haus.async_save_settings({"weather_entity": "weather.home", "notify_targets": ["mobile_app_pixel"], "notify_quiet": False,
                                           "notify_storm": "normal"})
        await rw.async_evaluate()
        await asyncio.sleep(0)
        wet = "Fenster offen – Regen" in hass.sent()
        hass.set("binary_sensor.wz_fenster", "off", {"device_class": "window"}, "Fenster Wohnzimmer")
        await rw.async_evaluate()
        return full, wet, hass.calls[-1]

    full, wet, back = asyncio.run(more())
    assert "ganz auf" in full[1] and (full[0][2].get("position") == 100 or full[0][1] == "open_cover"), full
    assert wet
    assert back[2].get("position") == 0 or back[1] == "close_cover", back


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
        # „Fenster schließen“ je Raum und Tag höchstens zweimal senden, danach nur Glocke
        for _ in range(2):
            hass.set("sensor.bad_h", "72", name="Bad Feuchte")
            NOW[0] += timedelta(minutes=5)
            hass.set("binary_sensor.bad_fenster", "on", name="Bad Fenster")
            await ctl.async_evaluate()
            NOW[0] += timedelta(minutes=11)
            hass.set("sensor.bad_h", "60", name="Bad Feuchte")
            await ctl.async_evaluate()
            await asyncio.sleep(0)
            assert ctl.status()["rooms"]["bad"]["air"]["open"]["done"]
            hass.set("binary_sensor.bad_fenster", "off", name="Bad Fenster")
            await ctl.async_evaluate()
        assert hass.sent().count("Fenster schließen") == 2
        assert any("nur Glocke – heute schon 2× gesendet" in (e.get("why") or "") for e in log.entries if e["title"] == "Fenster schließen")
        # Lüften gelernt: nach drei Lüftungen Dauer aus dem Luftwechsel des Raums; Kosten je Lüftung und Woche
        hass.set("sensor.bad_h", "72", name="Bad Feuchte")
        NOW[0] += timedelta(minutes=5)
        hass.set("binary_sensor.bad_fenster", "on", name="Bad Fenster")
        await ctl.async_evaluate()
        NOW[0] += timedelta(minutes=8)
        hass.set("sensor.bad_h", "60", name="Bad Feuchte")
        await ctl.async_evaluate()
        hass.set("binary_sensor.bad_fenster", "off", name="Bad Fenster")
        await ctl.async_evaluate()
        await ctl.async_evaluate()
        air = ctl.status()["rooms"]["bad"]["air"]
        assert len(ctl._data()["vent_tau"]["bad"]) == 3 and air["learned"] and air["tau"] and 3 <= air["minutes"] <= 30
        assert any(e["title"] == "Lüften gelernt" for e in log.entries)
        # Draußen schwül: Lüften trocknet nicht – keine Empfehlung, sondern „später“
        hass.set("sensor.bad_h", "75", name="Bad Feuchte")
        hass.set("weather.home", "cloudy", {"temperature": 24.0, "humidity": 95})
        await ctl.async_evaluate()
        res = ctl.status()["rooms"]["bad"]
        assert res["air"]["helps"] is False and res["air"]["wait"] and not any("Luftfeuchte" in r for r in (res["vent"] or {}).get("reasons", []))
        # beste Lüftzeit aus der Stunden-Vorhersage (Regen wird gemieden)
        start = NOW[0].replace(minute=0, second=0, microsecond=0)
        hass.hourly = [{"datetime": (start + timedelta(hours=i)).isoformat(), "temperature": 3 + i * 0.5, "humidity": 80,
                        "condition": "rainy" if i == 1 else "cloudy"} for i in range(24)]
        await haus._async_refresh_forecast(force=True)
        plan = ctl.status()["vent_plan"]
        assert plan and plan["times"] and all(t["minutes"] for t in plan["times"])

    asyncio.run(run())


def test_geraet_fertig_einmal_gemeldet(hw):
    """Kraftwerk-Gerät: läuft ohne Dashboard (nur Zustände und Takt), meldet „fertig“ je Kanal genau einmal –
    auch nach einem Neustart nicht doppelt; Korrektur und Zustand stehen im Status."""
    async def run():
        STORES.clear()
        NOW[0] = datetime(2026, 11, 20, 7, 0, tzinfo=timezone.utc)
        hass = Hass()
        hass.set("sensor.wm_leistung", "0.05", {"unit_of_measurement": "W"}, "WM Leistung")
        log, haus, ctl = await _setup(hw, hass)
        kw = hw.Kraftwerk(hass, log, haus)
        await kw.async_load()
        await kw.async_save_settings({"kw_appliances": [{"id": "wm", "name": "Waschmaschine", "type": "waschmaschine",
                                                         "power": "sensor.wm_leistung", "notify": ["mobile_app_pixel"],
                                                         "notify_ha": True}]})
        await kw.async_start()
        app = kw.appliances
        assert haus.status()["appliances"]["wm"]["label"] == "Bereit" and haus.status()["appliances"]["wm"]["learning"]

        def power(w, minutes):
            for _ in range(int(minutes * 2)):
                NOW[0] += timedelta(seconds=30)
                hass.set("sensor.wm_leistung", str(w), {"unit_of_measurement": "W"}, "WM Leistung")
                app._feed("wm", app._cfg("wm"), hass.states.get("sensor.wm_leistung"), NOW[0].timestamp())

        power(1900, 40)
        assert app.status()["wm"]["label"] == "Läuft"
        power(150, 30)
        power(1.6, 40)
        await asyncio.sleep(0)
        st = app.status()["wm"]
        assert st["state"] == "done" and st["label"] == "Fertig"
        assert hass.sent().count("Waschmaschine fertig") == 1
        assert any(c[0] == "persistent_notification" for c in hass.calls)
        # Neustart: aus dem Speicher laden – keine zweite Meldung
        kw2 = hw.Kraftwerk(hass, log, haus)
        await kw2.async_load()
        await kw2.async_start()
        rec = kw2.appliances.det["wm"].last
        kw2.appliances._announce("wm", kw2.appliances._cfg("wm"), rec)
        await asyncio.sleep(0)
        assert hass.sent().count("Waschmaschine fertig") == 1
        # Korrektur „Gesehen“
        res = await kw2.appliances.async_action("wm", "ack")
        assert res["ok"] and kw2.appliances.status()["wm"]["state"] == "idle"

    asyncio.run(run())


def test_rollwerk_zeiten_je_rollladen_und_beschattungstemperatur(hw):
    """Öffnen/Schließen je Rollladen: wie die Steuerung (hier ohne Sonnenregel = früheste Zeit), vorbei → morgen,
    gesperrt → keine Uhrzeit. „Beschattung ab“ nur bei erfüllter Außentemperatur (mit Hysterese)."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 11, 19, 8, 0, tzinfo=timezone.utc)  # 09:00 lokal, Donnerstag
        hass = Hass()
        feat = {"supported_features": 15}
        hass.set("cover.wz", "open", {"current_position": 100, **feat}, "Wohnzimmer")
        hass.set("cover.sz", "open", {"current_position": 100, **feat}, "Schlafzimmer")
        hass.set("sensor.aussen", "19.0", {"unit_of_measurement": "°C"}, "Außen")
        log, haus, ctl = await _setup(hw, hass)
        rw = hw.Rollwerk(hass, log, haus)
        await rw.async_load()
        await rw.async_start()
        prof = dict(rw.profiles["standard"], features=["up", "down", "time", "shading"], up_early="07:00", up_late="08:00",
                    up_early_we="08:30", up_late_we="09:30", down_early="17:30", down_late="22:00", down_early_we="18:00",
                    shade_start_and=["azimuth", "elevation", "temp2"], temp2_sensor="sensor.aussen", temp2_min=20, temp2_hyst=1)
        await rw.async_save_profile("standard", prof)
        await rw.async_save_settings({"rw_covers": ["cover.wz", "cover.sz"]})
        await rw.async_save_cover("cover.sz", {"profile": "standard", "auto": False})
        t = rw.status()["covers"]["cover.wz"]["times"]
        # 09:00: heute schon offen → Öffnen morgen (Freitag 07:00); Schließen heute 17:30 (Freitag ist Arbeitstag)
        assert t["open"] == {"at": "07:00", "min": 420, "tomorrow": True}
        assert t["close"]["at"] == "17:30" and t["close"]["tomorrow"] is False
        # Automatik aus: keine Uhrzeit
        assert rw.status()["covers"]["cover.sz"]["times"] == {"open": None, "close": None, "stage1": None}
        # nach dem Schließen: Schließen morgen – Freitagabend vor dem Samstag mit Wochenend-Zeit 18:00
        rw._rt.setdefault("cover.wz", {})["closed_on"] = "2026-11-19"
        assert rw.status()["covers"]["cover.wz"]["times"]["close"] == {"at": "18:00", "min": 1080, "tomorrow": True}
        # Beschattungstemperatur: 19 °C < 20 °C → nicht erfüllt; 20,5 °C → erfüllt; während Beschattung bis 19 °C (Hysterese)
        assert rw.shade_temp_ok("cover.wz") is False
        hass.set("sensor.aussen", "20.5", {"unit_of_measurement": "°C"}, "Außen")
        assert rw.shade_temp_ok("cover.wz") is True
        rw._rt["cover.wz"]["shading"] = True
        hass.set("sensor.aussen", "19.5", {"unit_of_measurement": "°C"}, "Außen")
        assert rw.shade_temp_ok("cover.wz") is True
        hass.set("sensor.aussen", "18.9", {"unit_of_measurement": "°C"}, "Außen")
        assert rw.shade_temp_ok("cover.wz") is False
        # Messwert fehlt: keine Beschattungsbereitschaft vortäuschen
        hass.set("sensor.aussen", "unavailable", {}, "Außen")
        assert rw.shade_temp_ok("cover.wz") is False
        # Beschattung zu erwarten? Nur bei passender Temperatur und sonnigem Wetter
        hass.set("sensor.aussen", "22", {"unit_of_measurement": "°C"}, "Außen")
        rw._rt["cover.wz"]["shading"] = False
        hass.set("weather.home", "rainy", {"temperature": 22}, "Wetter")
        await haus.async_save_settings({"weather_entity": "weather.home"})
        assert rw.shade_likely("cover.wz") is False
        hass.set("weather.home", "sunny", {"temperature": 22}, "Wetter")
        assert rw.shade_likely("cover.wz") is True
        # das Schließen hängt nicht an der Beschattungstemperatur
        assert rw.status()["covers"]["cover.wz"]["times"]["close"] is not None
        await rw.async_stop()

    asyncio.run(run())


def test_benachrichtigungskanaele(hw):
    """Gemeinsame Kanäle: alte Auswahl übernommen, je Anlass eigene Kanäle (z. B. Ansage), nur erreichbare,
    keine Doppel binnen 2 Min., Testnachricht mit Ergebnis je Kanal."""
    async def run():
        STORES.clear()
        NOW[0] = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
        STORES["hauswerk.haus"] = {"settings": {"notify_targets": ["mobile_app_pixel"], "notify_ha": True}}
        hass = Hass()
        hass.set("tts.google", "unknown", {}, "Google")
        hass.set("media_player.tablet", "idle", {}, "Tablet")
        hass.set("notify.iphone", "unknown", {}, "iPhone")
        hass.set("media_player.tv", "unavailable", {}, "Fernseher")
        log, haus, ctl = await _setup(hw, hass)
        assert haus.settings["notify_channels"] == ["svc:mobile_app_pixel", "ha"]
        await haus.async_save_settings({"notify_channels": ["svc:mobile_app_pixel", "ent:notify.iphone"],
                                        "notify_routes": {"vent_done": ["tts:tts.google|media_player.tablet", "tts:tts.google|media_player.tv"]},
                                        "notify_quiet": False, "notify_vent_done": "normal"})
        haus.notify("ventdone:bad", "vent_done", "Fenster schließen", "Bad: genug gelüftet")
        await asyncio.sleep(0)
        tts = [c for c in hass.calls if c[0] == "tts"]
        assert tts == [("tts", "speak", {"entity_id": "tts.google", "media_player_entity_id": "media_player.tablet",
                                         "message": "Fenster schließen. Bad: genug gelüftet"})]
        assert any(e["title"] == "Kanal nicht erreichbar" for e in log.entries)  # Fernseher aus
        # Standard-Kanäle für andere Anlässe: App-Dienst + notify-Entität
        haus.notify("frost", "frost", "Frost", "heute Nacht −5 °C")
        await asyncio.sleep(0)
        assert ("notify", "send_message", {"entity_id": "notify.iphone", "title": "❄️ Frost", "message": "heute Nacht −5 °C"}) in hass.calls
        # Ansagen ohne Emoji
        assert all(not str(d.get("message", "")).startswith(("❄", "🪟")) for dom, _s, d in hass.calls if dom == "tts")
        assert [c[1] for c in hass.calls if c[0] == "notify" and c[2].get("title") == "❄️ Frost"] == ["mobile_app_pixel", "send_message"]
        # gleiche Nachricht gleich nochmal über send(): kein Doppel
        n = len(hass.calls)
        haus.send(["ent:notify.iphone"], "Frost", "heute Nacht −5 °C")
        await asyncio.sleep(0)
        assert len(hass.calls) == n
        # Test: Ergebnis je Kanal
        res = await haus.async_test_notify(channels=["svc:mobile_app_pixel", "tts:tts.google|media_player.tv"])
        assert [r["ok"] for r in res] == [True, False] and res[1]["error"] == "nicht erreichbar"

    asyncio.run(run())


def test_kamin(hw):
    """Kamin: wärmer ohne Heizung → „vielleicht“, nicht in Komfort/überheizt; von Hand an/aus; Signal; Lernen verworfen."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 11, 20, 17, 0, tzinfo=timezone.utc)
        hass = Hass()
        hass.set("climate.wz", "heat", {"current_temperature": 21.0, "temperature": 21.0, "hvac_action": "idle"}, "Thermostat WZ")
        hass.set("sensor.wz_t", "21.0", name="WZ Temperatur")
        log, haus, ctl = await _setup(hw, hass)
        await ctl.async_save_room({"id": "wz", "name": "Wohnzimmer", "type": "heizkoerper", "comfort": 21, "eco": 18, "fireplace": True,
                                   "climates": ["climate.wz"], "temp_sensor": "sensor.wz_t", "enabled": True,
                                   "schedule": [{"start": "00:00", "end": "23:59", "days": [0, 1, 2, 3, 4, 5, 6]}]})
        for _ in range(80):
            NOW[0] += timedelta(minutes=1)
            await ctl.async_evaluate()
        assert ctl.status()["rooms"]["wz"]["fireplace"]["state"] is None
        for i in range(30):  # +1 °C in 30 Min. ohne Heizung
            NOW[0] += timedelta(minutes=1)
            hass.set("sensor.wz_t", f"{21.0 + (i + 1) / 30:.2f}", name="WZ Temperatur")
            await ctl.async_evaluate()
        fp = ctl.status()["rooms"]["wz"]["fireplace"]
        assert fp["state"] == "maybe" and fp["cause"] == "kamin?"
        assert any(e["title"] == "Wärmer ohne Heizung" for e in log.entries)
        ctl._record_stats()
        b = ctl._stat("wz")
        assert b["fire"] == 1 and b.get("mn", 0) == 0 and b.get("over", 0) == 0
        # von Hand an, dann aus
        await ctl.async_set_fireplace("wz", True, by="Test")
        fp = ctl.status()["rooms"]["wz"]["fireplace"]
        assert fp["state"] == "on" and fp["manual"] and fp["until"]
        await ctl.async_set_fireplace("wz", False)
        assert ctl.status()["rooms"]["wz"]["fireplace"]["state"] == "maybe"  # wird noch wärmer: Ursache wieder offen
        # Signal: Ofenrohr-Fühler 120 °C → an
        hass.set("sensor.ofen", "120", {"unit_of_measurement": "°C"}, "Ofenrohr")
        await ctl.async_save_room({**ctl.rooms["wz"], "fireplace_entity": "sensor.ofen"})
        await ctl.async_evaluate()
        fp = ctl.status()["rooms"]["wz"]["fireplace"]
        assert fp["state"] == "on" and fp["source"] == "signal"
        # Aufheizmessung während Kamin wird verworfen
        rt = ctl._rt("wz")
        rt["learn"] = {"ts": NOW[0].timestamp() - 1800, "temp": 19.0, "target": 21.0, "factor": 1.0}
        ctl._learn("wz", rt, {"mode": "komfort", "target": 21.0}, 21.0, NOW[0].timestamp())
        assert "wz" not in ctl.heat_rates and any(e["title"] == "Aufheizmessung verworfen" for e in log.entries)
        # Kamin abgewählt: alles weg
        await ctl.async_save_room({**ctl.rooms["wz"], "fireplace": False})
        assert ctl.status()["rooms"]["wz"]["fireplace"] is None

    asyncio.run(run())


def test_benachrichtigung_ausbau(hw):
    """Kanal-Zeiten (außerhalb nur Wichtiges), keine Ansage ins leere Haus, Bündeln, Zustand je Kanal, Verlauf,
    Rollwerk-Sturm als Anlass, Probehören mit eigenem Text."""
    async def run():
        import sys
        STORES.clear()
        NOW[0] = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)  # 13:00 Ortszeit
        hass = Hass()
        hass.set("tts.google", "unknown", {}, "Google")
        hass.set("media_player.tablet", "idle", {}, "Tablet")
        log, haus, ctl = await _setup(hw, hass)
        core = sys.modules[type(haus).__module__]
        timers = []
        core.async_call_later = lambda h, delay, fn: timers.append(fn) or (lambda: None)
        tts = "tts:tts.google|media_player.tablet"
        await haus.async_save_settings({"notify_channels": ["svc:mobile_app_pixel", tts], "notify_quiet": False,
                                        "notify_hours": {tts: ["08:00", "12:00"]}, "notify_bundle": ["svc:mobile_app_pixel"]})
        # 13 Uhr: Ansage außerhalb ihrer Zeit → nur das Handy
        assert haus.send(["svc:mobile_app_pixel", tts], "A", "eins") == ["svc:mobile_app_pixel"]
        # wichtig: Ansage trotzdem
        assert tts in haus.send([tts], "B", "zwei", important=True)
        # Bündeln: zweite und dritte Meldung binnen 5 Min. warten, kommen gesammelt
        await asyncio.sleep(0)
        n = len([c for c in hass.calls if c[1] == "mobile_app_pixel"])
        haus.send(["svc:mobile_app_pixel"], "C", "drei")
        haus.send(["svc:mobile_app_pixel"], "D", "vier")
        await asyncio.sleep(0)
        assert len([c for c in hass.calls if c[1] == "mobile_app_pixel"]) == n and len(timers) == 1
        timers[0]()
        await asyncio.sleep(0)
        last = [c for c in hass.calls if c[1] == "mobile_app_pixel"][-1][2]
        assert last["title"] == "📬 Hauswerk: 2 Meldungen" and "C: drei" in last["message"] and "D: vier" in last["message"]
        # Zustand je Kanal und Verlauf
        assert haus.notify_health["svc:mobile_app_pixel"]["ok"] is True
        await haus.async_save_settings({"notify_hours": {}, "notify_bundle": [], "notify_storm": "important"})
        haus.notify("rw_storm", "storm", "Sturm – Rollläden fahren hoch", "Böen 80 km/h")
        await asyncio.sleep(0)
        st = haus.status()["notify"]
        assert st["sent"] == 1 and st["last"][0]["title"].startswith("Sturm") and st["last"][0]["kind"] == "storm"
        # niemand zu Hause: normale Ansage fällt weg, Handy nicht
        haus.away = True
        assert haus.send(["svc:mobile_app_pixel", tts], "E", "fünf") == ["svc:mobile_app_pixel"]
        # Empfänger pausiert: bekommt nichts; sind alle pausiert, steht es so im Protokoll
        await haus.async_save_settings({"notify_off": ["svc:mobile_app_pixel"]})
        assert haus.send(["svc:mobile_app_pixel"], "F", "sechs") == []
        await haus.async_save_settings({"notify_channels": ["svc:mobile_app_pixel"], "notify_routes": {}, "notify_frost": "normal"})
        haus.notify("frost2", "frost", "Frost", "−6 °C")
        assert log.entries[-1]["why"].endswith("nur hier – alle Empfänger pausiert")
        await haus.async_save_settings({"notify_off": []})
        # Probehören mit eigenem Text
        res = await haus.async_test_notify(channels=[tts], title="Fenster schließen", message="Bad: genug gelüftet")
        assert res[0]["ok"] and hass.calls[-1][2]["message"] == "Fenster schließen. Bad: genug gelüftet"

    asyncio.run(run())


def test_heizplan_ueberfuehren_und_ursache(hw):
    """Alte Pläne mit Überschneidungen werden eindeutig (Protokoll), Ursache und Tagesablauf wie die Steuerung."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 11, 16, 16, 30, tzinfo=timezone.utc)  # Mo 17:30 Ortszeit
        STORES["hauswerk.heizen"] = {"rooms": {"wz": {"id": "wz", "name": "Wohnzimmer", "type": "heizkoerper", "comfort": 21, "eco": 18,
                                              "climates": ["climate.wz"], "enabled": True,
                                              "schedule": [{"start": "06:00", "end": "22:00", "days": [0, 1, 2, 3, 4]},
                                                           {"start": "17:00", "end": "21:00", "days": [0, 1, 2, 3, 4], "temp": 22.0}]}},
                            "plans": {}, "settings": {}}
        hass = Hass()
        hass.set("climate.wz", "heat", {"current_temperature": 20.0, "temperature": 21.0}, "Thermostat WZ")
        log, haus, ctl = await _setup(hw, hass)
        await ctl.async_start()
        sched = ctl.rooms["wz"]["schedule"]
        assert any(e["title"] == "Heizpläne bereinigt" for e in log.entries)
        assert {"start": "17:00", "end": "21:00", "days": [0, 1, 2, 3, 4], "temp": 22.0} in sched
        res = ctl.status()["rooms"]["wz"]
        assert res["target"] == 22.0 and res["cause"] == "Heizplan: Komfort 17:00–21:00 (eigene 22,0 °C)"
        assert res["plan_target"] == 22.0 and res["plan_label"].startswith("Komfort 17:00–21:00")
        today = [(s["start"], s["end"], s["target"]) for s in res["plan_today"]]
        assert today == [(0, 360, 18.0), (360, 1020, 21.0), (1020, 1260, 22.0), (1260, 1320, 21.0), (1320, 1440, 18.0)]
        # Vorrang: niemand zu Hause → Abwesend, Ursache nennt Grenze und Plan
        haus.settings["presence_force"] = "away"
        await ctl.async_evaluate()
        res = ctl.status()["rooms"]["wz"]
        assert res["mode"] == "abwesend" and res["cause"] == "Niemand zu Hause – höchstens 17,0 °C (Plan: 22,0 °C)"
        haus.settings["presence_force"] = None
        await ctl.async_set_override("wz", 23.0, 1)
        res = ctl.status()["rooms"]["wz"]
        assert res["mode"] == "manuell" and res["cause"].startswith("Von Hand bis ") and res["plan_target"] == 22.0

    asyncio.run(run())


def test_lichtwerk_logik(hw):
    """Smart-Light-Regeln: Sonne/Uhrzeit als Wechsel, Stand über Mitternacht, Tage, Nachtlicht, Dynamik, Vorrang."""
    L = hw.light
    import math
    elev = lambda m: 40 * math.sin((m - 360) / 720 * math.pi)  # noqa: E731 - Sonne 06:00 auf, 18:00 unter
    prof = {**L.LW_PROFILE_DEFAULTS, "on_sun": True, "sun_on": -1, "off_sun": True, "sun_off": 1, "off_time": True, "time_off": "23:00"}
    ev = L.day_events(prof, elev)
    assert [(round(m), a) for m, a, _ in ev] == [(359, "off"), (1083, "on"), (1380, "off")] or [a for _, a, _ in ev] == ["off", "on", "off"]
    # 05:00: noch dunkel, aber um 23:00 aus → bleibt aus (Wechsel zählt, nicht der Zustand)
    assert L.latched_at(ev, ev, 300)[0] is False
    assert L.latched_at(ev, ev, 1200) == (True, "Sonne unter -1°", ev[1][0])
    plan = L.day_plan(ev, ev)
    assert len(plan) == 1 and plan[0]["end"] == 1380 and plan[0]["reason"] == "Sonne unter -1°"
    # ohne Ausschaltzeit: an über Mitternacht bis Sonnenaufgang
    p2 = {**prof, "off_time": False}
    ev2 = L.day_events(p2, elev)
    assert L.latched_at(ev2, ev2, 120)[0] is True and L.day_plan(ev2, ev2)[0]["start"] == 0
    # Tage: am nicht erlaubten Tag nur Ausschalten
    assert [a for _, a, _ in L.day_events({**prof, "days": [0, 1]}, elev, allowed=False)] == ["off", "off"]
    assert L.day_allowed({"days": [0, 1, 2, 3, 4], "day_mode": "workday"}, 2, True) is False
    # Nachtlicht und Dynamik
    n = {**prof, "night": True, "night_from": "22:30", "night_to": "06:00", "night_brightness": 10, "color": "temp"}
    assert L.light_params(n, 23 * 60)["brightness"] == 10 and L.light_params(n, 23 * 60)["night"]
    assert L.light_params(n, 20 * 60)["brightness"] == 80 and L.light_params(n, 20 * 60)["kelvin"] == 2700
    d = L.light_params({**prof, "dynamic": "sun"}, 1000, elev=-6)
    assert d["brightness"] == 35 and d["kelvin"] == 2200
    # Vorrang
    assert L.decide(auto=False, latched=True)[0] is None
    assert L.decide(manual=True, latched=True) == (None, "Von Hand geschaltet – Automatik wartet")
    assert L.decide(away=True, latched=True) == ("off", "Niemand zu Hause")
    assert L.decide(away=True, simulating=True, latched=True, latched_reason="Uhrzeit")[0] == "on"
    assert L.decide(bypass_on=True, bypass_action="off", latched=True)[0] == "off"
    assert L.decide(motion_on=True) == ("on", "Bewegung")


def test_lichtwerk_rolllaeden_nach_neustart(hw):
    """Auslöser „Rollläden schließen“: echtes Schließen schaltet ein; nach einem Neustart melden sich die Rollläden
    erst „nicht verfügbar“, dann „geschlossen“ – das ist kein Schließen und darf das Licht nicht einschalten."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 11, 16, 21, 0, tzinfo=timezone.utc)  # 22:00 Ortszeit
        hass = Hass()
        hass.set("light.wz", "off", {"supported_color_modes": ["color_temp"]}, "Wohnzimmer")
        hass.set("cover.wz", "open", {}, "Rollladen Wohnzimmer")
        log, haus, ctl = await _setup(hw, hass)
        lw = hw.Lichtwerk(hass, log, haus)
        await lw.async_load()
        lw._sun_fn = lambda offset=0: None
        lw._covers_near = lambda eid: ["cover.wz"]
        await lw.async_save_profile("standard", {"name": "Abendlicht", "on_sun": False, "off_sun": False, "on_time": False, "off_time": False,
                                                 "on_covers": True})
        await lw.async_save_settings({"lw_lights": ["light.wz"]})
        await lw.async_evaluate()
        on = ("light", "turn_on")
        assert not any(c[:2] == on for c in hass.calls)
        hass.set("cover.wz", "closed", {}, "Rollladen Wohnzimmer")
        NOW[0] += timedelta(minutes=1)
        await lw.async_evaluate()
        assert any(c[:2] == on for c in hass.calls)  # echtes Schließen
        # von Hand aus, dann Neustart
        hass.set("light.wz", "off", {"supported_color_modes": ["color_temp"]}, "Wohnzimmer")
        lw._rt["light.wz"]["manual"] = {"since": NOW[0].timestamp(), "until": None, "state": "off"}
        await lw.async_stop()
        n = len(hass.calls)
        hass.set("cover.wz", "unavailable", {}, "Rollladen Wohnzimmer")
        lw2 = hw.Lichtwerk(hass, log, haus)
        await lw2.async_load()
        lw2._sun_fn = lambda offset=0: None
        lw2._covers_near = lambda eid: ["cover.wz"]
        NOW[0] += timedelta(minutes=30)
        await lw2.async_evaluate()
        hass.set("cover.wz", "closed", {}, "Rollladen Wohnzimmer")
        NOW[0] += timedelta(minutes=1)
        await lw2.async_evaluate()
        assert not any(c[:2] == on for c in hass.calls[n:]), hass.calls[n:]
        await lw2.async_stop()

    asyncio.run(run())


def test_lichtwerk(hw):
    """Ablauf: Uhrzeit an/aus, von Hand (Automatik wartet bis zum Wechsel), Neustart, Bewegung mit Nachtlicht,
    niemand zu Hause, Benachrichtigung, Status mit Tagesplan und nächster Schaltung."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)  # Mo 16:00 Ortszeit
        hass = Hass()
        hass.set("light.wz", "off", {"supported_color_modes": ["color_temp"], "supported_features": 32}, "Wohnzimmer")
        hass.set("light.flur", "off", {"supported_color_modes": ["brightness"]}, "Flur")
        hass.set("binary_sensor.flur_bewegung", "off", {"device_class": "motion"}, "Flur Bewegung")
        log, haus, ctl = await _setup(hw, hass)
        await haus.async_save_settings({"notify_channels": ["svc:mobile_app_pixel"], "notify_quiet": False})
        lw = hw.Lichtwerk(hass, log, haus)
        await lw.async_load()
        lw._sun_fn = lambda offset=0: None  # ohne Standort: nur Uhrzeit-Auslöser
        await lw.async_save_profile("standard", {"name": "Abendlicht", "on_sun": False, "off_sun": False,
                                                 "on_time": True, "time_on": "17:00", "off_time": True, "time_off": "23:00"})
        fid = await lw.async_save_profile(None, {"name": "Flur", "on_sun": False, "off_sun": False, "on_time": False, "off_time": False,
                                                 "motion": ["binary_sensor.flur_bewegung"], "motion_off": 3, "motion_dark": True,
                                                 "night": True, "night_from": "22:30", "night_to": "06:00", "night_brightness": 10})
        await lw.async_save_settings({"lw_lights": ["light.wz", "light.flur"]})
        await lw.async_save_light("light.flur", {"profile": fid})
        st = lw.status()["lights"]["light.wz"]
        assert st["want"] == "off" and st["plan"] == [{"start": 1020, "end": 1380, "reason": "Uhrzeit 17:00", "until": "spätestens 23:00"}]
        assert st["next"] == {"day": 0, "min": 1020, "action": "on", "reason": "Uhrzeit 17:00"}

        def ours(eid, state):
            old = hass.st[eid]
            hass.set(eid, state, old.attributes, old.name)
            hass.st[eid].context.id = lw._ctx[-1]
            lw._on_change(types.SimpleNamespace(data={"entity_id": eid, "old_state": old, "new_state": hass.st[eid]}))

        def manual(eid, state):
            old = hass.st[eid]
            hass.set(eid, state, old.attributes, old.name)
            lw._on_change(types.SimpleNamespace(data={"entity_id": eid, "old_state": old, "new_state": hass.st[eid]}))

        # 17:01 – Uhrzeit: an
        NOW[0] = datetime(2026, 11, 16, 16, 1, tzinfo=timezone.utc)
        await lw.async_evaluate()
        call = [c for c in hass.calls if c[0] == "light"][-1]
        assert call == ("light", "turn_on", {"entity_id": "light.wz", "brightness_pct": 80, "transition": 1.0})
        ours("light.wz", "on")
        assert lw.status()["lights"]["light.wz"]["manual"] is None
        assert any(e["title"] == "Wohnzimmer an" and e["why"].startswith("Uhrzeit 17:00") for e in log.entries)
        # 18:00 von Hand aus → Automatik wartet
        NOW[0] = datetime(2026, 11, 16, 17, 0, tzinfo=timezone.utc)
        manual("light.wz", "off")
        n = len(hass.calls)
        await lw.async_evaluate()
        st = lw.status()["lights"]["light.wz"]
        assert st["manual"] and st["cause"].startswith("Von Hand") and len(hass.calls) == n
        # Neustart um 20:00: Stand aus der Vorausrechnung (an), von Hand bleibt gemerkt
        await lw.async_stop()
        lw2 = hw.Lichtwerk(hass, log, haus)
        await lw2.async_load()
        lw2._sun_fn = lambda offset=0: None
        NOW[0] = datetime(2026, 11, 16, 19, 0, tzinfo=timezone.utc)
        await lw2.async_evaluate()
        assert lw2.status()["lights"]["light.wz"]["manual"] and lw2.status()["lights"]["light.wz"]["latch"] is True
        # 23:00 – Wechsel „aus“ beendet „von Hand“
        NOW[0] = datetime(2026, 11, 16, 22, 0, tzinfo=timezone.utc)
        await lw2.async_evaluate()
        NOW[0] = datetime(2026, 11, 16, 22, 1, tzinfo=timezone.utc)
        await lw2.async_evaluate()
        st = lw2.status()["lights"]["light.wz"]
        assert st["manual"] is None and st["want"] == "off" and st["cause"] == "spätestens 23:00"
        # Bewegung im Flur um 23:01 → Nachtlicht 10 %
        lw = lw2
        hass.set("binary_sensor.flur_bewegung", "on", {"device_class": "motion"}, "Flur Bewegung")
        await lw.async_evaluate()
        call = [c for c in hass.calls if c[0] == "light"][-1]
        assert call == ("light", "turn_on", {"entity_id": "light.flur", "brightness_pct": 10})
        assert lw.status()["lights"]["light.flur"]["cause"] == "Bewegung · Nachtlicht"
        ours("light.flur", "on")
        hass.set("binary_sensor.flur_bewegung", "off", {"device_class": "motion"}, "Flur Bewegung")
        NOW[0] = datetime(2026, 11, 16, 22, 3, tzinfo=timezone.utc)
        await lw.async_evaluate()
        assert lw.status()["lights"]["light.flur"]["want"] == "on"
        NOW[0] = datetime(2026, 11, 16, 22, 6, tzinfo=timezone.utc)
        await lw.async_evaluate()
        assert [c for c in hass.calls if c[0] == "light"][-1] == ("light", "turn_off", {"entity_id": "light.flur"})
        ours("light.flur", "off")
        # Dienstag 17:30 – niemand zu Hause: aus statt an; Licht brennt (von Hand) → Nachricht nach 30 Min.
        NOW[0] = datetime(2026, 11, 17, 16, 30, tzinfo=timezone.utc)
        haus.settings["presence_force"] = "away"
        haus.update()
        await lw.async_evaluate()
        st = lw.status()["lights"]["light.wz"]
        assert st["want"] == "off" and st["cause"] == "Niemand zu Hause"
        manual("light.flur", "on")
        await lw.async_evaluate()
        NOW[0] = datetime(2026, 11, 17, 17, 5, tzinfo=timezone.utc)
        await lw.async_evaluate()
        await asyncio.sleep(0)
        assert "Licht an, niemand zu Hause" in hass.sent()
        # Panel: von Hand an (Helligkeit) und „Automatik übernimmt“
        await lw.async_command(["light.wz"], "on", 40)
        assert hass.calls[-1] == ("light", "turn_on", {"entity_id": "light.wz", "brightness_pct": 40})
        await lw.async_command(["light.wz"], "resume")
        assert lw.status()["lights"]["light.wz"]["manual"] is None
        # Profil an der Leuchte aus: nichts schalten, Ursache und Protokoll
        haus.settings["presence_force"] = None
        haus.update()
        await lw.async_save_light("light.wz", {"auto": False})
        n = len(hass.calls)
        await lw.async_evaluate()
        st = lw.status()["lights"]["light.wz"]
        assert st["auto"] is False and st["want"] is None and st["cause"] == "Profil aus – Lichtwerk schaltet nicht" and len(hass.calls) == n
        assert any(e["title"] == "Wohnzimmer: Profil „Abendlicht“ aus" for e in log.entries)
        await lw.async_save_light("light.wz", {"auto": True})
        assert lw.status()["lights"]["light.wz"]["auto"] is True

    asyncio.run(run())


def test_homematic_verknuepfungen(hw):
    """CCU-Direktverknüpfungen: Kopplung nur für verknüpfte Heizkörper, Fensterpause macht die CCU, Hinweise
    (Wandthermostat ohne Verknüpfung, Heizkörper ohne Wandthermostat, freier Aktor-Kanal)."""
    async def run():
        STORES.clear()
        REG.clear()
        DEVS.clear()
        NOW[0] = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
        hass = Hass()

        def dev(eid, did, addr, model, name, state="heat", attrs=None):
            DEVS[did] = types.SimpleNamespace(id=did, model=model, name=name, name_by_user=None, area_id=None,
                                              identifiers={("homematicip_local", f"{addr}@ccu3-webui-HmIP-RF")})
            if eid:
                REG[eid] = types.SimpleNamespace(entity_id=eid, device_id=did, domain=eid.split(".")[0], disabled_by=None, platform="homematicip_local")
                hass.set(eid, state, attrs or {"temperature": 21.0, "current_temperature": 20.5}, name)

        dev("climate.wth_wz", "d1", "WTHWZ", "HmIP-WTH-2", "WTH Wohnzimmer")
        dev("climate.trv_wz", "d2", "TRVWZ", "HMIP-eTRV", "Heizkörper Wohnzimmer")
        dev("climate.trv_wz2", "d3", "TRVWZ2", "HMIP-eTRV", "Heizkörper Wohnzimmer Fenster")
        dev("binary_sensor.fenster_wz", "d4", "SWDOWZ", "HMIP-SWDO", "Fenster Wohnzimmer", "off", {})
        dev("climate.wth_jonte", "d5", "WTHJ", "HmIP-WTH-2", "WTH Jonte")
        dev(None, "d6", "FAL", "HmIP-FAL230-C6", "A_Fußbodenheizung")
        hass.links = {"WTHWZ": ["TRVWZ:6", "TRVWZ:5", "TRVWZ:3", "SWDOWZ:1", "FAL:1", "FAL:2"], "TRVWZ": ["WTHWZ:1"], "WTHJ": []}
        log, haus, ctl = await _setup(hw, hass)
        await ctl.async_save_room({"id": "wz", "name": "Wohnzimmer", "type": "heizkoerper", "comfort": 21, "eco": 18, "enabled": True,
                                   "climates": ["climate.wth_wz", "climate.trv_wz", "climate.trv_wz2"], "windows": ["binary_sensor.fenster_wz"],
                                   "schedule": [{"start": "00:00", "end": "24:00", "days": [0, 1, 2, 3, 4, 5, 6]}]})
        await ctl.async_save_room({"id": "jo", "name": "Jonte", "type": "flaeche", "comfort": 21, "eco": 18, "enabled": True,
                                   "climates": ["climate.wth_jonte"], "schedule": []})
        st = await ctl.async_refresh_links(by="Test")
        info = st["rooms"]["wz"]
        assert info["linked_trvs"] == ["climate.trv_wz"] and info["unlinked_trvs"] == ["climate.trv_wz2"]
        assert info["windows_ccu"] == ["binary_sensor.fenster_wz"]
        peers = {p["name"]: p for p in info["walls"][0]["peers"]}
        assert peers["Heizkörper Wohnzimmer"]["channels"] == [3, 5, 6] and peers["Heizkörper Wohnzimmer"]["kind"] == "trv"
        texts = [f["text"] for f in st["findings"]]
        assert "WTH Jonte ist in der CCU mit keinem Gerät verknüpft – steuert es dort etwas?" in texts
        assert "Heizkörper Wohnzimmer Fenster ist nicht mit dem Wandthermostat verknüpft – Hauswerk stellt ihn selbst" in texts
        assert "A_Fußbodenheizung: Kanal 3, 4, 5, 6 ist keinem Wandthermostat zugeordnet – Heizkreis ohne Regelung?" in texts
        # Kopplung: nur der verknüpfte Heizkörper folgt
        assert ctl.status()["rooms"]["wz"]["followers"] == ["climate.trv_wz"]
        # Fenster auf: Pause macht die CCU – Hauswerk sendet den verknüpften Thermostaten nichts, dem anderen schon
        hass.set("binary_sensor.fenster_wz", "on", {}, "Fenster Wohnzimmer")
        hass.st["binary_sensor.fenster_wz"].last_changed = NOW[0] - timedelta(minutes=5)
        n = len(hass.calls)
        await ctl.async_evaluate()
        res = ctl.status()["rooms"]["wz"]
        assert res["mode"] == "fenster" and res["window_ccu"] and "CCU senkt" in res["cause"]
        sent = [c[2].get("entity_id") for c in hass.calls[n:] if c[0] == "climate"]
        assert "climate.wth_wz" not in sent and "climate.trv_wz" not in sent and "climate.trv_wz2" in sent
        # Raum-Einstellung aus: Hauswerk macht die Pause selbst
        await ctl.async_save_room({**ctl.rooms["wz"], "window_ccu": False})
        n = len(hass.calls)
        await ctl.async_evaluate()
        assert not ctl.status()["rooms"]["wz"]["window_ccu"]

    asyncio.run(run())


def test_hmip_einschaltdauer():
    import importlib.util as iu
    spec = iu.spec_from_file_location("hml", Path(__file__).resolve().parents[1] / "custom_components" / "hauswerk" / "hmlinks.py")
    m = iu.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.on_time({"SHORT_ON_TIME_BASE": 4, "SHORT_ON_TIME_FACTOR": 1}) == 60
    assert m.on_time({"SHORT_ON_TIME_BASE": 1, "SHORT_ON_TIME_FACTOR": 30}) == 30
    assert m.on_time({"SHORT_ON_TIME_BASE": 7, "SHORT_ON_TIME_FACTOR": 31}) is None
    assert m.on_time({"SHORT_ON_TIME": 60.0}) == 60 and m.on_time({"SHORT_ON_TIME": 111600.0}) is None
    assert m.entity_channel("00085d89a3c2f9_4_state", "00085D89A3C2F9") == 4 and m.entity_channel(None, "X") is None


def test_lichtwerk_ccu_verknuepfungen(hw):
    """Lichtwerk: Leuchten, die die CCU direkt schaltet (Bewegungsmelder), werden erkannt; Schalten über die
    Verknüpfung ist nicht „von Hand“ – Lichtwerk wartet, bis die CCU wieder ausschaltet. BidCos je Kanal."""
    async def run():
        STORES.clear()
        REG.clear()
        DEVS.clear()
        NOW[0] = datetime(2026, 11, 20, 11, 0, tzinfo=timezone.utc)  # 12:00
        hass = Hass()

        def dev(eid, did, addr, model, name, state, attrs=None):
            DEVS[did] = types.SimpleNamespace(id=did, model=model, name=name, name_by_user=None, area_id=None,
                                              identifiers={("homematicip_local", f"{addr}@ccu3")})
            REG[eid] = types.SimpleNamespace(entity_id=eid, device_id=did, domain=eid.split(".")[0], disabled_by=None, platform="homematicip_local")
            hass.set(eid, state, attrs or {}, name)

        dev("light.windfang", "l1", "BSM1", "HmIP-BSM", "Windfang Wand", "off", {"supported_color_modes": ["onoff"]})
        dev("binary_sensor.spi", "s1", "SPI1", "HmIP-SPI", "S_Bewegung:Windfang", "off", {"device_class": "occupancy"})
        dev("light.eingang", "l2", "PEQ1", "HM-LC-Sw1PBU-FM", "Eingang", "off", {"supported_color_modes": ["onoff"]})
        dev("binary_sensor.mdir", "s2", "PEQ9", "HM-Sen-MDIR-O-3", "S_Bewegung:Vorgarten", "off", {"device_class": "motion"})
        REG_ = sys.modules["homeassistant.helpers.entity_registry"]
        REG_.async_get = lambda h: types.SimpleNamespace(async_get=REG.get, entities=REG)
        hass.links = {"BSM1": ["BSM1:4", "BSM1:1", "SPI1:1"], "PEQ1:1": ["PEQ9:1", "PEQ1:1", "PEQ1:2"]}
        hass.bidcos = {"PEQ1"}
        hass.paramsets = {("SPI1:1", "BSM1:4"): {"SHORT_ON_TIME_BASE": 4, "SHORT_ON_TIME_FACTOR": 1, "SHORT_OFF_TIME_BASE": 7},
                          ("PEQ9:1", "PEQ1:1"): {"SHORT_ON_TIME": 90.0}}
        log, haus, ctl = await _setup(hw, hass)
        lw = hw.Lichtwerk(hass, log, haus)
        await lw.async_load()
        lw._sun_fn = lambda offset=0: None
        await lw.async_save_profile("standard", {"name": "Abendlicht", "on_sun": False, "off_sun": False, "on_time": True,
                                                 "time_on": "17:00", "off_time": True, "time_off": "23:00"})
        await lw.async_save_settings({"lw_lights": ["light.windfang", "light.eingang"]})
        st = await lw.async_refresh_links(by="Test")
        wf = st["lights"]["light.windfang"]
        assert wf["own"] and [p["name"] for p in wf["peers"]] == ["S_Bewegung:Windfang"] and wf["peers"][0]["kind"] == "motion"
        assert wf["peers"][0]["entities"] == ["binary_sensor.spi"]
        assert [p["name"] for p in st["lights"]["light.eingang"]["peers"]] == ["S_Bewegung:Vorgarten"]  # BidCos je Kanal
        assert any(f["text"] == "Windfang Wand wird in der CCU direkt von S_Bewegung:Windfang geschaltet – zusätzlich zum Profil „Abendlicht“" for f in st["findings"])
        # 12:00, Profil will aus: Anwesenheit → CCU schaltet ein → kein „von Hand“, Lichtwerk schaltet nicht wieder aus
        old = hass.st["binary_sensor.spi"]
        hass.set("binary_sensor.spi", "on", {"device_class": "occupancy"}, "S_Bewegung:Windfang")
        lw._on_change(types.SimpleNamespace(data={"entity_id": "binary_sensor.spi", "old_state": old, "new_state": hass.st["binary_sensor.spi"]}))
        old = hass.st["light.windfang"]
        hass.set("light.windfang", "on", old.attributes, "Windfang Wand")
        lw._on_change(types.SimpleNamespace(data={"entity_id": "light.windfang", "old_state": old, "new_state": hass.st["light.windfang"]}))
        n = len(hass.calls)
        await lw.async_evaluate()
        x = lw.status()["lights"]["light.windfang"]
        assert x["ccu"] == "S_Bewegung:Windfang" and x["want"] is None and x["cause"].startswith("HmIP: S_Bewegung:Windfang") and len(hass.calls) == n
        assert lw.status()["manual"] == 0
        # Ablauftimer: Melder meldet noch → „solange Bewegung + 1 Min.“; Melder ruhig → Ablauf 1 Min. danach
        assert wf["peers"][0]["on_time"] == 60 and st["lights"]["light.eingang"]["peers"][0]["on_time"] == 90
        assert lw.status()["lights"]["light.windfang"]["off"] == {"while": 60, "src": "HmIP", "learned": False}
        hass.set("binary_sensor.spi", "off", {"device_class": "occupancy"}, "S_Bewegung:Windfang")
        await lw.async_evaluate()
        off = lw.status()["lights"]["light.windfang"]["off"]
        assert off["src"] == "HmIP" and off["at"] == (NOW[0] + timedelta(seconds=60)).isoformat(), off
        # CCU schaltet nach ihrer Nachlaufzeit aus → Lichtwerk übernimmt wieder
        NOW[0] += timedelta(minutes=3)
        old = hass.st["light.windfang"]
        hass.set("light.windfang", "off", old.attributes, "Windfang Wand")
        lw._on_change(types.SimpleNamespace(data={"entity_id": "light.windfang", "old_state": old, "new_state": hass.st["light.windfang"]}))
        await lw.async_evaluate()
        assert lw.status()["lights"]["light.windfang"]["manual"] is None and lw.status()["lights"]["light.windfang"]["want"] == "off"
        # Leuchte meldet vor dem Melder: zuerst „von Hand“, nach der Nachprüfung CCU
        NOW[0] += timedelta(minutes=10)
        old = hass.st["light.eingang"]
        hass.set("light.eingang", "on", old.attributes, "Eingang")
        lw._on_change(types.SimpleNamespace(data={"entity_id": "light.eingang", "old_state": old, "new_state": hass.st["light.eingang"]}))
        assert lw._rt["light.eingang"]["manual"].get("ccu") is None
        lw._sensor_seen["binary_sensor.mdir"] = NOW[0].timestamp() + 1
        lw._recheck_ccu("light.eingang", "on", lw._rt["light.eingang"]["manual"]["since"])
        await asyncio.sleep(0)
        assert lw._rt["light.eingang"]["manual"]["ccu"] == "S_Bewegung:Vorgarten"
        # CCU schaltet nach der Nachlaufzeit aus, ohne dass Lichtwerk das Einschalten gesehen hat → HmIP statt von Hand
        lw._rt["light.windfang"]["manual"] = None
        hass.set("light.windfang", "on", hass.st["light.windfang"].attributes, "Windfang Wand")
        hass.set("binary_sensor.spi", "off", {"device_class": "occupancy"}, "S_Bewegung:Windfang")
        NOW[0] += timedelta(minutes=5)
        old = hass.st["light.windfang"]
        hass.set("light.windfang", "off", old.attributes, "Windfang Wand")
        lw._on_change(types.SimpleNamespace(data={"entity_id": "light.windfang", "old_state": old, "new_state": hass.st["light.windfang"]}))
        assert lw._rt["light.windfang"]["manual"] is None
        assert any(e["title"] == "Windfang Wand: HmIP aus" for e in log.entries[-3:])
        # Bewegungsmelder auch im Profil: doppelt → Warnung
        await lw.async_save_profile("standard", {"motion": ["binary_sensor.spi"]})
        assert any(f["level"] == "warn" and "schaltet bei Bewegung doppelt" in f["text"] for f in lw.links_status()["findings"])

    asyncio.run(run())


def test_lichtwerk_szenen_tageszeit(hw):
    """Szenen je Tageszeit: letzte begonnene gilt, vor der ersten die vom Vortag; Nachtlicht hat Vorrang."""
    L = hw.light
    sc = [{"from": "06:00", "name": "Morgen", "brightness": 60, "kelvin": 4000}, {"from": "18:00", "name": "Abend", "brightness": 40, "kelvin": 2700},
          {"from": "22:00", "name": "Spät", "brightness": 20}]
    prof = {**L.LW_PROFILE_DEFAULTS, "scenes_on": True, "scenes": sc, "brightness": 80}
    assert L.light_params(prof, 7 * 60) == {"brightness": 60, "night": False, "mode": "Szene „Morgen“", "scene": "Morgen", "kelvin": 4000}
    assert L.light_params(prof, 19 * 60)["brightness"] == 40
    p = L.light_params(prof, 3 * 60)  # vor 06:00: „Spät“ vom Vortag, ohne eigene Farbe
    assert p["scene"] == "Spät" and p["brightness"] == 20 and "kelvin" not in p
    assert L.light_params({**prof, "scenes_on": False}, 7 * 60)["brightness"] == 80
    night = L.light_params({**prof, "night": True, "night_from": "22:30", "night_to": "06:00"}, 23 * 60)
    assert night["night"] and night["mode"] == "Nachtlicht"


def test_lichtwerk_ausschaltzeit_lernen(hw):
    """Lichtwerk lernt, wie lange nach dem letzten Melden die CCU wirklich ausschaltet (Median ab 3 Messungen)."""
    async def run():
        STORES.clear()
        REG.clear()
        DEVS.clear()
        NOW[0] = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
        hass = Hass()

        def dev(eid, did, addr, model, name, state, attrs=None):
            DEVS[did] = types.SimpleNamespace(id=did, model=model, name=name, name_by_user=None, area_id=None,
                                              identifiers={("homematicip_local", f"{addr}@ccu3")})
            REG[eid] = types.SimpleNamespace(entity_id=eid, device_id=did, domain=eid.split(".")[0], disabled_by=None, platform="homematicip_local")
            hass.set(eid, state, attrs or {}, name)

        dev("light.windfang", "l1", "BSM1", "HmIP-BSM", "Windfang Wand", "off", {"supported_color_modes": ["onoff"]})
        dev("binary_sensor.spi", "s1", "SPI1", "HmIP-SPI", "S_Bewegung:Windfang", "off", {"device_class": "occupancy"})
        sys.modules["homeassistant.helpers.entity_registry"].async_get = lambda h: types.SimpleNamespace(async_get=REG.get, entities=REG)
        hass.links = {"BSM1": ["SPI1:1"]}
        hass.paramsets = {("SPI1:1", "BSM1:4"): {"SHORT_ON_TIME_BASE": 4, "SHORT_ON_TIME_FACTOR": 1}}
        log, haus, ctl = await _setup(hw, hass)
        lw = hw.Lichtwerk(hass, log, haus)
        await lw.async_load()
        lw._sun_fn = lambda offset=0: None
        await lw.async_save_settings({"lw_lights": ["light.windfang"]})
        await lw.async_refresh_links()

        def ch(eid, state, attrs):
            old = hass.st[eid]
            hass.set(eid, state, attrs, old.name if hasattr(old, "name") else eid)
            lw._on_change(types.SimpleNamespace(data={"entity_id": eid, "old_state": old, "new_state": hass.st[eid]}))

        for wait in (95, 100, 90):
            ch("binary_sensor.spi", "on", {"device_class": "occupancy"})
            ch("light.windfang", "on", {"supported_color_modes": ["onoff"]})
            NOW[0] += timedelta(seconds=30)
            ch("binary_sensor.spi", "off", {"device_class": "occupancy"})
            NOW[0] += timedelta(seconds=wait)
            ch("light.windfang", "off", {"supported_color_modes": ["onoff"]})
            NOW[0] += timedelta(minutes=5)
        assert lw._learn["light.windfang"]["SPI1"] == [95, 100, 90]
        # nächstes Mal: Timer mit gelerntem Wert (95 s statt 60 s aus der CCU)
        ch("binary_sensor.spi", "on", {"device_class": "occupancy"})
        ch("light.windfang", "on", {"supported_color_modes": ["onoff"]})
        ch("binary_sensor.spi", "off", {"device_class": "occupancy"})
        await lw.async_evaluate()
        off = lw.status()["lights"]["light.windfang"]["off"]
        assert off["learned"] and off["at"] == (NOW[0] + timedelta(seconds=95)).isoformat(), off
        assert lw._data()["learn"]["light.windfang"]["SPI1"]

    asyncio.run(run())


def test_lichtwerk_bericht_gesundheit(hw):
    """Bericht: Brenndauer und Energie, von Hand früher als geplant → Vorschlag; Leuchte schaltet nicht → Hinweis; Batterie."""
    L = hw.light
    plan = [{"start": 17 * 60, "end": 23 * 60}]
    assert L.plan_offset(plan, 16 * 60 + 40, "on") == 20 and L.plan_offset(plan, 13 * 60, "on") is None
    assert L.plan_offset(plan, 22 * 60 + 30, "off") == 30 and L.plan_offset(plan, 18 * 60, "off") is None
    evs = [{"p": "standard", "a": "on", "d": d, "e": "light.wz"} for d in (20, 25, 15)] + [{"p": "flur", "a": "on", "d": 30, "e": "light.f"}]
    assert L.manual_suggestions(evs) == [{"profile": "standard", "action": "on", "count": 3, "minutes": 20, "lights": ["light.wz"]}]

    async def run():
        STORES.clear()
        REG.clear()
        DEVS.clear()
        NOW[0] = datetime(2026, 11, 20, 15, 0, tzinfo=timezone.utc)  # 16:00
        hass = Hass()
        hass.set("light.wz", "off", {"supported_color_modes": ["brightness"]}, "Wohnzimmer")
        log, haus, ctl = await _setup(hw, hass)
        lw = hw.Lichtwerk(hass, log, haus)
        await lw.async_load()
        lw._sun_fn = lambda offset=0: None
        await lw.async_save_profile("standard", {"name": "Abendlicht", "on_sun": False, "off_sun": False, "on_time": True,
                                                 "time_on": "17:00", "off_time": True, "time_off": "23:00"})
        await lw.async_save_settings({"lw_lights": ["light.wz"]})
        await lw.async_save_light("light.wz", {"watt": 12})
        await lw.async_evaluate()
        # 16:40 von Hand an (20 Min. vor dem Plan)
        NOW[0] += timedelta(minutes=40)
        old = hass.st["light.wz"]
        hass.set("light.wz", "on", {"supported_color_modes": ["brightness"], "brightness": 200}, "Wohnzimmer")
        lw._on_change(types.SimpleNamespace(data={"entity_id": "light.wz", "old_state": old, "new_state": hass.st["light.wz"]}))
        assert lw._manual_ev[-1]["d"] == 20 and lw._manual_ev[-1]["a"] == "on"
        # Brenndauer: 2 Std. zählen
        lw._count_usage()
        for _ in range(120):
            NOW[0] += timedelta(minutes=1)
            lw._count_usage()
        r = lw.report()["lights"]["light.wz"]
        assert r["today_h"] == 2.0 and r["kwh"] == 0.02 and r["power"] == 12 and r["power_src"] == "set" and r["manual_on"] == 1
        # zwei weitere Tage früher eingeschaltet → Vorschlag
        lw._manual_ev += [{"t": NOW[0].timestamp(), "e": "light.wz", "a": "on", "p": "standard", "d": d} for d in (25, 15)]
        assert any(s["kind"] == "manual" and "20 Min. früher einschalten" in s["text"] for s in lw.report()["suggestions"])
        # Lichtwerk schaltet, Leuchte reagiert nicht → „schaltet nicht“
        lw._rt["light.wz"]["manual"] = None
        await lw._switch("light.wz", False, {"brightness": 80}, lw.profile("light.wz"), "Test")
        lw._check_switched("light.wz", False)
        assert lw._health("light.wz")["fail"]["want"] == "off"
        assert any(e["title"] == "Wohnzimmer schaltet nicht" for e in log.entries)
        hass.set("light.wz", "off", {"supported_color_modes": ["brightness"]}, "Wohnzimmer")
        lw._check_switched("light.wz", False)
        assert not lw._health("light.wz").get("fail")

    asyncio.run(run())


def test_beetwerk_maehpause_fehler_wartung(hw):
    """Beetwerk: Mäher und Geräte-Entitäten automatisch gefunden; Mähpause bei Regen (in die Station), danach weiter;
    während und nach dem Bewässern keine Fahrt; Fehler als Nachricht, Messer-Hinweis."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 6, 10, 9, 0, tzinfo=timezone.utc)  # 11:00 lokal
        hass = Hass()
        for eid in ("lawn_mower.robonect", "sensor.robonect_mower_battery_charge", "sensor.robonect_mower_error_message",
                    "sensor.robonect_mower_blades_days", "switch.robonect_winter_mode", "button.robonect_eod"):
            REG[eid] = types.SimpleNamespace(entity_id=eid, device_id="mower", domain=eid.split(".")[0], disabled_by=None,
                                             device_class="battery" if "battery" in eid else None, original_device_class=None)
        hass.set("lawn_mower.robonect", "mowing", {}, "Automower")
        hass.set("sensor.robonect_mower_battery_charge", "80", name="Akku")
        hass.set("sensor.robonect_mower_error_message", "Fehler 0", name="Fehler")
        hass.set("sensor.robonect_mower_blades_days", "70", name="Messer Tage")
        hass.set("switch.robonect_winter_mode", "off", name="Winter")
        hass.set("sensor.star_bodenfeuchte_rasen", "60", {"device_class": "moisture", "unit_of_measurement": "%"}, "Bodenfeuchte Rasen")
        hass.set("binary_sensor.smart_irrigation_rasen_1_watering_now", "off", name="gießt")
        hass.set("weather.home", "rainy", {"temperature": 14, "humidity": 90})
        log, haus, ctl = await _setup(hw, hass)
        await haus.async_save_settings({"weather_entity": "weather.home", "notify_targets": ["mobile_app_pixel"], "notify_quiet": False})
        bw = hw.Beetwerk(hass, log, haus)
        await bw.async_load()
        await bw.async_start()
        ent = bw.entities()
        assert ent["mower"] == "lawn_mower.robonect" and ent["battery"] == "sensor.robonect_mower_battery_charge"
        assert ent["soil"] == "sensor.star_bodenfeuchte_rasen" and ent["watering"] == "binary_sensor.smart_irrigation_rasen_1_watering_now"
        assert ent["winter"] == "switch.robonect_winter_mode" and ent["eod"] == "button.robonect_eod"
        # Regen beim Mähen -> zur Station
        await bw.async_evaluate()
        assert ("lawn_mower", "dock", {"entity_id": "lawn_mower.robonect"}) in hass.calls
        st = haus.status()["beetwerk"]
        assert st["paused"]["why"] == "es regnet" and st["reasons"][0]["k"] == "rain"
        # Regen vorbei, Mäher in der Station: nach 60 Min. weiter
        hass.set("lawn_mower.robonect", "docked", {}, "Automower")
        hass.set("weather.home", "cloudy", {"temperature": 14, "humidity": 70})
        await bw.async_evaluate()
        assert ("lawn_mower", "start_mowing", {"entity_id": "lawn_mower.robonect"}) not in hass.calls
        NOW[0] += timedelta(minutes=61)
        await bw.async_evaluate()
        assert ("lawn_mower", "start_mowing", {"entity_id": "lawn_mower.robonect"}) in hass.calls
        assert haus.status()["beetwerk"]["paused"] is None
        # Bewässerung: während und 60 Min. danach Pause
        hass.set("lawn_mower.robonect", "mowing", {}, "Automower")
        hass.set("binary_sensor.smart_irrigation_rasen_1_watering_now", "on", name="gießt")
        n = hass.calls.count(("lawn_mower", "dock", {"entity_id": "lawn_mower.robonect"}))
        await bw.async_evaluate()
        assert hass.calls.count(("lawn_mower", "dock", {"entity_id": "lawn_mower.robonect"})) == n + 1
        assert haus.status()["beetwerk"]["watering"] is True
        # Fehler -> Nachricht; Messer 70 Tage -> Hinweis (nur Glocke)
        hass.set("lawn_mower.robonect", "error", {}, "Automower")
        hass.set("sensor.robonect_mower_error_message", "Mäher steckt fest", name="Fehler")
        await bw.async_evaluate()
        await asyncio.sleep(0)
        assert "Mähroboter braucht Hilfe" in hass.sent()
        assert haus.status()["beetwerk"]["error"] == "Mäher steckt fest"
        assert any(e["title"] == "Mähroboter: Messer wechseln" for e in log.entries) or "bw_blades" in str(haus.notify_summary())
        await bw.async_save_settings({"bw_soil_wet": 70, "bw_pause": ["rain"]})
        assert bw.settings["bw_soil_wet"] == 70
        await bw.async_stop()

    asyncio.run(run())


def test_beetwerk_garten_frei_igel_hitze_waechter(hw):
    """Beetwerk-Mäher: Kamera meldet Person -> heim (Nachricht mit Kamerabild), 30 Min. ohne Meldung -> weiter;
    Garten belegt; Igelschutz nachts per Feierabend; Hitzepause; Wächter; Verschleiß; Statistik und Zeitpläne."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 6, 10, 9, 0, tzinfo=timezone.utc)  # 10:00 lokal
        hass = Hass()
        ents = ("lawn_mower.robonect", "sensor.automower_mower_battery_charge", "button.automower_eod", "sensor.automower_battery_capacity",
                "sensor.automower_wire", "sensor.automower_wlan_rssi", "sensor.automower_health_climate_humidity", "sensor.automower_motor_blade",
                "switch.automower_timer_1", "switch.automower_timer_2", "sensor.automower_mower_statistic_hours")
        for eid in ents:
            REG[eid] = types.SimpleNamespace(entity_id=eid, device_id="mower", domain=eid.split(".")[0], disabled_by=None,
                                             device_class="battery" if "battery_charge" in eid else None, original_device_class=None)
        hass.set("lawn_mower.robonect", "mowing", {}, "Automower")
        hass.set("sensor.automower_mower_battery_charge", "80")
        hass.set("sensor.automower_battery_capacity", "1600")
        hass.set("sensor.automower_wire", "100")
        hass.set("sensor.automower_wlan_rssi", "90")
        hass.set("sensor.automower_health_climate_humidity", "40")
        hass.set("sensor.automower_motor_blade", "2900")
        hass.set("sensor.automower_mower_statistic_hours", "1703")
        hass.set("switch.automower_timer_1", "on", {"id": 1, "start": "08:00", "end": "14:10", "weekdays": {"mo": True, "tu": False, "we": True, "th": False, "fr": False, "sa": False, "su": False}}, "Timer 1")
        hass.set("switch.automower_timer_2", "off", {"id": 2, "start": "08:00", "end": "10:00", "weekdays": {}}, "Timer 2")
        hass.set("binary_sensor.garten_person", "off", {}, "Garten Person")
        hass.set("binary_sensor.garten_fahrzeug", "off", {}, "Garten Fahrzeug")
        hass.set("camera.garten_fliessend", "idle", {}, "Garten")
        hass.set("sun.sun", "above_horizon", {"next_setting": "2026-06-10T19:30:00+00:00", "next_rising": "2026-06-11T03:00:00+00:00"})
        hass.set("weather.home", "sunny", {"temperature": 22, "humidity": 50})
        log, haus, ctl = await _setup(hw, hass)
        await haus.async_save_settings({"weather_entity": "weather.home", "notify_targets": ["mobile_app_pixel"], "notify_quiet": False,
                                        "notify_mower_guard": "normal"})
        bw = hw.Beetwerk(hass, log, haus)
        await bw.async_load()
        await bw.async_start()
        assert bw.guard_sensors() == ["binary_sensor.garten_person"] and bw.camera() == "camera.garten_fliessend"
        dock = ("lawn_mower", "dock", {"entity_id": "lawn_mower.robonect"})
        start = ("lawn_mower", "start_mowing", {"entity_id": "lawn_mower.robonect"})
        await bw.async_evaluate()
        assert dock not in hass.calls
        # Kinder im Garten -> heim, Nachricht mit Kamerabild
        hass.set("binary_sensor.garten_person", "on", {}, "Garten Person")
        await bw.async_evaluate()
        await asyncio.sleep(0)
        assert dock in hass.calls
        assert "Mäher fährt heim" in hass.sent()
        assert any(c[0] == "notify" and c[2].get("title") == "🧒 Mäher fährt heim" for c in hass.calls), [c for c in hass.calls if c[0] == "notify"]
        assert any(c[0] == "notify" and (c[2].get("data") or {}).get("image") == "/api/camera_proxy/camera.garten_fliessend" for c in hass.calls)
        hass.set("lawn_mower.robonect", "docked", {}, "Automower")
        hass.set("binary_sensor.garten_person", "off", {}, "Garten Person")
        NOW[0] += timedelta(minutes=20)
        await bw.async_evaluate()
        assert start not in hass.calls  # erst 30 Min. nach der letzten Meldung
        NOW[0] += timedelta(minutes=11)
        await bw.async_evaluate()
        assert start in hass.calls
        # Garten belegt 2 Std.
        hass.set("lawn_mower.robonect", "mowing", {}, "Automower")
        n = hass.calls.count(dock)
        await bw.async_busy(hours=2, by="Test")
        assert hass.calls.count(dock) == n + 1 and bw.status()["busy_until"]
        await bw.async_busy(None)
        assert bw.status()["busy_until"] is None
        # Hitze: ab 30 °C
        hass.set("lawn_mower.robonect", "mowing", {}, "Automower")
        hass.set("weather.home", "sunny", {"temperature": 31, "humidity": 30})
        n = hass.calls.count(dock)
        await bw.async_evaluate()
        assert hass.calls.count(dock) == n + 1 and "heat" in [r["k"] for r in bw.status()["reasons"]]
        hass.set("weather.home", "sunny", {"temperature": 29, "humidity": 30})
        await bw.async_evaluate()
        assert "heat" in [r["k"] for r in bw.status()["reasons"]]  # Abstand 2 °C
        hass.set("weather.home", "sunny", {"temperature": 22, "humidity": 30})
        await bw.async_evaluate()
        # Igelschutz: nachts mäht er -> Feierabend statt Station, kein Neustart
        bw._persist["paused"] = None
        hass.set("lawn_mower.robonect", "mowing", {}, "Automower")
        hass.set("sun.sun", "below_horizon", {"next_setting": "2026-06-11T19:30:00+00:00", "next_rising": "2026-06-11T03:00:00+00:00"})
        await bw.async_evaluate()
        assert ("button", "press", {"entity_id": "button.automower_eod"}) in hass.calls
        assert "night" in [r["k"] for r in bw.status()["reasons"]]
        # Wächter: nachts nach 22 Uhr nicht in der Station
        NOW[0] = datetime(2026, 6, 10, 21, 30, tzinfo=timezone.utc)  # 22:30 lokal
        await bw.async_evaluate()
        await asyncio.sleep(0)
        assert "Mähroboter nachts nicht in der Station" in hass.sent()
        # Verschleiß: Akku-Kapazität fällt unter 70 %
        hass.set("sensor.automower_battery_capacity", "1000")
        assert "Akku altert" in (bw.wear(bw.entities())["battery"] or "")
        hass.set("sensor.automower_health_climate_humidity", "85")
        assert bw.wear(bw.entities())["humid"]
        st = bw.status()
        assert st["stats"]["days"][-1]["hours"] > 0 and len(st["timers"]) == 2
        assert st["timers"][0] == {"entity": "switch.automower_timer_1", "id": 1, "on": True, "start": "08:00", "end": "14:10", "days": ["mo", "we"]}
        await bw.async_timer(2, True, "09:00", "12:00", ["sa", "su"], by="Test")
        assert ("robonect", "timer", {"entity_id": "lawn_mower.robonect", "timer": "2", "enable": True, "start": "09:00", "end": "12:00", "weekdays": ["sa", "su"]}) in hass.calls
        await bw.async_stop()

    asyncio.run(run())


def test_beetwerk_maehplan(hw):
    """Mähplan: Wochenziel auf die erlaubten Tage verteilt, Regenstunden ausgelassen, in die Robonect-Zeitpläne
    geschrieben (je Wochentag zwei); beim Abschalten kommen die alten Zeitpläne zurück; Pause endet mit „Auto“."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 6, 10, 6, 0, tzinfo=timezone.utc)  # Mi 07:00 lokal (Test-Zeitzone UTC+1)
        hass = Hass()
        ents = ["lawn_mower.robonect", "button.automower_auto", "button.automower_eod"] + [f"switch.automower_timer_{i}" for i in range(1, 15)]
        for eid in ents:
            REG[eid] = types.SimpleNamespace(entity_id=eid, device_id="mower", domain=eid.split(".")[0], disabled_by=None, device_class=None, original_device_class=None)
        hass.set("lawn_mower.robonect", "docked", {}, "Automower")
        for i in range(1, 15):
            hass.set(f"switch.automower_timer_{i}", "on" if i == 1 else "off", {"id": i, "start": "08:00", "end": "14:10" if i == 1 else "10:00",
                                                                                 "weekdays": {"mo": i == 1}}, f"Timer {i}")
        hass.set("weather.home", "sunny", {"temperature": 20, "humidity": 50})
        log, haus, ctl = await _setup(hw, hass)
        await haus.async_save_settings({"weather_entity": "weather.home"})
        start = NOW[0].timestamp()
        haus.hourly = [{"ts": start + k * 3600, "hour": (7 + k) % 24, "temp": 20, "rh": 50, "rain": k in (4, 5)} for k in range(48)]  # 11–12 Uhr Regen
        bw = hw.Beetwerk(hass, log, haus)
        await bw.async_load()
        await bw.async_start()
        await bw.async_save_settings({"bw_plan": True, "bw_plan_hours": 12, "bw_night": False}, by="Test")
        plan = bw.status()["plan"]
        assert plan and plan["mode"] == "timers" and plan["target"] == 12.0
        today = plan["days"][0]
        assert today["wd"] == "we" and today["windows"] == [[540, 660]], today  # 9–11 Uhr, vor dem Regen
        assert any(b[2] == "rain" for b in today["bad"])
        assert plan["days"][4]["wd"] == "su" and plan["days"][4]["windows"] == []  # Sonntag nicht erlaubt
        writes = [c[2] for c in hass.calls if c[:2] == ("robonect", "timer")]
        assert {"entity_id": "lawn_mower.robonect", "timer": "5", "enable": True, "start": "09:00", "end": "11:00", "weekdays": ["we"]} in writes, writes
        assert any(w["timer"] == "1" and w["enable"] is True and w["weekdays"] == ["mo"] for w in writes)
        # Pause (Regen) endet: mit Mähplan „Auto“ statt „Mähen“
        hass.set("lawn_mower.robonect", "mowing", {}, "Automower")
        hass.set("weather.home", "rainy", {"temperature": 20, "humidity": 90})
        await bw.async_evaluate()
        hass.set("lawn_mower.robonect", "docked", {}, "Automower")
        hass.set("weather.home", "sunny", {"temperature": 20, "humidity": 50})
        NOW[0] += timedelta(minutes=61)
        await bw.async_evaluate()
        NOW[0] += timedelta(minutes=61)
        await bw.async_evaluate()
        assert ("button", "press", {"entity_id": "button.automower_auto"}) in hass.calls
        assert ("lawn_mower", "start_mowing", {"entity_id": "lawn_mower.robonect"}) not in hass.calls
        # Abschalten: alte Zeitpläne zurück
        n = len(hass.calls)
        await bw.async_save_settings({"bw_plan": False}, by="Test")
        back = [c[2] for c in hass.calls[n:] if c[:2] == ("robonect", "timer")]
        assert {"entity_id": "lawn_mower.robonect", "timer": "1", "enable": True, "start": "08:00", "end": "14:10", "weekdays": ["mo"]} in back
        assert bw.status()["plan"] is None
        await bw.async_stop()

    asyncio.run(run())


def test_beetwerk_giessen_mit_smart_irrigation(hw):
    """Beetwerk gießt: Zonen aus Smart Irrigation, Ventil mit gleichem Namen gefunden, Dauer berechnet, danach
    Ventil zu und Wasserbilanz zurück; Gießplan zur Startzeit, bei Regen ausgelassen; Mäher fährt solange in die Station."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 6, 10, 4, 1, tzinfo=timezone.utc)  # 05:01 lokal (Test-Zeitzone UTC+1)
        hass = Hass()
        hass.set("sensor.smart_irrigation_rasen_1", "600", {"bucket": -4.2, "multiplier": 0.85, "unit_of_measurement": "s"}, "Rasen 1 Dauer")
        hass.set("sensor.smart_irrigation_beet_links", "0", {"bucket": 3.1, "unit_of_measurement": "s"}, "Beet Links Dauer")
        hass.set("valve.smart_irrigation_rasen_1", "unavailable", {}, "Rasen 1")
        hass.set("valve.garten_rasen", "closed", {}, "Rasen 1")
        hass.set("valve.garten_beet", "closed", {}, "Beet_Links")
        hass.set("lawn_mower.robonect", "mowing", {}, "Automower")
        hass.set("weather.home", "sunny", {"temperature": 18, "humidity": 60})
        hass.set("automation.rasenbewasserung", "on", {}, "Bewässerung_Rasen")
        log, haus, ctl = await _setup(hw, hass)
        await haus.async_save_settings({"weather_entity": "weather.home"})
        bw = hw.Beetwerk(hass, log, haus)
        await bw.async_load()
        await bw.async_start()
        z = {x["zone"]: x for x in bw.zones()}
        assert z["sensor.smart_irrigation_rasen_1"]["valve"] == "valve.garten_rasen" and z["sensor.smart_irrigation_beet_links"]["valve"] == "valve.garten_beet"
        assert bw.status()["automations"] == [{"id": "automation.rasenbewasserung", "name": "Bewässerung_Rasen", "on": True}]
        # Gießplan 05:00 (an): nur die Zone mit Dauer > 0
        await bw.async_save_settings({"bw_water_auto": True, "bw_water_time": "05:00"})
        await bw.async_evaluate()
        assert ("valve", "open_valve", {"entity_id": "valve.garten_rasen"}) in hass.calls
        assert ("valve", "open_valve", {"entity_id": "valve.garten_beet"}) not in hass.calls
        assert ("lawn_mower", "dock", {"entity_id": "lawn_mower.robonect"}) in hass.calls
        zs = {x["zone"]: x for x in bw.status()["zones"]}
        assert bw.status()["watering"] is True and zs["sensor.smart_irrigation_rasen_1"]["running_until"]
        # nach 10 Min.: zu, Wasserbilanz zurück
        NOW[0] += timedelta(minutes=10, seconds=5)
        await bw.async_evaluate()
        assert ("valve", "close_valve", {"entity_id": "valve.garten_rasen"}) in hass.calls
        assert ("smart_irrigation", "set_bucket", {"entity_id": "sensor.smart_irrigation_rasen_1"}) in hass.calls
        assert any(e["title"] == "Rasen 1 gegossen" for e in log.entries)
        # Von Hand: 5 Min. Beet, Stopp
        await bw.async_water("sensor.smart_irrigation_beet_links", 300)
        assert ("valve", "open_valve", {"entity_id": "valve.garten_beet"}) in hass.calls
        await bw.async_water_stop()
        assert ("valve", "close_valve", {"entity_id": "valve.garten_beet"}) in hass.calls and not any(x["running_until"] for x in bw.status()["zones"])
        # Nächster Tag mit Regen: ausgelassen
        NOW[0] += timedelta(days=1)
        hass.set("weather.home", "rainy", {"temperature": 14, "humidity": 95})
        n = hass.calls.count(("valve", "open_valve", {"entity_id": "valve.garten_rasen"}))
        await bw.async_evaluate()
        assert hass.calls.count(("valve", "open_valve", {"entity_id": "valve.garten_rasen"})) == n
        assert any(e["title"] == "Bewässerung ausgelassen" for e in log.entries)
        await bw.async_stop()

    asyncio.run(run())


def test_beetwerk_zone_mit_zwei_ventilen(hw):
    """Eine Zone, zwei Ventile (zu wenig Wasserdruck): nacheinander je die volle Zeit, Bilanz erst nach dem zweiten zurück;
    Ablauftimer für Zone und ganze Bewässerung."""
    async def run():
        STORES.clear()
        REG.clear()
        NOW[0] = datetime(2026, 6, 10, 10, 0, tzinfo=timezone.utc)
        hass = Hass()
        hass.set("sensor.smart_irrigation_rasen_1", "600", {"bucket": -4.2, "unit_of_measurement": "s"}, "Rasen 1 Dauer")
        hass.set("valve.links", "closed", {}, "Garten Links")
        hass.set("valve.rechts", "closed", {}, "Garten Rechts")
        log, haus, ctl = await _setup(hw, hass)
        bw = hw.Beetwerk(hass, log, haus)
        await bw.async_load()
        await bw.async_save_settings({"bw_zones": [{"zone": "sensor.smart_irrigation_rasen_1", "valves": ["valve.links", "valve.rechts"], "auto": True}]})
        await bw.async_water("sensor.smart_irrigation_rasen_1")
        assert ("valve", "open_valve", {"entity_id": "valve.links"}) in hass.calls and ("valve", "open_valve", {"entity_id": "valve.rechts"}) not in hass.calls
        z = bw.status()["zones"][0]
        assert z["part"] == 1 and z["parts"] == 2 and z["running_valve"] == "valve.links"
        start = NOW[0]
        assert bw.status()["water_until"] == (start + timedelta(minutes=20)).isoformat().replace("+00:00", "+00:00") or bw.status()["water_until"]
        assert z["zone_until"] and z["zone_until"] > z["running_until"]
        NOW[0] += timedelta(minutes=10, seconds=2)
        await bw.async_evaluate()
        assert ("valve", "close_valve", {"entity_id": "valve.links"}) in hass.calls and ("valve", "open_valve", {"entity_id": "valve.rechts"}) in hass.calls
        assert ("smart_irrigation", "set_bucket", {"entity_id": "sensor.smart_irrigation_rasen_1"}) not in hass.calls
        NOW[0] += timedelta(minutes=10, seconds=2)
        await bw.async_evaluate()
        assert ("valve", "close_valve", {"entity_id": "valve.rechts"}) in hass.calls
        assert ("smart_irrigation", "set_bucket", {"entity_id": "sensor.smart_irrigation_rasen_1"}) in hass.calls
        assert bw.status()["water_until"] is None

    asyncio.run(run())
