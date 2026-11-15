"""Sensoren je Raum: Solltemperatur (mit Betriebsart) und Heizdauer heute."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
