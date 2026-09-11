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
    CONF_LIST_ENTRY,
    CONF_TODO_ENTITY,
    CONF_USE_OPENFOODFACTS,
    DEFAULT_ADD_UNKNOWN,
    DEFAULT_EVENT_NAMES,
    DEFAULT_LANGUAGE,
    DEFAULT_USE_OPENFOODFACTS,
    EVENT_CODE_KEYS,
    EVENT_SCANNED,
    EVENT_UPDATED,
    LISTS_API,
    SIGNAL_UPDATED,
    SOURCE_OPENFOODFACTS,
    STATUS_KNOWN,
    STATUS_LOOKED_UP,
    STATUS_UNKNOWN,
)
from .details import DetailStore
from .images import ImageStore
from .store import MappingStore, normalize_code

_LOGGER = logging.getLogger(__name__)


class HomeBasketManager:
    """Owns the mapping store and turns scanned codes into shopping list items."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        store: MappingStore,
        images: ImageStore,
        details: DetailStore,
    ) -> None:
        """Initialise the manager."""
        self.hass = hass
        self.entry = entry
        self.store = store
        self.images = images
        self.details = details
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
            "product_code": code,
            "name": None,
            "brand": None,
            "category": None,
            "image": None,
            "status": STATUS_UNKNOWN,
            "added": False,
            "already_on_list": False,
            "increased": False,
            "quantity": None,
            "list": None,
            "source": source,
            "timestamp": dt_util.utcnow().isoformat(),
        }

        if not code:
            return result

        if (resolved := self.store.resolve(code)) is not None:
            primary, mapping = resolved
            result.update(
                product_code=primary,
                name=mapping.get("name"),
                brand=mapping.get("brand"),
                category=mapping.get("category"),
                image=mapping.get("image"),
                status=STATUS_KNOWN,
            )
            await self.store.async_record_scan(code)
        elif self.use_openfoodfacts:
            if (product := await self.async_fetch_details(code)) is not None:
                await self.store.async_save_mapping(
                    code,
                    product["label"],
                    brand=product.get("brand"),
                    category=product.get("category"),
                    image=product.get("image"),
                    source=SOURCE_OPENFOODFACTS,
                )
                await self.store.async_record_scan(code)
                result.update(
                    name=product["label"],
                    brand=product.get("brand"),
                    category=product.get("category"),
                    image=product.get("image"),
                    status=STATUS_LOOKED_UP,
                )

        if result["status"] == STATUS_UNKNOWN:
            await self.store.async_add_pending(code)
            if self.add_unknown:
                result["name"] = code

        if add_to_list and result["name"]:
            result.update(
                await self.async_add_to_list(
                    result["name"], code=result["product_code"]
                )
            )

        self.last_scan = result
        self.hass.bus.async_fire(EVENT_SCANNED, result)
        self.async_notify_updated()
        return result

    @property
    def lists_api(self) -> Any | None:
        """Return HomeBasket Lists' API object, when that is installed."""
        return self.hass.data.get(LISTS_API)

    @property
    def list_entry(self) -> str | None:
        """Return which HomeBasket Lists list scans go on, when one was chosen."""
        return self._option(CONF_LIST_ENTRY, None) or None

    async def async_add_to_list(
        self, name: str, *, code: str | None = None
    ) -> dict[str, Any]:
        """Put a product on the shopping list.

        HomeBasket Lists gets it when that integration is installed and there
        is a list to put it on - and a second scan of the same thing there
        means two of it, not two lines saying it. Without HomeBasket Lists,
        the configured to-do entity gets a line, the way it always has.

        Returns what happened: `added` for a new line, `increased` when the
        count went up, `already_on_list` when it was there and nothing needed
        doing.
        """
        if (outcome := await self._async_add_to_lists(name, code)) is not None:
            return outcome
        return await self._async_add_to_todo(name)

    async def _async_add_to_lists(
        self, name: str, code: str | None
    ) -> dict[str, Any] | None:
        """Put a product on a HomeBasket Lists list, if there is one.

        Returns None when that integration is absent, too old to be written
        to, or has no list this could mean - so the caller falls back.
        """
        api = self.lists_api
        if api is None or not hasattr(api, "async_add_item"):
            return None

        try:
            result = await api.async_add_item(
                name, entry_id=self.list_entry, quantity=1, product_code=code
            )
        except Exception:  # noqa: BLE001 - fall back to the to-do list
            _LOGGER.exception("HomeBasket Lists would not take '%s'", name)
            return None

        if result is None:
            # No list of that id, or several lists and none chosen.
            return None

        # The list says what it did with it: a new line, one more of what was
        # already there, or nothing because it keeps what it has.
        outcome = result.get("outcome") or (
            "counted" if result.get("increased") else "added"
        )
        return {
            "added": outcome == "added",
            "increased": outcome == "counted",
            "already_on_list": outcome == "kept",
            "quantity": (result.get("item") or {}).get("quantity"),
            "list": result.get("list"),
        }

    async def _async_add_to_todo(self, name: str) -> dict[str, Any]:
        """Add a line to the configured to-do entity."""
        nothing = {
            "added": False,
            "increased": False,
            "already_on_list": False,
            "quantity": None,
            "list": None,
        }

        entity_id = self.todo_entity
        if not entity_id:
            _LOGGER.warning("No shopping list configured, '%s' was not added", name)
            return nothing

        if name.casefold() in {item.casefold() for item in await self.async_list_items()}:
            return {**nothing, "already_on_list": True, "list": entity_id}

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
            return nothing
        return {**nothing, "added": True, "list": entity_id}

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

    async def async_fetch_details(self, code: str) -> dict[str, Any] | None:
        """Ask Open Food Facts about a code and cache what comes back."""
        details = await openfoodfacts.async_fetch(self.hass, code, self.language)
        if details is not None:
            await self.details.async_set(code, details)
        return details

    async def async_forget(self, code: str) -> bool:
        """Remove a product, its other barcodes, its photo and its records."""
        removed = await self.store.async_remove_mapping(code)
        for entry_code in removed:
            await self.images.async_delete(entry_code)
            await self.details.async_delete(entry_code)
        return bool(removed)

    async def async_link_code(self, code: str, primary: str) -> str | None:
        """Attach a barcode to an existing product.

        A photo taken for the barcode is kept when the product has none, so
        linking never silently loses a picture.
        """
        code = normalize_code(code)
        target = await self.store.async_add_alias(code, primary)
        if target is None:
            return None

        if code != target and self.images.has(code):
            if not self.images.has(target) and (
                photo := await self.images.async_get(code)
            ):
                await self.images.async_set(target, photo)
            await self.images.async_delete(code)
        return target

    @callback
    def async_notify_updated(self) -> None:
        """Tell entities and the dashboard card that something changed."""
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)
        self.hass.bus.async_fire(EVENT_UPDATED, {})
