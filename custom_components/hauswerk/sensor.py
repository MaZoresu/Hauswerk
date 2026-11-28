"""Sensoren je Raum: Solltemperatur (mit Betriebsart) und Heizdauer heute."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from datetime import timedelta

from homeassistant.const import MATCH_ALL, EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import perf
from .entity import RoomEntity, setup_room_entities


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    setup_room_entities(
        hass,
        entry,
        async_add_entities,
        lambda ctl, room_id: [TargetSensor(ctl, room_id), HeatTimeSensor(ctl, room_id)],
    )
    async_add_entities([PerfSensor()])


class PerfSensor(SensorEntity):
    """Rechenlast von Hauswerk in % (Anteil der Zeit, die Hauswerk rechnet) – Einzelwerte als Attribute (nicht aufgezeichnet)."""

    _attr_should_poll = False
    _attr_has_entity_name = False
    _attr_name = "Hauswerk Leistung"
    _attr_unique_id = "hauswerk_leistung"
    _attr_icon = "mdi:speedometer"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _unrecorded_attributes = frozenset({MATCH_ALL})

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_track_time_interval(self.hass, self._tick, timedelta(minutes=1)))

    async def _tick(self, _now=None) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> float:
        pts = perf.summary()["points"]
        # „minute“ enthält bei Heizwerk, Rollwerk und Lichtwerk das Berechnen – nicht doppelt zählen
        calc = {k.split(".")[0] for k in pts if k.endswith(".berechnen")}
        return round(sum(v["load"] for k, v in pts.items()
                         if not k.startswith(("status.", "ha.", "meldung.")) and not (k.endswith(".minute") and k.split(".")[0] in calc)), 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = perf.summary()
        return {"punkte": s["points"], "meldungen_bytes": s["sizes"], "panels": s["panels"]}


class TargetSensor(RoomEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermostat-auto"

    @property
    def unique_id(self) -> str:
        return f"hauswerk_{self.room_id}_target"

    @property
    def name(self) -> str:
        return f"Hauswerk {self.room.get('name', self.room_id)} Soll"

    @property
    def native_value(self) -> float | None:
        return self.result.get("target")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        r = self.result
        return {
            "betriebsart": r.get("mode"),
            "betriebsart_text": r.get("mode_label"),
            "raumtemperatur": r.get("room_temp"),
            "luftfeuchte": r.get("humidity"),
            "fenster_offen": r.get("windows_open"),
            "heizt": r.get("heating"),
            "manuell_bis": r.get("override_until"),
            "heizungsart": self.room.get("type"),
        }


class HeatTimeSensor(RoomEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:fire"

    @property
    def unique_id(self) -> str:
        return f"hauswerk_{self.room_id}_heat_today"

    @property
    def name(self) -> str:
        return f"Hauswerk {self.room.get('name', self.room_id)} Heizdauer heute"

    @property
    def native_value(self) -> int:
        report = self.controller.report(1).get(self.room_id) or [{}]
        return int(report[-1].get("heat_min", 0))
