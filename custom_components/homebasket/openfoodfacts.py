"""Thin async client for the Open Food Facts product API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import VERSION

_LOGGER = logging.getLogger(__name__)

API_URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
BASE_FIELDS = (
    "code",
    "product_name",
    "generic_name",
    "brands",
    "quantity",
    "image_front_small_url",
)
TIMEOUT = aiohttp.ClientTimeout(total=10)
USER_AGENT = f"HomeBasket/{VERSION} (Home Assistant custom integration)"


def _pick_name(product: dict[str, Any], language: str | None) -> str | None:
    """Return the best available product name, preferring the user's language."""
    candidates = []
    if language:
        lang = language.lower().split("-")[0]
        candidates += [f"product_name_{lang}", f"generic_name_{lang}"]
    candidates += ["product_name", "generic_name"]

    for key in candidates:
        value = product.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


async def async_lookup(
    hass: HomeAssistant, code: str, language: str | None = None
) -> dict[str, Any] | None:
    """Look a barcode up. Returns None when the product is unknown."""
    fields = list(BASE_FIELDS)
    if language:
        lang = language.lower().split("-")[0]
        fields += [f"product_name_{lang}", f"generic_name_{lang}"]

    session = async_get_clientsession(hass)
    url = API_URL.format(code=code)

    try:
        response = await session.get(
            url,
            params={"fields": ",".join(fields)},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        if response.status == 404:
            return None
        response.raise_for_status()
        payload = await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
        _LOGGER.warning("Open Food Facts lookup for %s failed: %s", code, err)
        return None

    if payload.get("status") != 1:
        return None

    product = payload.get("product") or {}
    name = _pick_name(product, language)
    if not name:
        return None

    brand = (product.get("brands") or "").split(",")[0].strip() or None
    quantity = (product.get("quantity") or "").strip() or None
    if quantity and quantity.lower() not in name.lower():
        name = f"{name} {quantity}"

    return {
        "name": name,
        "brand": brand,
        "image": product.get("image_front_small_url") or None,
    }
