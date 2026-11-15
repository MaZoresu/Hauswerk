"""Schalter: Urlaub (global) und Automatik je Raum."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODULE_HEATING
from .entity import HauswerkEntity, RoomEntity, setup_room_entities


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    ctl = hass.data[DOMAIN][MODULE_HEATING]
    async_add_entities(
        [
            SettingSwitch(ctl, "vacation", "hauswerk_vacation", "Hauswerk Urlaub", "mdi:palm-tree"),
            SettingSwitch(ctl, "guest", "hauswerk_guest", "Hauswerk Gäste", "mdi:account-group-outline"),
            SettingSwitch(ctl, "party", "hauswerk_party", "Hauswerk Party", "mdi:party-popper"),
            SettingSwitch(ctl, "liming", "hauswerk_liming", "Hauswerk Entkalken", "mdi:water-sync"),
            SettingSwitch(ctl, "eco_force", "hauswerk_eco_force", "Hauswerk Eco erzwingen", "mdi:leaf"),
        ]
    )
    setup_room_entities(
        hass, entry, async_add_entities, lambda ctl, room_id: [RoomAutoSwitch(ctl, room_id)]
    )


class SettingSwitch(HauswerkEntity, SwitchEntity):
    """Schaltet eine globale Einstellung (Urlaub, Gäste, Party, Entkalken)."""

    def __init__(self, controller, key: str, unique_id: str, name: str, icon: str) -> None:
        super().__init__(controller)
        self._key = key
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_icon = icon

    @property
    def is_on(self) -> bool:
        return bool(self.controller.settings.get(self._key))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.controller.async_save_settings({self._key: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.controller.async_save_settings({self._key: False})


class RoomAutoSwitch(RoomEntity, SwitchEntity):
    _attr_icon = "mdi:radiator"

    @property
    def unique_id(self) -> str:
        return f"hauswerk_{self.room_id}_auto"

    @property
    def name(self) -> str:
        return f"Hauswerk {self.room.get('name', self.room_id)} Automatik"

    @property
    def is_on(self) -> bool:
        return bool(self.room.get("enabled", True))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.controller.async_set_room_enabled(self.room_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.controller.async_set_room_enabled(self.room_id, False)
