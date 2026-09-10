"""Checks the barcode dictionary without a running Home Assistant.

The store decides whether a scan is a product you already have or a new one,
which is the difference between opening a product and creating a duplicate:

    python3 tests/test_store.py
"""

from __future__ import annotations

import asyncio
import datetime
import sys
import types
from pathlib import Path

# --- Home Assistant stubs, before importing the integration ----------------
for name in (
    "homeassistant",
    "homeassistant.core",
    "homeassistant.helpers",
    "homeassistant.helpers.storage",
    "homeassistant.util",
):
    sys.modules.setdefault(name, types.ModuleType(name))

sys.modules["homeassistant.core"].HomeAssistant = object
sys.modules["homeassistant.util"].dt = types.SimpleNamespace(
    utcnow=lambda: datetime.datetime(2026, 1, 1)
)


class _Store:
    """Storage that keeps the data in memory."""

    def __init__(self, *args, **kwargs) -> None:
        self.data = None

    async def async_load(self):
        return self.data

    async def async_save(self, data) -> None:
        self.data = data


sys.modules["homeassistant.helpers.storage"].Store = _Store

_COMPONENT = (
    Path(__file__).resolve().parent.parent / "custom_components" / "homebasket"
)
_package = types.ModuleType("homebasket")
_package.__path__ = [str(_COMPONENT)]
sys.modules["homebasket"] = _package

from homebasket.store import MappingStore, code_variants  # noqa: E402

# The same physical label, read as UPC-A and as EAN-13.
UPC = "012345678905"
EAN = "0012345678905"


def check(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: got {actual!r}, expected {expected!r}")
    print(f"  ok  {label}")


async def store() -> MappingStore:
    made = MappingStore(None)
    await made.async_load()
    return made


async def main() -> None:
    check(
        "a twelve digit code is also its thirteen digit reading",
        code_variants(UPC),
        [UPC, EAN],
    )
    check(
        "and the other way round",
        code_variants(EAN),
        [EAN, UPC],
    )
    check(
        "a code that is not a barcode is left alone",
        code_variants("QR-ABC"),
        ["QR-ABC"],
    )
    check(
        "a thirteen digit code that is not a padded twelve is left alone",
        code_variants("4003994103586"),
        ["4003994103586"],
    )

    # A product saved from one scanner, scanned again by another.
    keeper = await store()
    await keeper.async_save_mapping(EAN, "Мляко")
    resolved = keeper.resolve(UPC)
    check("the same label read the short way finds the product", resolved[0], EAN)
    check("and it is the same product, not a copy", resolved[1]["name"], "Мляко")

    await keeper.async_save_mapping(UPC, "Мляко 3%")
    check("saving under the other reading edits it", len(keeper.mappings), 1)
    check("rather than creating a second one", keeper.mappings[EAN]["name"], "Мляко 3%")

    await keeper.async_record_scan(UPC)
    check("a scan of either reading counts", keeper.mappings[EAN]["scan_count"], 1)

    await keeper.async_add_pending(UPC)
    check("and a known product never lands in pending", keeper.pending, {})

    # Two genuinely different products stay apart.
    other = await store()
    await other.async_save_mapping("4003994103586", "Кисело мляко")
    check(
        "a different barcode is still unknown",
        other.resolve("5000159407236"),
        None,
    )

    # A barcode attached to a product is found by either reading too.
    linked = await store()
    await linked.async_save_mapping("111", "Кафе")
    await linked.async_add_alias(EAN, "111")
    check("an attached barcode resolves to its product", linked.resolve(UPC)[0], "111")

    print("\nall barcode checks passed")


if __name__ == "__main__":
    asyncio.run(main())
