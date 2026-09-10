"""Core scan pipeline: barcode → product name → shopping list."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from . import openfoodfacts
from .const import (
    CONF_ADD_UNKNOWN,
    CONF_EVENT_NAMES,
    CONF_LANGUAGE,
    CONF_TODO_ENTITY,
    CONF_USE_OPENFOODFACTS,
    DEFAULT_ADD_UNKNOWN,
    DEFAULT_EVENT_NAMES,
    DEFAULT_LANGUAGE,
    DEFAULT_USE_OPENFOODFACTS,
    EVENT_CODE_KEYS,
    EVENT_SCANNED,
    EVENT_UPDATED,
    SIGNAL_UPDATED,
    SOURCE_OPENFOODFACTS,
    STATUS_KNOWN,
    STATUS_LOOKED_UP,
    STATUS_UNKNOWN,
)
from .store import MappingStore, normalize_code

_LOGGER = logging.getLogger(__name__)


class HomeBasketManager:
    """Owns the mapping store and turns scanned codes into shopping list items."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, store: MappingStore
    ) -> None:
        """Initialise the manager."""
        self.hass = hass
        self.entry = entry
        self.store = store
        self.last_scan: dict[str, Any] | None = None
        self._unsubscribes: list[Any] = []

    # ------------------------------------------------------------------
    # Options
    # ------------------------------------------------------------------
    def _option(self, key: str, default: Any) -> Any:
        return self.entry.options.get(key, self.entry.data.get(key, default))

    @property
    def todo_entity(self) -> str | None:
        """Return the to-do list scanned products are added to."""
        return self._option(CONF_TODO_ENTITY, None)

    @property
    def use_openfoodfacts(self) -> bool:
        """Return whether unknown codes are looked up online."""
        return self._option(CONF_USE_OPENFOODFACTS, DEFAULT_USE_OPENFOODFACTS)

    @property
    def add_unknown(self) -> bool:
        """Return whether unidentified codes are added to the list as-is."""
        return self._option(CONF_ADD_UNKNOWN, DEFAULT_ADD_UNKNOWN)

    @property
    def language(self) -> str:
        """Return the preferred product name language."""
        return self._option(CONF_LANGUAGE, DEFAULT_LANGUAGE)

    @property
    def event_names(self) -> list[str]:
        """Return the bus events an external scanner may fire."""
        names = self._option(CONF_EVENT_NAMES, DEFAULT_EVENT_NAMES)
        if isinstance(names, str):
            names = [part.strip() for part in names.split(",")]
        return [name for name in names if name]

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Start listening for scan events from external scanners."""
        for event_name in self.event_names:
            self._unsubscribes.append(
                self.hass.bus.async_listen(event_name, self._async_handle_event)
            )
            _LOGGER.debug("HomeBasket listening for '%s' events", event_name)

    async def async_unload(self) -> None:
        """Stop listening."""
        while self._unsubscribes:
            self._unsubscribes.pop()()

    async def _async_handle_event(self, event: Event) -> None:
        """Handle a scan event fired by an external barcode scanner."""
        data = event.data or {}
        code = next(
            (
                normalize_code(data[key])
                for key in EVENT_CODE_KEYS
                if data.get(key) not in (None, "")
            ),
            "",
        )
        if not code:
            _LOGGER.debug("Ignoring '%s' event without a code: %s", event.event_type, data)
            return
        await self.async_handle_code(code, source=event.event_type)

    # ------------------------------------------------------------------
    # Scan pipeline
    # ------------------------------------------------------------------
    async def async_handle_code(
        self,
        code: str,
        *,
        add_to_list: bool = True,
        source: str = "manual",
    ) -> dict[str, Any]:
        """Resolve a code to a product and optionally put it on the list.

        Known code            → name from the local dictionary
        Unknown code          → Open Food Facts, remembered for next time
        Still unknown         → kept as pending so the card can ask for a name
        """
        code = normalize_code(code)
        result: dict[str, Any] = {
            "code": code,
            "name": None,
            "brand": None,
            "image": None,
            "status": STATUS_UNKNOWN,
            "added": False,
            "already_on_list": False,
            "source": source,
            "timestamp": dt_util.utcnow().isoformat(),
        }

        if not code:
            return result

        if (mapping := self.store.get(code)) is not None:
            result.update(
                name=mapping.get("name"),
                brand=mapping.get("brand"),
                image=mapping.get("image"),
                status=STATUS_KNOWN,
            )
            await self.store.async_record_scan(code)
        elif self.use_openfoodfacts:
            if (product := await openfoodfacts.async_lookup(
                self.hass, code, self.language
            )) is not None:
                await self.store.async_save_mapping(
                    code,
                    product["name"],
                    brand=product.get("brand"),
                    image=product.get("image"),
                    source=SOURCE_OPENFOODFACTS,
                )
                await self.store.async_record_scan(code)
                result.update(
                    name=product["name"],
                    brand=product.get("brand"),
                    image=product.get("image"),
                    status=STATUS_LOOKED_UP,
                )

        if result["status"] == STATUS_UNKNOWN:
            await self.store.async_add_pending(code)
            if self.add_unknown:
                result["name"] = code

        if add_to_list and result["name"]:
            added, already = await self.async_add_to_list(result["name"])
            result["added"] = added
            result["already_on_list"] = already

        self.last_scan = result
        self.hass.bus.async_fire(EVENT_SCANNED, result)
        self.async_notify_updated()
        return result

    async def async_add_to_list(self, name: str) -> tuple[bool, bool]:
        """Add an item to the configured to-do list.

        Returns (added, already_on_list).
        """
        entity_id = self.todo_entity
        if not entity_id:
            _LOGGER.warning("No to-do list configured, '%s' was not added", name)
            return False, False

        if name.casefold() in {item.casefold() for item in await self.async_list_items()}:
            return False, True

        try:
            await self.hass.services.async_call(
                "todo",
                "add_item",
                {"item": name},
                target={"entity_id": entity_id},
                blocking=True,
            )
        except Exception:  # noqa: BLE001 - surfaced to the user, never fatal
            _LOGGER.exception("Failed to add '%s' to %s", name, entity_id)
            return False, False
        return True, False

    async def async_list_items(self) -> list[str]:
        """Return the open items on the configured to-do list."""
        entity_id = self.todo_entity
        if not entity_id:
            return []

        try:
            response = await self.hass.services.async_call(
                "todo",
                "get_items",
                {"status": ["needs_action"]},
                target={"entity_id": entity_id},
                blocking=True,
                return_response=True,
            )
        except Exception:  # noqa: BLE001 - an empty list is a safe fallback
            _LOGGER.exception("Failed to read the items of %s", entity_id)
            return []

        items = (response or {}).get(entity_id, {}).get("items", [])
        return [item["summary"] for item in items if item.get("summary")]

    @callback
    def async_notify_updated(self) -> None:
        """Tell entities and the dashboard card that something changed."""
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)
        self.hass.bus.async_fire(EVENT_UPDATED, {})
