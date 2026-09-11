"""Thin async client for the Open Food Facts family of product APIs.

A barcode is looked for in Open Food Facts, then Open Beauty Facts, then Open
Pet Food Facts, and finally Open Products Facts - the same API and the same
shape in all four. Which one answered is what a product turns out to be.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import KIND_BEAUTY, KIND_FOOD, KIND_PETFOOD, KIND_PRODUCT, VERSION

_LOGGER = logging.getLogger(__name__)

# The four databases of the Open Food Facts family, in the order a barcode is
# looked for: the common case first, the catch-all last.
SITES = {
    KIND_FOOD: "world.openfoodfacts.org",
    KIND_BEAUTY: "world.openbeautyfacts.org",
    KIND_PETFOOD: "world.openpetfoodfacts.org",
    KIND_PRODUCT: "world.openproductsfacts.org",
}
API_URL = "https://{host}/api/v2/product/{code}.json"
PRODUCT_URL = "https://{host}/product/{code}"
TIMEOUT = aiohttp.ClientTimeout(total=10)
USER_AGENT = f"HomeBasket/{VERSION} (Home Assistant custom integration)"

# Fields with no language variant.
PLAIN_FIELDS = (
    "code",
    "brands",
    "quantity",
    "serving_size",
    "allergens_tags",
    "traces_tags",
    "categories_tags",
    "nutriscore_grade",
    "nova_group",
    "ecoscore_grade",
    "nutriments",
    "stores",
    "origins",
    "manufacturing_places",
    "image_front_url",
    "image_front_small_url",
    "image_ingredients_url",
    "image_nutrition_url",
)
# Fields Open Food Facts also publishes as `<field>_<language>`.
TRANSLATED_FIELDS = (
    "product_name",
    "generic_name",
    "categories",
    "labels",
    "ingredients_text",
    "packaging",
    "countries",
)

# The nutriments worth showing, in the order a label prints them.
NUTRIMENTS = (
    ("energy-kcal", "Energy", "kcal"),
    ("fat", "Fat", "g"),
    ("saturated-fat", "of which saturates", "g"),
    ("carbohydrates", "Carbohydrates", "g"),
    ("sugars", "of which sugars", "g"),
    ("fiber", "Fibre", "g"),
    ("proteins", "Protein", "g"),
    ("salt", "Salt", "g"),
)


def _language(language: str | None) -> str | None:
    """Return the bare two letter code of a language."""
    if not language:
        return None
    return language.lower().split("-")[0] or None


def _pick(product: dict[str, Any], field: str, language: str | None) -> str | None:
    """Return a translated field, falling back to the international one."""
    keys = [f"{field}_{language}"] if language else []
    keys.append(field)
    for key in keys:
        value = product.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _split(value: str | None) -> list[str]:
    """Split one of Open Food Facts' comma separated lists."""
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _prettify(value: str) -> str:
    """Turn a slug like 'produits-a-tartiner' into readable words."""
    if " " not in value and "-" in value:
        value = value.replace("-", " ")
    return value[:1].upper() + value[1:] if value else value


def _categories(product: dict[str, Any], language: str | None) -> list[str]:
    """Return the category path, dropping the raw slugs.

    Open Food Facts mixes proper names with slugs left over from other
    languages - "Confectionary based spreads" next to "produits-a-tartiner" -
    so the written-out ones are kept and the rest dropped. When a product has
    nothing but slugs they are tidied up instead, since something beats
    nothing.
    """
    listed = _split(_pick(product, "categories", language))
    if worded := [item for item in listed if " " in item or "-" not in item]:
        return worded
    if listed:
        return [_prettify(item) for item in listed]
    return _untag(product.get("categories_tags"))


def _grade(value: Any) -> str | None:
    """Return a score grade, or None when Open Food Facts has no verdict."""
    if not isinstance(value, str):
        return None
    grade = value.strip().lower()
    if grade in ("", "unknown", "not-applicable"):
        return None
    return grade


def _untag(tags: Any) -> list[str]:
    """Turn tags like 'en:milk' into 'Milk'."""
    if not isinstance(tags, list):
        return []
    names = []
    for tag in tags:
        if not isinstance(tag, str):
            continue
        name = tag.split(":", 1)[-1].strip()
        if name:
            names.append(_prettify(name))
    return names


def _nutriments(raw: Any) -> list[dict[str, Any]]:
    """Return the per-100 g values that are actually present."""
    if not isinstance(raw, dict):
        return []

    rows = []
    for key, label, unit in NUTRIMENTS:
        value = raw.get(f"{key}_100g")
        if not isinstance(value, (int, float)):
            continue
        rows.append({"key": key, "label": label, "value": round(float(value), 2), "unit": unit})
    return rows


def _fields(language: str | None) -> str:
    """Build the fields parameter for the API call."""
    fields = list(PLAIN_FIELDS) + list(TRANSLATED_FIELDS)
    if language:
        fields += [f"{field}_{language}" for field in TRANSLATED_FIELDS]
    return ",".join(fields)


async def async_fetch(
    hass: HomeAssistant, code: str, language: str | None = None, kind: str | None = None
) -> dict[str, Any] | None:
    """Fetch everything the Open Food Facts family knows about a barcode.

    Open Food Facts is asked first and Open Products Facts after it, unless
    `kind` says which one answered last time - a re-lookup should not walk the
    whole family again. Returns None when neither knows the barcode.
    """
    language = _language(language)
    order = [kind] if kind in SITES else []
    order += [name for name in SITES if name not in order]

    for name in order:
        found = await _async_fetch_from(hass, SITES[name], name, code, language)
        if found is not None:
            return found
    return None


async def _async_fetch_from(
    hass: HomeAssistant, host: str, kind: str, code: str, language: str | None
) -> dict[str, Any] | None:
    """Ask one of the databases about a barcode."""
    session = async_get_clientsession(hass)

    try:
        response = await session.get(
            API_URL.format(host=host, code=code),
            params={"fields": _fields(language)},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        if response.status == 404:
            return None
        response.raise_for_status()
        payload = await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
        _LOGGER.warning("%s lookup for %s failed: %s", host, code, err)
        return None

    if payload.get("status") != 1:
        return None

    product = payload.get("product") or {}
    name = _pick(product, "product_name", language) or _pick(
        product, "generic_name", language
    )
    if not name:
        return None

    brands = _split(product.get("brands"))
    brand = brands[0] if brands else None
    quantity = (product.get("quantity") or "").strip() or None
    categories = _categories(product, language)

    # Open Food Facts keeps the brand out of product_name, which leaves names
    # like "Original Taste" that say nothing on a shopping list.
    label = name
    if brand and brand.lower() not in label.lower():
        label = f"{brand} {label}"
    if quantity and quantity.lower() not in label.lower():
        label = f"{label} {quantity}"

    return {
        "code": code,
        # Which database answered: a grocery, or a thing.
        "kind": kind,
        # What the shopping list and the product row use.
        "label": label,
        "category": categories[-1] if categories else None,
        "image": product.get("image_front_small_url")
        or product.get("image_front_url")
        or None,
        # The full picture, for the details page.
        "name": name,
        "generic_name": _pick(product, "generic_name", language),
        "brand": brand,
        "brands": brands,
        "quantity": quantity,
        "serving_size": (product.get("serving_size") or "").strip() or None,
        "categories": categories,
        "labels": [_prettify(item) for item in _split(_pick(product, "labels", language))],
        "stores": _split(product.get("stores")),
        "countries": _split(_pick(product, "countries", language)),
        "origins": (product.get("origins") or "").strip() or None,
        "manufacturing_places": (product.get("manufacturing_places") or "").strip() or None,
        "packaging": _pick(product, "packaging", language),
        "ingredients": _pick(product, "ingredients_text", language),
        "allergens": _untag(product.get("allergens_tags")),
        "traces": _untag(product.get("traces_tags")),
        "grades": {
            "nutriscore": _grade(product.get("nutriscore_grade")),
            "nova": product.get("nova_group"),
            "ecoscore": _grade(product.get("ecoscore_grade")),
        },
        "nutriments": _nutriments(product.get("nutriments")),
        "images": {
            "front": product.get("image_front_url") or None,
            "ingredients": product.get("image_ingredients_url") or None,
            "nutrition": product.get("image_nutrition_url") or None,
        },
        "url": PRODUCT_URL.format(host=host, code=code),
        "fetched": dt_util.utcnow().isoformat(),
    }


async def async_lookup(
    hass: HomeAssistant, code: str, language: str | None = None
) -> dict[str, Any] | None:
    """Return just the fields a scan needs: name, brand, category and image."""
    if (details := await async_fetch(hass, code, language)) is None:
        return None
    return {
        "name": details["label"],
        "brand": details["brand"],
        "category": details["category"],
        "image": details["image"],
    }
