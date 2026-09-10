"""Constants for the HomeBasket integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "homebasket"

# Where the public API object is published for other integrations.
DATA_API: Final = "homebasket_api"
VERSION: Final = "0.1.0"

# Config / options keys
CONF_TODO_ENTITY: Final = "todo_entity"
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
SOURCE_IMPORT: Final = "import"

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
