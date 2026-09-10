"""Cache of the full Open Food Facts record for each product.

The details are only useful when someone opens a product, and they are far
bulkier than a mapping, so they live in their own store that is loaded the
first time it is read rather than at startup.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .store import normalize_code

STORAGE_KEY = "homebasket.details"
STORAGE_VERSION = 1


class DetailStore:
    """Keeps one Open Food Facts record per barcode."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise the store."""
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._details: dict[str, dict[str, Any]] | None = None

    async def _async_loaded(self) -> dict[str, dict[str, Any]]:
        """Load the cache on first use."""
        if self._details is None:
            data = await self._store.async_load() or {}
            self._details = dict(data.get("details") or {})
        return self._details

    async def async_get(self, code: str) -> dict[str, Any] | None:
        """Return the cached record for a code, if there is one."""
        return (await self._async_loaded()).get(normalize_code(code))

    async def async_set(self, code: str, details: dict[str, Any]) -> None:
        """Store the record for a code."""
        cache = await self._async_loaded()
        cache[normalize_code(code)] = details
        await self._store.async_save({"details": cache})

    async def async_delete(self, code: str) -> bool:
        """Drop the record for a code. Returns True when one was dropped."""
        cache = await self._async_loaded()
        if cache.pop(normalize_code(code), None) is None:
            return False
        await self._store.async_save({"details": cache})
        return True
