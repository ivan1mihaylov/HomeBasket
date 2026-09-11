"""Checks where a scanned product ends up, without a running Home Assistant.

HomeBasket works on its own and alongside HomeBasket Lists, and neither may
depend on the other being there:

    python3 tests/test_shopping_list.py
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
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.dispatcher",
    "homeassistant.helpers.storage",
    "homeassistant.config_entries",
    "homeassistant.util",
):
    sys.modules.setdefault(name, types.ModuleType(name))

sys.modules.setdefault("aiohttp", types.ModuleType("aiohttp"))
sys.modules["aiohttp"].ClientError = Exception
sys.modules["aiohttp"].ClientSession = object
sys.modules["aiohttp"].ClientTimeout = lambda **kwargs: None

sys.modules["homeassistant.core"].HomeAssistant = object
sys.modules["homeassistant.core"].Event = object
sys.modules["homeassistant.core"].callback = lambda func: func
sys.modules["homeassistant.config_entries"].ConfigEntry = object
sys.modules["homeassistant.helpers.dispatcher"].async_dispatcher_send = (
    lambda *a, **k: None
)
sys.modules["homeassistant.helpers.aiohttp_client"].async_get_clientsession = (
    lambda hass: None
)
sys.modules["homeassistant.util"].dt = types.SimpleNamespace(
    utcnow=lambda: datetime.datetime(2026, 1, 1)
)


class _Store:
    def __init__(self, *args, **kwargs) -> None:
        self.data = None

    async def async_load(self):
        return self.data

    async def async_save(self, data) -> None:
        self.data = data


sys.modules["homeassistant.helpers.storage"].Store = _Store

_COMPONENT = Path(__file__).resolve().parent.parent / "custom_components" / "homebasket"
_package = types.ModuleType("homebasket")
_package.__path__ = [str(_COMPONENT)]
sys.modules["homebasket"] = _package

from homebasket.manager import HomeBasketManager  # noqa: E402
from homebasket.store import MappingStore  # noqa: E402

TODO = "todo.shopping"


class FakeTodo:
    """The built-in shopping list, as far as the manager can tell."""

    def __init__(self) -> None:
        self.items: list[str] = []

    async def async_call(self, domain, service, data, **kwargs):
        assert domain == "todo", domain
        if service == "get_items":
            return {TODO: {"items": [{"summary": name} for name in self.items]}}
        if service == "add_item":
            self.items.append(data["item"])
            return None
        raise AssertionError(f"unexpected todo.{service}")


class FakeBus:
    def async_fire(self, *args, **kwargs) -> None:
        pass


class FakeHass:
    def __init__(self, todo) -> None:
        self.services = todo
        self.bus = FakeBus()
        self.data: dict = {}


class FakeEntry:
    def __init__(self, **options) -> None:
        self.entry_id = "entry"
        self.data: dict = {}
        self.options = {"todo_entity": TODO, **options}


class FakeLists:
    """HomeBasket Lists, holding one list that counts what is on it."""

    def __init__(self, lists=("Пазар",), mode="count") -> None:
        self.mode = mode
        self.lists = [
            {"entry_id": f"list{i}", "name": name} for i, name in enumerate(lists)
        ]
        self.items: dict[str, dict] = {}
        self.calls: list[dict] = []

    async def async_add_item(self, summary, *, entry_id=None, name=None, **fields):
        self.calls.append({"summary": summary, "entry_id": entry_id, **fields})
        if entry_id is not None:
            board = next((b for b in self.lists if b["entry_id"] == entry_id), None)
        else:
            board = self.lists[0] if len(self.lists) == 1 else None
        if board is None:
            return None

        item = self.items.get(summary)
        if item is None:
            item = {"summary": summary, "quantity": fields.get("quantity") or 1}
            self.items[summary] = item
            return {"list": board["name"], "item": item, "outcome": "added"}

        if self.mode == "ignore":
            return {"list": board["name"], "item": item, "outcome": "kept"}

        item["quantity"] += fields.get("quantity") or 1
        return {"list": board["name"], "item": item, "outcome": "counted"}


class Ancient:
    """A HomeBasket Lists too old to be written to."""

    lists: list = []


def check(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: got {actual!r}, expected {expected!r}")
    print(f"  ok  {label}")


async def manager(hass, **options) -> HomeBasketManager:
    store = MappingStore(None)
    await store.async_load()
    images = types.SimpleNamespace(has=lambda code: False)
    return HomeBasketManager(hass, FakeEntry(**options), store, images, None)


async def main() -> None:
    # --- on its own, with only a to-do list --------------------------------
    todo = FakeTodo()
    hass = FakeHass(todo)
    alone = await manager(hass)

    check(
        "without HomeBasket Lists a scan lands on the to-do list",
        await alone.async_add_to_list("Мляко"),
        {
            "added": True,
            "increased": False,
            "already_on_list": False,
            "quantity": None,
            "list": TODO,
        },
    )
    check("...and it is really there", todo.items, ["Мляко"])
    check(
        "scanning it again says it is already there",
        (await alone.async_add_to_list("Мляко"))["already_on_list"],
        True,
    )
    check("...without repeating the line", todo.items, ["Мляко"])

    # --- with HomeBasket Lists ---------------------------------------------
    todo = FakeTodo()
    hass = FakeHass(todo)
    lists = FakeLists()
    hass.data["homebasket_lists_api"] = lists
    paired = await manager(hass)

    first = await paired.async_add_to_list("Мляко", code="123")
    check("with the lists installed, the scan goes there", first["added"], True)
    check("...on the only list there is", first["list"], "Пазар")
    check("...and the to-do list is left alone", todo.items, [])
    check("...carrying the barcode", lists.calls[0]["product_code"], "123")

    second = await paired.async_add_to_list("Мляко", code="123")
    check("scanning the same product again counts one more", second["increased"], True)
    check("...rather than adding a line", second["added"], False)
    check("...and says how many there are now", second["quantity"], 2)

    # A list set to keep what it has reports that, rather than a new line.
    todo = FakeTodo()
    hass = FakeHass(todo)
    hass.data["homebasket_lists_api"] = FakeLists(mode="ignore")
    keeping = await manager(hass)
    await keeping.async_add_to_list("Мляко")
    again = await keeping.async_add_to_list("Мляко")
    check("a list that keeps what it has says so", again["already_on_list"], True)
    check("...and nothing was added", again["added"], False)
    check("...and nothing was counted", again["increased"], False)

    # --- several lists and none chosen -------------------------------------
    todo = FakeTodo()
    hass = FakeHass(todo)
    hass.data["homebasket_lists_api"] = FakeLists(("Пазар", "Ремонт"))
    unsure = await manager(hass)
    check(
        "with several lists and none chosen, the to-do list is used",
        (await unsure.async_add_to_list("Мляко"))["list"],
        TODO,
    )

    todo = FakeTodo()
    hass = FakeHass(todo)
    hass.data["homebasket_lists_api"] = FakeLists(("Пазар", "Ремонт"))
    chosen = await manager(hass, lists_entry="list1")
    check(
        "choosing one sends the scan there",
        (await chosen.async_add_to_list("Мляко"))["list"],
        "Ремонт",
    )

    # --- an older HomeBasket Lists, and a broken one -----------------------
    todo = FakeTodo()
    hass = FakeHass(todo)
    hass.data["homebasket_lists_api"] = Ancient()
    old = await manager(hass)
    check(
        "a version that cannot be written to falls back",
        (await old.async_add_to_list("Мляко"))["list"],
        TODO,
    )

    class Broken(FakeLists):
        async def async_add_item(self, *args, **kwargs):
            raise RuntimeError("boom")

    todo = FakeTodo()
    hass = FakeHass(todo)
    hass.data["homebasket_lists_api"] = Broken()
    broken = await manager(hass)
    check(
        "and so does one that throws",
        (await broken.async_add_to_list("Мляко"))["list"],
        TODO,
    )

    # --- nothing configured at all -----------------------------------------
    hass = FakeHass(FakeTodo())
    nowhere = await manager(hass)
    nowhere.entry.options["todo_entity"] = None
    check(
        "with no shopping list anywhere, nothing is added and nothing breaks",
        (await nowhere.async_add_to_list("Мляко"))["added"],
        False,
    )

    # --- what the card is shown --------------------------------------------
    hass = FakeHass(FakeTodo())
    shelf = await manager(hass)
    shelf.remember_scan({"code": "1", "name": "Milk"})
    shelf.remember_scan({"code": "2", "name": "Bread"})
    shelf.remember_scan({"code": "1", "name": "Milk"})
    check("a scan goes to the front of the recent list", [s["code"] for s in shelf.recent], ["1", "2"])
    check("...listed once per barcode", len(shelf.recent), 2)

    check("a scan can be dismissed", await shelf.async_forget_scan("1"), True)
    check("...and only once", await shelf.async_forget_scan("1"), False)
    check("...leaving the others", [s["code"] for s in shelf.recent], ["2"])

    for index in range(12):
        shelf.remember_scan({"code": f"code{index}", "name": "x"})
    check("the list does not grow forever", len(shelf.recent), 8)

    print("\nall shopping list checks passed")


if __name__ == "__main__":
    asyncio.run(main())
