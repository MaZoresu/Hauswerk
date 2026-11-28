"""Kalender „Hauswerk Wartung“: wann welche Wartung fällig ist und Termine beim Fachbetrieb."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MODULE_SERVICES


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([WartungCalendar(hass.data[DOMAIN][MODULE_SERVICES])])


def _event(e: dict) -> CalendarEvent:
    if e.get("timed"):
        start = dt_util.as_local(datetime.fromisoformat(e["start"]).replace(tzinfo=dt_util.get_default_time_zone()))
        return CalendarEvent(start=start, end=start + timedelta(hours=1), summary=e["summary"], description=e.get("description") or None,
                             uid=e.get("uid"))
    d = date.fromisoformat(e["start"][:10])
    return CalendarEvent(start=d, end=d + timedelta(days=1), summary=e["summary"], description=e.get("description") or None, uid=e.get("uid"))


class WartungCalendar(CalendarEntity):
    _attr_should_poll = False
    _attr_has_entity_name = False
    _attr_name = "Hauswerk Wartung"
    _attr_unique_id = "hauswerk_wartung_kalender"
    _attr_icon = "mdi:calendar-wrench"

    def __init__(self, dienste) -> None:
        self.dienste = dienste

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.dienste.subscribe(self.async_write_ha_state))

    @property
    def event(self) -> CalendarEvent | None:
        today = dt_util.now().date()
        evs = sorted(self.dienste.calendar_events(today, today + timedelta(days=400)), key=lambda e: e["start"])
        return _event(evs[0]) if evs else None

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        evs = self.dienste.calendar_events(dt_util.as_local(start_date).date(), dt_util.as_local(end_date).date())
        return [_event(e) for e in evs]
