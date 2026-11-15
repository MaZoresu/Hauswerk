"""Gemeinsame Hilfen für die Hauswerk-Entitäten."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODULE_HEATING, SIGNAL_ROOMS, SIGNAL_UPDATE
from .controller import Heizen


class HauswerkEntity(Entity):
    _attr_should_poll = False

    def __init__(self, controller: Heizen) -> None:
        self.controller = controller

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATE, self.async_write_ha_state)
        )


class RoomEntity(HauswerkEntity):
    def __init__(self, controller: Heizen, room_id: str) -> None:
        super().__init__(controller)
        self.room_id = room_id

    @property
    def room(self) -> dict:
        return self.controller.rooms.get(self.room_id, {})

    @property
    def result(self) -> dict:
        return (self.controller.runtime.get(self.room_id) or {}).get("result") or {}

    @property
    def available(self) -> bool:
        return self.room_id in self.controller.rooms


def setup_room_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    factory: Callable[[Heizen, str], list[RoomEntity]],
) -> None:
    """Legt für jeden Raum Entitäten an und entfernt sie, wenn der Raum gelöscht wird."""
    controller: Heizen = hass.data[DOMAIN][MODULE_HEATING]
    known: dict[str, list[RoomEntity]] = {}

    @callback
    def sync() -> None:
        new: list[RoomEntity] = []
        for room_id in controller.rooms:
            if room_id not in known:
                known[room_id] = factory(controller, room_id)
                new.extend(known[room_id])
        registry = er.async_get(hass)
        for room_id in [r for r in known if r not in controller.rooms]:
            for entity in known.pop(room_id):
                if entity.entity_id and registry.async_get(entity.entity_id):
                    registry.async_remove(entity.entity_id)
                elif entity.hass is not None:
                    hass.async_create_task(entity.async_remove())
        if new:
            async_add_entities(new)

    sync()
    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_ROOMS, sync))
