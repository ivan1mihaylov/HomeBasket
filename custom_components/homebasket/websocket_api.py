"""WebSocket commands used by the HomeBasket dashboard card."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api as ws
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, SOURCE_MANUAL
from .images import InvalidImage
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
    mappings = [
        {**item, "has_photo": manager.images.has(item["code"])}
        for item in manager.store.as_list()
    ]
    return {
        "mappings": mappings,
        "pending": manager.store.pending_as_list(),
        "last_scan": manager.last_scan,
        "todo_entity": manager.todo_entity,
        "language": manager.language,
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
        websocket_get_photo,
        websocket_set_photo,
        websocket_delete_photo,
        websocket_details,
        websocket_dismiss_pending,
        websocket_link_code,
        websocket_unlink_code,
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
        vol.Optional("category"): vol.Any(str, None),
        vol.Optional("image"): vol.Any(str, None),
        vol.Optional("add_to_list", default=False): bool,
    }
)
@ws.async_response
async def websocket_save_mapping(
    hass: HomeAssistant, connection: ws.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Create or update a mapping, optionally adding it to the list."""
    manager = _manager(hass)
    # Only the fields the card actually sent are touched, so an omitted key
    # keeps its stored value while an explicit null clears it.
    optional = {key: msg[key] for key in ("category", "image") if key in msg}
    entry = await manager.store.async_save_mapping(
        msg["code"],
        msg["name"],
        brand=msg.get("brand"),
        source=SOURCE_MANUAL,
        **optional,
    )
    result: dict[str, Any] = {
        "mapping": entry,
        "added": False,
        "already_on_list": False,
        "increased": False,
    }
    if msg["add_to_list"]:
        result.update(await manager.async_add_to_list(entry["name"], code=entry["code"]))
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
    removed = await manager.async_forget(msg["code"])
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
    details = await manager.async_fetch_details(msg["code"])
    connection.send_result(
        msg["id"],
        {"found": False}
        if details is None
        else {
            "found": True,
            "name": details["label"],
            "brand": details["brand"],
            "category": details["category"],
            "image": details["image"],
        },
    )


@ws.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/list/add",
        vol.Required("name"): str,
        vol.Optional("code"): str,
    }
)
@ws.async_response
async def websocket_add_to_list(
    hass: HomeAssistant, connection: ws.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Put an arbitrary name on the shopping list."""
    manager = _manager(hass)
    outcome = await manager.async_add_to_list(msg["name"], code=msg.get("code"))
    connection.send_result(msg["id"], outcome)


@ws.websocket_command({vol.Required("type"): f"{DOMAIN}/list/items"})
@ws.async_response
async def websocket_list_items(
    hass: HomeAssistant, connection: ws.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the open items on the shopping list."""
    connection.send_result(
        msg["id"], {"items": await _manager(hass).async_list_items()}
    )


@ws.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/photo/get", vol.Required("code"): str}
)
@ws.async_response
async def websocket_get_photo(
    hass: HomeAssistant, connection: ws.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return a locally stored product photo as a data URL."""
    photo = await _manager(hass).images.async_get(msg["code"])
    connection.send_result(msg["id"], {"photo": photo})


@ws.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/photo/set",
        vol.Required("code"): str,
        vol.Required("photo"): str,
    }
)
@ws.async_response
async def websocket_set_photo(
    hass: HomeAssistant, connection: ws.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Store a photo the user took or uploaded for a product."""
    manager = _manager(hass)
    try:
        await manager.images.async_set(msg["code"], msg["photo"])
    except InvalidImage as err:
        connection.send_error(msg["id"], "invalid_image", str(err))
        return
    manager.async_notify_updated()
    connection.send_result(msg["id"], {"saved": True})


@ws.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/photo/delete", vol.Required("code"): str}
)
@ws.async_response
async def websocket_delete_photo(
    hass: HomeAssistant, connection: ws.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Remove a stored product photo."""
    manager = _manager(hass)
    removed = await manager.images.async_delete(msg["code"])
    manager.async_notify_updated()
    connection.send_result(msg["id"], {"removed": removed})


@ws.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/details",
        vol.Required("code"): str,
        vol.Optional("refresh", default=False): bool,
    }
)
@ws.async_response
async def websocket_details(
    hass: HomeAssistant, connection: ws.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the full Open Food Facts record for a product.

    The cached copy is used unless `refresh` asks for a fresh fetch, so
    opening a product does not hit Open Food Facts every time.
    """
    manager = _manager(hass)
    code = msg["code"]

    if not msg["refresh"]:
        if (cached := await manager.details.async_get(code)) is not None:
            connection.send_result(msg["id"], {"details": cached, "cached": True})
            return
        if not manager.use_openfoodfacts:
            connection.send_result(msg["id"], {"details": None, "cached": False})
            return

    details = await manager.async_fetch_details(code)
    connection.send_result(msg["id"], {"details": details, "cached": False})


@ws.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/pending/dismiss", vol.Required("code"): str}
)
@ws.async_response
async def websocket_dismiss_pending(
    hass: HomeAssistant, connection: ws.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Forget that a code was scanned, without touching any product."""
    manager = _manager(hass)
    removed = await manager.store.async_remove_pending(msg["code"])
    manager.async_notify_updated()
    connection.send_result(msg["id"], {"removed": removed})


@ws.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/alias/add",
        vol.Required("code"): str,
        vol.Required("product"): str,
    }
)
@ws.async_response
async def websocket_link_code(
    hass: HomeAssistant, connection: ws.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Attach a second barcode to an existing product."""
    manager = _manager(hass)
    target = await manager.async_link_code(msg["code"], msg["product"])
    if target is None:
        connection.send_error(msg["id"], "not_found", "No such product")
        return
    manager.async_notify_updated()
    connection.send_result(msg["id"], {"product": target})


@ws.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/alias/remove", vol.Required("code"): str}
)
@ws.async_response
async def websocket_unlink_code(
    hass: HomeAssistant, connection: ws.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Detach a barcode from its product, leaving the product in place."""
    manager = _manager(hass)
    removed = await manager.store.async_remove_alias(msg["code"])
    manager.async_notify_updated()
    connection.send_result(msg["id"], {"removed": removed})
