"""The HomeBasket integration."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from . import websocket_api
from .api import HomeBasketAPI
from .const import (
    ATTR_ADD_TO_LIST,
    ATTR_BRAND,
    ATTR_CATEGORY,
    ATTR_CODE,
    ATTR_INCLUDE_DETAILS,
    ATTR_INCLUDE_PHOTO,
    ATTR_NAME,
    ATTR_OVERWRITE,
    ATTR_PATH,
    ATTR_QUERY,
    ATTR_REFRESH,
    DATA_API,
    DOMAIN,
    SERVICE_ADD_MAPPING,
    SERVICE_GET_PRODUCT,
    SERVICE_GET_PRODUCTS,
    SERVICE_IMPORT_MAPPINGS,
    SERVICE_LOOKUP,
    SERVICE_REMOVE_MAPPING,
    SERVICE_SCAN,
    SOURCE_MANUAL,
)
from .details import DetailStore
from .http_api import async_register_http_api
from .frontend import async_register_frontend
from .images import ImageStore
from .manager import HomeBasketManager
from .store import MappingStore

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# The card and the old BeepBasket service calls spell the same two fields
# differently, so both names are accepted and resolved in the handlers.
CODE_KEYS = (ATTR_CODE, "barcode")
NAME_KEYS = (ATTR_NAME, "product", "product_name")

CODE_SCHEMA = vol.Schema(
    {vol.Optional(key): cv.string for key in CODE_KEYS}, extra=vol.ALLOW_EXTRA
)

ADD_MAPPING_SCHEMA = CODE_SCHEMA.extend(
    {
        **{vol.Optional(key): cv.string for key in NAME_KEYS},
        vol.Optional(ATTR_BRAND): cv.string,
        vol.Optional(ATTR_CATEGORY): cv.string,
    }
)

REMOVE_MAPPING_SCHEMA = CODE_SCHEMA

SCAN_SCHEMA = CODE_SCHEMA.extend(
    {vol.Optional(ATTR_ADD_TO_LIST, default=True): cv.boolean}
)

LOOKUP_SCHEMA = CODE_SCHEMA

GET_PRODUCT_SCHEMA = CODE_SCHEMA.extend(
    {
        vol.Optional(ATTR_INCLUDE_DETAILS, default=True): cv.boolean,
        vol.Optional(ATTR_INCLUDE_PHOTO, default=False): cv.boolean,
        vol.Optional(ATTR_REFRESH, default=False): cv.boolean,
    }
)

GET_PRODUCTS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_QUERY): cv.string,
        vol.Optional(ATTR_CATEGORY): cv.string,
        vol.Optional(ATTR_INCLUDE_DETAILS, default=False): cv.boolean,
    }
)

IMPORT_MAPPINGS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PATH): cv.string,
        vol.Optional(ATTR_OVERWRITE, default=False): cv.boolean,
    }
)


def _code_of(call: ServiceCall) -> str:
    """Return the code from a service call, whichever field name was used."""
    for key in CODE_KEYS:
        if value := call.data.get(key):
            return str(value).strip()
    return ""


def _name_of(call: ServiceCall) -> str:
    """Return the product name from a service call, whichever field was used."""
    for key in NAME_KEYS:
        if value := call.data.get(key):
            return str(value).strip()
    return ""


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HomeBasket from a config entry."""
    store = MappingStore(hass)
    await store.async_load()

    images = ImageStore(hass)
    await images.async_load()

    manager = HomeBasketManager(hass, entry, store, images, DetailStore(hass))
    await manager.async_setup()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager
    # Published for other integrations; see api.py.
    hass.data[DATA_API] = HomeBasketAPI(manager)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass)
    websocket_api.async_register(hass)
    async_register_http_api(hass)
    await async_register_frontend(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        manager: HomeBasketManager = hass.data[DOMAIN].pop(entry.entry_id)
        await manager.async_unload()
        hass.data.pop(DATA_API, None)
        if not hass.data[DOMAIN]:
            for service in (
                SERVICE_ADD_MAPPING,
                SERVICE_REMOVE_MAPPING,
                SERVICE_SCAN,
                SERVICE_LOOKUP,
                SERVICE_IMPORT_MAPPINGS,
                SERVICE_GET_PRODUCT,
                SERVICE_GET_PRODUCTS,
            ):
                hass.services.async_remove(DOMAIN, service)
    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _get_manager(hass: HomeAssistant) -> HomeBasketManager:
    """Return the single active manager instance."""
    managers = list(hass.data.get(DOMAIN, {}).values())
    if not managers:
        raise HomeAssistantError("HomeBasket is not set up")
    return managers[0]


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the HomeBasket services once."""
    if hass.services.has_service(DOMAIN, SERVICE_ADD_MAPPING):
        return

    async def async_add_mapping(call: ServiceCall) -> ServiceResponse:
        manager = _get_manager(hass)
        code, name = _code_of(call), _name_of(call)
        if not code or not name:
            raise HomeAssistantError("Both a code and a product name are required")
        entry = await manager.store.async_save_mapping(
            code,
            name,
            brand=call.data.get(ATTR_BRAND),
            category=call.data.get(ATTR_CATEGORY),
            source=SOURCE_MANUAL,
        )
        manager.async_notify_updated()
        return dict(entry)

    async def async_remove_mapping(call: ServiceCall) -> ServiceResponse:
        manager = _get_manager(hass)
        removed = await manager.async_forget(_code_of(call))
        manager.async_notify_updated()
        return {"removed": removed}

    async def async_scan(call: ServiceCall) -> ServiceResponse:
        manager = _get_manager(hass)
        return await manager.async_handle_code(
            _code_of(call),
            add_to_list=call.data.get(ATTR_ADD_TO_LIST, True),
            source="service",
        )

    async def async_lookup(call: ServiceCall) -> ServiceResponse:
        manager = _get_manager(hass)
        details = await manager.async_fetch_details(_code_of(call))
        if details is None:
            return {"found": False}
        return {
            "found": True,
            "name": details["label"],
            "brand": details["brand"],
            "category": details["category"],
            "image": details["image"],
        }

    async def async_import_mappings(call: ServiceCall) -> ServiceResponse:
        manager = _get_manager(hass)
        path = Path(call.data[ATTR_PATH])
        config_dir = Path(hass.config.config_dir).resolve()
        try:
            inside_config = path.resolve().is_relative_to(config_dir)
        except OSError:
            inside_config = False
        if not inside_config and not hass.config.is_allowed_path(str(path)):
            raise HomeAssistantError(f"Reading {path} is not allowed")

        def _read() -> dict:
            return json.loads(path.read_text(encoding="utf-8"))

        try:
            raw = await hass.async_add_executor_job(_read)
        except (OSError, ValueError) as err:
            raise HomeAssistantError(f"Could not read {path}: {err}") from err

        if not isinstance(raw, dict):
            raise HomeAssistantError(f"{path} does not contain a barcode dictionary")

        # BeepBasket wraps its dictionary in a "mappings" key in some versions.
        mappings = raw.get("mappings") if isinstance(raw.get("mappings"), dict) else raw
        imported = await manager.store.async_import(
            mappings, overwrite=call.data.get(ATTR_OVERWRITE, False)
        )
        manager.async_notify_updated()
        _LOGGER.info("Imported %s mappings from %s", imported, path)
        return {"imported": imported}

    async def async_get_product(call: ServiceCall) -> ServiceResponse:
        api = hass.data[DATA_API]
        code = _code_of(call)
        product = api.get(code)
        if product is None:
            return {"found": False}

        if call.data[ATTR_INCLUDE_DETAILS]:
            product["details"] = await api.async_get_details(
                code, refresh=call.data[ATTR_REFRESH]
            )
        if call.data[ATTR_INCLUDE_PHOTO]:
            product["photo"] = await api.async_get_photo(code)
        return {"found": True, "product": product}

    async def async_get_products(call: ServiceCall) -> ServiceResponse:
        api = hass.data[DATA_API]

        products = (
            api.find(query) if (query := call.data.get(ATTR_QUERY)) else api.products
        )
        if category := call.data.get(ATTR_CATEGORY):
            wanted = category.casefold()
            products = [
                item
                for item in products
                if str(item.get("category") or "").casefold() == wanted
            ]

        if call.data[ATTR_INCLUDE_DETAILS]:
            for product in products:
                product["details"] = await api.async_get_details(product["code"])

        return {"count": len(products), "products": products}

    services = (
        (SERVICE_GET_PRODUCT, async_get_product, GET_PRODUCT_SCHEMA),
        (SERVICE_GET_PRODUCTS, async_get_products, GET_PRODUCTS_SCHEMA),
        (SERVICE_ADD_MAPPING, async_add_mapping, ADD_MAPPING_SCHEMA),
        (SERVICE_REMOVE_MAPPING, async_remove_mapping, REMOVE_MAPPING_SCHEMA),
        (SERVICE_SCAN, async_scan, SCAN_SCHEMA),
        (SERVICE_LOOKUP, async_lookup, LOOKUP_SCHEMA),
        (SERVICE_IMPORT_MAPPINGS, async_import_mappings, IMPORT_MAPPINGS_SCHEMA),
    )
    for name, handler, schema in services:
        hass.services.async_register(
            DOMAIN,
            name,
            handler,
            schema=schema,
            supports_response=SupportsResponse.OPTIONAL,
        )
