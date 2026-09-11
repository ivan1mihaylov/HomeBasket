"""Constants for the HomeBasket integration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

DOMAIN: Final = "homebasket"

# The integration HomeBasket Lists publishes its API under. Optional: without
# it, scans go on the configured to-do entity as they always have.
LISTS_API: Final = "homebasket_lists_api"

# What a barcode turned out to be: a grocery, from Open Food Facts, or a thing,
# from Open Products Facts. A product named by hand has neither until it is
# looked up.
KIND_FOOD: Final = "food"
KIND_BEAUTY: Final = "beauty"
KIND_PETFOOD: Final = "petfood"
KIND_PRODUCT: Final = "product"
KINDS: Final = [KIND_FOOD, KIND_BEAUTY, KIND_PETFOOD, KIND_PRODUCT]

# Which kind of shop a product is bought in. A kind says which database knew
# the barcode; this says where you go for it, which is not the same thing - a
# tomato and a shampoo are both "products" to a database, and two different
# shops to a person.
DEPARTMENT_GROCERIES: Final = "groceries"
DEPARTMENT_BAKERY: Final = "bakery"
DEPARTMENT_PRODUCE: Final = "produce"
DEPARTMENT_BUTCHER: Final = "butcher"
DEPARTMENT_COSMETICS: Final = "cosmetics"
DEPARTMENT_MEDICINES: Final = "medicines"
DEPARTMENT_PETS: Final = "pets"
DEPARTMENT_BUILDING: Final = "building"
DEPARTMENTS: Final = [
    DEPARTMENT_GROCERIES,
    DEPARTMENT_BAKERY,
    DEPARTMENT_PRODUCE,
    DEPARTMENT_BUTCHER,
    DEPARTMENT_COSMETICS,
    DEPARTMENT_MEDICINES,
    DEPARTMENT_PETS,
    DEPARTMENT_BUILDING,
]

# What the database that knew a barcode says about where to buy it. Groceries
# and things alike start as groceries - a supermarket sells both - while the
# two databases that are about one thing say exactly which shop that is. Any
# of it can be changed afterwards; this is only where a product starts.
KIND_DEPARTMENTS: Final = {
    KIND_FOOD: DEPARTMENT_GROCERIES,
    KIND_PRODUCT: DEPARTMENT_GROCERIES,
    KIND_PETFOOD: DEPARTMENT_PETS,
    KIND_BEAUTY: DEPARTMENT_COSMETICS,
}

# Where the public API object is published for other integrations.
DATA_API: Final = "homebasket_api"

# Config / options keys
CONF_TODO_ENTITY: Final = "todo_entity"
# Which HomeBasket Lists list a scan goes on, when that integration is there.
CONF_LIST_ENTRY: Final = "lists_entry"
CONF_USE_OPENFOODFACTS: Final = "use_openfoodfacts"
CONF_ADD_UNKNOWN: Final = "add_unknown"
CONF_LANGUAGE: Final = "language"
CONF_EVENT_NAMES: Final = "event_names"

DEFAULT_USE_OPENFOODFACTS: Final = True
DEFAULT_ADD_UNKNOWN: Final = False
DEFAULT_LANGUAGE: Final = "en"
DEFAULT_EVENT_NAMES: Final = ["barcode_scanned"]

# Keys accepted inside an incoming scan event payload
EVENT_CODE_KEYS: Final = ("barcode", "code", "tag_id", "text", "value")

# Events fired on the Home Assistant bus
EVENT_SCANNED: Final = "homebasket_scanned"
EVENT_UPDATED: Final = "homebasket_updated"

# Dispatcher signal used to refresh entities
SIGNAL_UPDATED: Final = "homebasket_updated_signal"

# Storage
STORAGE_KEY: Final = "homebasket.mappings"
STORAGE_VERSION: Final = 1

# Scan result statuses
STATUS_KNOWN: Final = "known"
STATUS_LOOKED_UP: Final = "looked_up"
STATUS_UNKNOWN: Final = "unknown"

# Where a mapping came from
SOURCE_MANUAL: Final = "manual"
SOURCE_OPENFOODFACTS: Final = "openfoodfacts"
SOURCE_OPENBEAUTYFACTS: Final = "openbeautyfacts"
SOURCE_OPENPETFOODFACTS: Final = "openpetfoodfacts"
SOURCE_OPENPRODUCTSFACTS: Final = "openproductsfacts"

# Which database a kind came from, for the source stamped on a product.
KIND_SOURCES: Final = {
    KIND_FOOD: SOURCE_OPENFOODFACTS,
    KIND_BEAUTY: SOURCE_OPENBEAUTYFACTS,
    KIND_PETFOOD: SOURCE_OPENPETFOODFACTS,
    KIND_PRODUCT: SOURCE_OPENPRODUCTSFACTS,
}
SOURCE_IMPORT: Final = "import"
# Something a shopping list configured and handed over, rather than a scan.
SOURCE_LIST: Final = "list"

# Services
SERVICE_ADD_MAPPING: Final = "add_mapping"
SERVICE_REMOVE_MAPPING: Final = "remove_mapping"
SERVICE_SCAN: Final = "scan"
SERVICE_LOOKUP: Final = "lookup"
SERVICE_IMPORT_MAPPINGS: Final = "import_mappings"
SERVICE_GET_PRODUCT: Final = "get_product"
SERVICE_GET_PRODUCTS: Final = "get_products"

ATTR_CODE: Final = "code"
ATTR_NAME: Final = "name"
ATTR_BRAND: Final = "brand"
ATTR_CATEGORY: Final = "category"
ATTR_ADD_TO_LIST: Final = "add_to_list"
ATTR_PATH: Final = "path"
ATTR_OVERWRITE: Final = "overwrite"
ATTR_QUERY: Final = "query"
ATTR_INCLUDE_DETAILS: Final = "include_details"
ATTR_INCLUDE_PHOTO: Final = "include_photo"
ATTR_REFRESH: Final = "refresh"


def _installed_version() -> str:
    """Return the version this integration is installed as.

    It is read from the manifest rather than written down twice, so what the
    device shows and what the databases are told about the caller are the
    version that is actually running.
    """
    try:
        manifest = Path(__file__).parent / "manifest.json"
        return json.loads(manifest.read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):  # pragma: no cover - never shipped
        return "0.0.0"


VERSION: Final = _installed_version()
