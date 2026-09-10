"""Persistent storage of barcode → product mappings."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import SOURCE_IMPORT, SOURCE_MANUAL, STORAGE_KEY, STORAGE_VERSION

def normalize_code(code: Any) -> str:
    """Return a canonical representation of a scanned code."""
    return str(code or "").strip()


class MappingStore:
    """Keeps the barcode dictionary and the list of not-yet-named codes."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise the store."""
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY, private=True
        )
        self._mappings: dict[str, dict[str, Any]] = {}
        self._pending: dict[str, dict[str, Any]] = {}

    async def async_load(self) -> None:
        """Load the stored data from disk."""
        data = await self._store.async_load() or {}
        self._mappings = dict(data.get("mappings") or {})
        self._pending = dict(data.get("pending") or {})

    async def _async_save(self) -> None:
        await self._store.async_save(
            {"mappings": self._mappings, "pending": self._pending}
        )

    @property
    def mappings(self) -> dict[str, dict[str, Any]]:
        """Return all known mappings, keyed by code."""
        return self._mappings

    @property
    def pending(self) -> dict[str, dict[str, Any]]:
        """Return codes that were scanned but could not be identified."""
        return self._pending

    def get(self, code: str) -> dict[str, Any] | None:
        """Return a single mapping, or None when the code is unknown."""
        return self._mappings.get(normalize_code(code))

    def as_list(self) -> list[dict[str, Any]]:
        """Return the mappings as a list suitable for the frontend."""
        return [{"code": code, **entry} for code, entry in self._mappings.items()]

    def pending_as_list(self) -> list[dict[str, Any]]:
        """Return the pending codes as a list suitable for the frontend."""
        return [{"code": code, **entry} for code, entry in self._pending.items()]

    async def async_save_mapping(
        self,
        code: str,
        name: str,
        *,
        brand: str | None = None,
        category: str | None = None,
        image: str | None = None,
        source: str = SOURCE_MANUAL,
    ) -> dict[str, Any]:
        """Create or update a mapping and drop it from the pending list."""
        code = normalize_code(code)
        now = dt_util.utcnow().isoformat()
        existing = self._mappings.get(code, {})

        entry = {
            **existing,
            "name": name.strip(),
            "brand": brand or existing.get("brand"),
            "category": category if category is not None else existing.get("category"),
            "image": image or existing.get("image"),
            "source": source,
            "created": existing.get("created", now),
            "updated": now,
            "scan_count": existing.get("scan_count", 0),
        }
        self._mappings[code] = entry
        self._pending.pop(code, None)
        await self._async_save()
        return {"code": code, **entry}

    async def async_remove_mapping(self, code: str) -> bool:
        """Remove a mapping. Returns True when something was removed."""
        code = normalize_code(code)
        removed = self._mappings.pop(code, None) is not None
        removed = self._pending.pop(code, None) is not None or removed
        if removed:
            await self._async_save()
        return removed

    async def async_record_scan(self, code: str) -> None:
        """Increase the scan counter of a known mapping."""
        code = normalize_code(code)
        if (entry := self._mappings.get(code)) is None:
            return
        entry["scan_count"] = entry.get("scan_count", 0) + 1
        entry["last_scanned"] = dt_util.utcnow().isoformat()
        await self._async_save()

    async def async_add_pending(self, code: str) -> None:
        """Remember a code we could not identify so the card can ask for a name."""
        code = normalize_code(code)
        if code in self._mappings:
            return
        entry = self._pending.get(code, {"scan_count": 0})
        entry["scan_count"] = entry.get("scan_count", 0) + 1
        entry["last_scanned"] = dt_util.utcnow().isoformat()
        self._pending[code] = entry
        await self._async_save()

    async def async_import(
        self, mappings: dict[str, Any], *, overwrite: bool = False
    ) -> int:
        """Import mappings from another source. Returns the number imported."""
        imported = 0
        now = dt_util.utcnow().isoformat()

        for raw_code, raw_value in mappings.items():
            code = normalize_code(raw_code)
            if not code:
                continue
            if code in self._mappings and not overwrite:
                continue

            if isinstance(raw_value, dict):
                name = raw_value.get("name") or raw_value.get("product")
                brand = raw_value.get("brand") or raw_value.get("brands")
                category = raw_value.get("category")
                image = raw_value.get("image")
            else:
                name = raw_value
                brand = category = image = None

            if not name:
                continue

            self._mappings[code] = {
                "name": str(name).strip(),
                "brand": brand,
                "category": category,
                "image": image,
                "source": SOURCE_IMPORT,
                "created": now,
                "updated": now,
                "scan_count": 0,
            }
            imported += 1

        if imported:
            await self._async_save()
        return imported
