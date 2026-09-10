"""WebSocket commands used by the HomeBasket dashboard card."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api as ws
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from . import openfoodfacts
from .const import DOMAIN, SOURCE_MANUAL
from .manager import HomeBasketManager

_REGISTERED = f"{DOMAIN}_ws_registered"


def _manager(hass: HomeAssistant) -> HomeBasketManager:
    """Return the active manager or raise."""
    managers = list(hass.data.get(DOMAIN, {}).values())
    if not managers:
        raise HomeAssistantError("HomeBasket is not set up")
    return managers[0]


def _state(manager: HomeBasketManager) -> dict[str, Any]:
    """Return the payload the card renders itself from."""
    return {
        "mappings": manager.store.as_list(),
        "pending": manager.store.pending_as_list(),
        "last_scan": manager.last_scan,
        "todo_entity": manager.todo_entity,
    }


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the WebSocket commands once."""
    if hass.data.get(_REGISTERED):
        return
    hass.data[_REGISTERED] = True

    for handler in (
        websocket_get_state,
        websocket_save_mapping,
        websocket_delete_mapping,
        websocket_scan,
        websocket_lookup,
        websocket_add_to_list,
        websocket_list_items,
    ):
        ws.async_register_command(hass, handler)


@ws.websocket_command({vol.Required("type"): f"{DOMAIN}/state"})
@ws.async_response
async def websocket_get_state(
    hass: HomeAssistant, connection: ws.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return every mapping plus the current scan state."""
    connection.send_result(msg["id"], _state(_manager(hass)))


@ws.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/mapping/save",
        vol.Required("code"): str,
        vol.Required("name"): str,
        vol.Optional("brand"): vol.Any(str, None),
        vol.Optional("add_to_list", default=False): bool,
    }
)
@ws.async_response
async def websocket_save_mapping(
    hass: HomeAssistant, connection: ws.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Create or update a mapping, optionally adding it to the list."""
    manager = _manager(hass)
    entry = await manager.store.async_save_mapping(
        msg["code"], msg["name"], brand=msg.get("brand"), source=SOURCE_MANUAL
    )
    result: dict[str, Any] = {"mapping": entry, "added": False, "already_on_list": False}
    if msg["add_to_list"]:
        added, already = await manager.async_add_to_list(entry["name"])
        result.update(added=added, already_on_list=already)
    manager.async_notify_updated()
    connection.send_result(msg["id"], result)


@ws.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/mapping/delete", vol.Required("code"): str}
)
@ws.async_response
async def websocket_delete_mapping(
    hass: HomeAssistant, connection: ws.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete a mapping."""
    manager = _manager(hass)
    removed = await manager.store.async_remove_mapping(msg["code"])
    manager.async_notify_updated()
    connection.send_result(msg["id"], {"removed": removed})


@ws.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/scan",
        vol.Required("code"): str,
        vol.Optional("add_to_list", default=True): bool,
    }
)
@ws.async_response
async def websocket_scan(
    hass: HomeAssistant, connection: ws.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Run a scanned code through the full pipeline."""
    manager = _manager(hass)
    result = await manager.async_handle_code(
        msg["code"], add_to_list=msg["add_to_list"], source="card"
    )
    connection.send_result(msg["id"], result)


@ws.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/lookup", vol.Required("code"): str}
)
@ws.async_response
async def websocket_lookup(
    hass: HomeAssistant, connection: ws.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Look a code up online without touching the list or the dictionary."""
    manager = _manager(hass)
    product = await openfoodfacts.async_lookup(hass, msg["code"], manager.language)
    connection.send_result(
        msg["id"], {"found": product is not None, **(product or {})}
    )


@ws.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/list/add", vol.Required("name"): str}
)
@ws.async_response
async def websocket_add_to_list(
    hass: HomeAssistant, connection: ws.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Put an arbitrary name on the shopping list."""
    manager = _manager(hass)
    added, already = await manager.async_add_to_list(msg["name"])
    connection.send_result(msg["id"], {"added": added, "already_on_list": already})


@ws.websocket_command({vol.Required("type"): f"{DOMAIN}/list/items"})
@ws.async_response
async def websocket_list_items(
    hass: HomeAssistant, connection: ws.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the open items on the shopping list."""
    connection.send_result(
        msg["id"], {"items": await _manager(hass).async_list_items()}
    )
