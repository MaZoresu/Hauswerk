"""Aufgabenliste „Hauswerk Wartung“: die fälligen Wartungsaufgaben als To-do-Liste in Home Assistant (auch für Assist)."""
from __future__ import annotations

from datetime import date

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity, TodoListEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODULE_SERVICES

HORIZON = 30  # Aufgaben, die in so vielen Tagen fällig sind, stehen in der Liste


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([WartungTodo(hass.data[DOMAIN][MODULE_SERVICES])])


class WartungTodo(TodoListEntity):
    """Fällige und bald fällige Aufgaben; abhaken = erledigt bzw. quittiert, neu = einmalige Aufgabe."""

    _attr_should_poll = False
    _attr_has_entity_name = False
    _attr_name = "Hauswerk Wartung"
    _attr_unique_id = "hauswerk_wartung_todo"
    _attr_icon = "mdi:wrench-clock"
    _attr_supported_features = (TodoListEntityFeature.CREATE_TODO_ITEM | TodoListEntityFeature.UPDATE_TODO_ITEM
                                | TodoListEntityFeature.DELETE_TODO_ITEM | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
                                | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM)

    def __init__(self, dienste) -> None:
        self.dienste = dienste

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.dienste.subscribe(self.async_write_ha_state))

    @property
    def todo_items(self) -> list[TodoItem]:
        out = []
        for t in self.dienste.tasks():
            left = t.get("left")
            if left is None or left > HORIZON:
                continue
            desc = " · ".join(x for x in (t.get("room"), t.get("person_name"), t.get("note")) if x) or None
            out.append(TodoItem(summary=t["name"], uid=t["id"], status=TodoItemStatus.NEEDS_ACTION,
                                due=date.fromisoformat(t["due"]) if t.get("due") else None, description=desc))
        return out

    async def async_create_todo_item(self, item: TodoItem) -> None:
        due = item.due.isoformat()[:10] if item.due else None
        await self.dienste.async_add_task(item.summary or "Aufgabe", by="Aufgabenliste", due=due, note=item.description)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        if item.status == TodoItemStatus.COMPLETED and item.uid:
            await self.dienste.async_task_done(item.uid, by="Aufgabenliste")
        self.async_write_ha_state()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        for uid in uids:
            if uid.startswith("auto:"):
                await self.dienste.async_task_done(uid, by="Aufgabenliste")
            else:
                await self.dienste.async_delete_task(uid, by="Aufgabenliste")
