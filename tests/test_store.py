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

from homebasket.store import MappingStore, code_variants, is_local  # noqa: E402

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

    # --- which kind of shop a product is bought in -------------------------
    # The database that knew the barcode says where you go for it: a
    # supermarket for groceries and things alike, the pet shop for what the cat
    # eats, the chemist's for a shampoo.
    shops = await store()
    for code, name, kind, expected in (
        ("1", "Мляко", "food", "groceries"),
        ("2", "Лампа", "product", "groceries"),
        ("3", "Котешка храна", "petfood", "pets"),
        ("4", "Шампоан", "beauty", "cosmetics"),
    ):
        await shops.async_save_mapping(code, name, kind=kind)
        check(f"{kind} is bought at the {expected}", shops.get(code)["department"], expected)

    # Moved by hand, and it stays moved however often it is looked up again.
    await shops.async_set_department("1", "produce")
    check("a product can be moved", shops.get("1")["department"], "produce")
    await shops.async_save_mapping("1", "Мляко", kind="food")
    check("...and stays where it was put", shops.get("1")["department"], "produce")

    # One saved before any of this had no kind either; the lookup that gives it
    # one gives it a shop too.
    await shops.async_save_mapping("5", "Хляб")
    check("a product with no kind has no shop yet", shops.get("5").get("department"), None)
    await shops.async_set_kind("5", "food")
    check("...and learns both at once", shops.get("5")["department"], "groceries")

    # --- a product with no barcode -----------------------------------------
    # A shopping list configures things that were never scanned; they are kept
    # under a key of their own until someone gives them a barcode.
    loose = await store()
    milk = await loose.async_create_local("Мляко", department="groceries", source="list")
    check("a product can be kept without a barcode", milk["code"].startswith("local:"), True)
    check("...with what was configured for it", milk["department"], "groceries")
    check("...and it is found by name", loose.find_by_name("мляко")[0], milk["code"])
    check("...only by exactly that name", loose.find_by_name("мля"), None)

    second = await loose.async_create_local("Мляко")
    check("two things of the same name get their own keys", second["code"] != milk["code"], True)

    # A barcode given to it later behaves like any other barcode of a product.
    await loose.async_add_alias("3800024911001", milk["code"])
    check("scanning the barcode finds it", loose.resolve("3800024911001")[0], milk["code"])
    check("...and the name comes with it", loose.get("3800024911001")["name"], "Мляко")
    check(
        "...while its own key is not a barcode",
        [code for code in loose.codes_for(milk["code"]) if not is_local(code)],
        ["3800024911001"],
    )

    # Renaming leaves everything else about a product as it was.
    await loose.async_save_mapping("4003994103586", "Кисело мляко", kind="food")
    before = dict(loose.get("4003994103586"))
    check("renaming says it changed something", await loose.async_set_name("4003994103586", "Кисело мляко 3,6%"), True)
    after = loose.get("4003994103586")
    check("...the name is the new one", after["name"], "Кисело мляко 3,6%")
    check("...what it is stays", (after["kind"], after["source"]), (before["kind"], before["source"]))
    check("...and the same name again changes nothing", await loose.async_set_name("4003994103586", "Кисело мляко 3,6%"), False)
    check("...nor does an empty one", await loose.async_set_name("4003994103586", "  "), False)

    print("\nall barcode checks passed")


if __name__ == "__main__":
    asyncio.run(main())
