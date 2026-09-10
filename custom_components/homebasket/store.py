"""Persistent storage of barcode → product mappings."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import SOURCE_IMPORT, SOURCE_MANUAL, STORAGE_KEY, STORAGE_VERSION

# Sentinel for "leave this field as it is", so that passing None can mean
# "clear this field" - the card needs both.
KEEP = object()

# A product is stored under its first barcode. Any further barcode for the
# same product is stored as {"alias_of": "<first barcode>"}, so the same
# yoghurt in a 400 g and a 900 g tub can share one entry.
ALIAS_KEY = "alias_of"


def normalize_code(code: Any) -> str:
    """Return a canonical representation of a scanned code."""
    return str(code or "").strip()


def code_variants(code: str) -> list[str]:
    """Return the ways the same physical barcode can be reported.

    A UPC-A label is twelve digits, and the very same label read as EAN-13
    comes back with a leading zero. Which one you get depends on the scanner,
    so a product saved from one reading must still be found by the other -
    otherwise scanning a product you already have creates a second one.
    """
    code = normalize_code(code)
    if not code.isdigit():
        return [code]
    if len(code) == 13 and code.startswith("0"):
        return [code, code[1:]]
    if len(code) == 12:
        return [code, f"0{code}"]
    return [code]


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

    def resolve(self, code: str) -> tuple[str, dict[str, Any]] | None:
        """Return the (primary code, product) a barcode belongs to."""
        for candidate in code_variants(code):
            if (entry := self._mappings.get(candidate)) is None:
                continue
            if (primary := entry.get(ALIAS_KEY)) is None:
                return candidate, entry

            target = self._mappings.get(primary)
            if target is not None and ALIAS_KEY not in target:
                return primary, target
            # A dangling alias behaves like an unknown code, but the other
            # spelling of the same barcode may still lead somewhere.
        return None

    def get(self, code: str) -> dict[str, Any] | None:
        """Return the product a barcode belongs to, or None when unknown."""
        resolved = self.resolve(code)
        return resolved[1] if resolved else None

    def codes_for(self, primary: str) -> list[str]:
        """Return every barcode of a product, its first one first."""
        primary = normalize_code(primary)
        aliases = sorted(
            code
            for code, entry in self._mappings.items()
            if entry.get(ALIAS_KEY) == primary
        )
        return [primary, *aliases]

    def as_list(self) -> list[dict[str, Any]]:
        """Return the products as a list suitable for the frontend."""
        return [
            {"code": code, "codes": self.codes_for(code), **entry}
            for code, entry in self._mappings.items()
            if ALIAS_KEY not in entry
        ]

    def pending_as_list(self) -> list[dict[str, Any]]:
        """Return the pending codes as a list suitable for the frontend."""
        return [{"code": code, **entry} for code, entry in self._pending.items()]

    async def async_save_mapping(
        self,
        code: str,
        name: str,
        *,
        brand: str | None = None,
        category: str | None | object = KEEP,
        image: str | None | object = KEEP,
        source: str = SOURCE_MANUAL,
    ) -> dict[str, Any]:
        """Create or update a product and drop the code from the pending list."""
        scanned = normalize_code(code)
        code = resolved[0] if (resolved := self.resolve(scanned)) else scanned
        now = dt_util.utcnow().isoformat()
        existing = self._mappings.get(code, {})

        entry = {
            **existing,
            "name": name.strip(),
            "brand": brand or existing.get("brand"),
            "category": existing.get("category") if category is KEEP else category,
            "image": existing.get("image") if image is KEEP else image,
            "source": source,
            "created": existing.get("created", now),
            "updated": now,
            "scan_count": existing.get("scan_count", 0),
        }
        self._mappings[code] = entry
        self._pending.pop(code, None)
        self._pending.pop(scanned, None)
        await self._async_save()
        return {"code": code, "codes": self.codes_for(code), **entry}

    async def async_remove_mapping(self, code: str) -> list[str]:
        """Remove a product and every barcode of it.

        Returns the codes that were removed, so their photos and cached
        records can be cleaned up too.
        """
        scanned = normalize_code(code)
        removed: list[str] = []

        if (resolved := self.resolve(scanned)) is not None:
            for entry_code in self.codes_for(resolved[0]):
                self._mappings.pop(entry_code, None)
                self._pending.pop(entry_code, None)
                removed.append(entry_code)
        elif self._mappings.pop(scanned, None) is not None:
            removed.append(scanned)  # A dangling alias.

        if self._pending.pop(scanned, None) is not None and scanned not in removed:
            removed.append(scanned)

        if removed:
            await self._async_save()
        return removed

    async def async_add_alias(self, code: str, primary: str) -> str | None:
        """Attach a barcode to an existing product.

        When the barcode is itself a product, its own barcodes come along and
        its entry is dropped. Returns the product's first barcode, or None
        when the target does not exist.
        """
        code = normalize_code(code)
        if (resolved := self.resolve(primary)) is None:
            return None

        target = resolved[0]
        if code == target or not code:
            return target

        for other, entry in list(self._mappings.items()):
            if entry.get(ALIAS_KEY) == code:
                self._mappings[other] = {ALIAS_KEY: target}

        self._mappings[code] = {ALIAS_KEY: target}
        self._pending.pop(code, None)
        await self._async_save()
        return target

    async def async_remove_alias(self, code: str) -> bool:
        """Detach a barcode from its product, leaving the product alone."""
        code = normalize_code(code)
        if ALIAS_KEY not in (self._mappings.get(code) or {}):
            return False
        del self._mappings[code]
        await self._async_save()
        return True

    async def async_remove_pending(self, code: str) -> bool:
        """Drop a code from the pending list, leaving any mapping alone."""
        if self._pending.pop(normalize_code(code), None) is None:
            return False
        await self._async_save()
        return True

    async def async_record_scan(self, code: str) -> None:
        """Increase the scan counter of a known product."""
        if (resolved := self.resolve(code)) is None:
            return
        entry = resolved[1]
        entry["scan_count"] = entry.get("scan_count", 0) + 1
        entry["last_scanned"] = dt_util.utcnow().isoformat()
        await self._async_save()

    async def async_add_pending(self, code: str) -> None:
        """Remember a code we could not identify so the card can ask for a name."""
        code = normalize_code(code)
        if self.resolve(code) is not None:
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
