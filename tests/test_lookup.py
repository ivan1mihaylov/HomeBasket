"""Checks where a barcode is looked for, without a running Home Assistant.

Open Food Facts knows groceries, Open Beauty Facts cosmetics, Open Pet Food
Facts what the cat eats, and Open Products Facts everything else. A barcode is
looked for in all four, and which one answered is what a product turns out to
be:

    python3 tests/test_lookup.py
"""

from __future__ import annotations

import asyncio
import datetime
import sys
import types
from pathlib import Path

for name in (
    "homeassistant",
    "homeassistant.core",
    "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.util",
):
    sys.modules.setdefault(name, types.ModuleType(name))

aiohttp = types.ModuleType("aiohttp")
aiohttp.ClientError = type("ClientError", (Exception,), {})
aiohttp.ClientTimeout = lambda **kwargs: None
sys.modules["aiohttp"] = aiohttp

sys.modules["homeassistant.core"].HomeAssistant = object
sys.modules["homeassistant.util"].dt = types.SimpleNamespace(
    utcnow=lambda: datetime.datetime(2026, 1, 1)
)

_COMPONENT = Path(__file__).resolve().parent.parent / "custom_components" / "homebasket"
_package = types.ModuleType("homebasket")
_package.__path__ = [str(_COMPONENT)]
sys.modules["homebasket"] = _package

# What each database would answer with.
FOOD = {
    "status": 1,
    "product": {
        "product_name": "Fresh milk",
        "brands": "Vereya",
        "quantity": "1 l",
        "categories": "Dairies, Milks",
        "nutriscore_grade": "b",
        "nutriments": {"fat_100g": 3.6},
        "image_front_small_url": "https://images.openfoodfacts.org/milk.jpg",
    },
}
SHAMPOO = {
    "status": 1,
    "product": {
        "product_name": "Shampoo",
        "brands": "Nivea",
        "quantity": "250 ml",
        "categories": "Hair care, Shampoos",
        "ingredients_text": "Aqua, Sodium laureth sulfate",
    },
}
KIBBLE = {
    "status": 1,
    "product": {
        "product_name": "Pouch beef loaf",
        "brands": "Pedigree",
        "quantity": "100 g",
        "categories": "Dog food",
        "nutriments": {"proteins_100g": 8},
    },
}
THING = {
    "status": 1,
    "product": {
        "product_name": "864GL-82X-ONE",
        "brands": "Sinsay",
        "categories": "Lamps",
        "origins": "China",
        "image_front_small_url": "https://images.openproductsfacts.org/lamp.jpg",
    },
}
NOTHING = {"status": 0}

ANSWERS = {}
ASKED: list[str] = []


class FakeResponse:
    def __init__(self, payload) -> None:
        self.payload = payload
        self.status = 200

    def raise_for_status(self) -> None:
        pass

    async def json(self, content_type=None):
        return self.payload


class FakeSession:
    async def get(self, url, **kwargs):
        host = url.split("//", 1)[1].split("/", 1)[0]
        ASKED.append(host)
        if host not in ANSWERS:
            raise AssertionError(f"asked an unexpected host: {host}")
        return FakeResponse(ANSWERS[host])


sys.modules["homeassistant.helpers.aiohttp_client"].async_get_clientsession = (
    lambda hass: FakeSession()
)

from homebasket import openfoodfacts  # noqa: E402

FOOD_HOST = "world.openfoodfacts.org"
BEAUTY_HOST = "world.openbeautyfacts.org"
PET_HOST = "world.openpetfoodfacts.org"
THING_HOST = "world.openproductsfacts.org"
NOWHERE = {FOOD_HOST: NOTHING, BEAUTY_HOST: NOTHING, PET_HOST: NOTHING, THING_HOST: NOTHING}


def check(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: got {actual!r}, expected {expected!r}")
    print(f"  ok  {label}")


async def fetch(**answers):
    ANSWERS.clear()
    ANSWERS.update(answers)
    ASKED.clear()
    return await openfoodfacts.async_fetch(None, "123", "en")


async def main() -> None:
    found = await fetch(**{**NOWHERE, FOOD_HOST: FOOD})
    check("a grocery is found in Open Food Facts", found["kind"], "food")
    check("...and nothing else is asked", ASKED, [FOOD_HOST])
    check("...with the brand in front of the name", found["label"], "Vereya Fresh milk 1 l")
    check("...and its nutrition", found["grades"]["nutriscore"], "b")
    check("...linking to the right site", found["url"], f"https://{FOOD_HOST}/product/123")

    found = await fetch(**{**NOWHERE, BEAUTY_HOST: SHAMPOO})
    check("a cosmetic is found in Open Beauty Facts", found["kind"], "beauty")
    check("...after food, and no further", ASKED, [FOOD_HOST, BEAUTY_HOST])
    check("...with its ingredients", found["ingredients"], "Aqua, Sodium laureth sulfate")

    found = await fetch(**{**NOWHERE, PET_HOST: KIBBLE})
    check("what the cat eats is found in Open Pet Food Facts", found["kind"], "petfood")
    check("...after the other two", ASKED, [FOOD_HOST, BEAUTY_HOST, PET_HOST])
    check("...and it has nutrition like any food", len(found["nutriments"]), 1)

    found = await fetch(**{**NOWHERE, THING_HOST: THING})
    check("everything else is found in Open Products Facts", found["kind"], "product")
    check("...which is asked last", ASKED, [FOOD_HOST, BEAUTY_HOST, PET_HOST, THING_HOST])
    check("...and it is the thing it found", found["label"], "Sinsay 864GL-82X-ONE")
    check("...with no nutrition to speak of", found["nutriments"], [])
    check("...and no scores", found["grades"]["nutriscore"], None)
    check("...linking to the site that knew it", found["url"], f"https://{THING_HOST}/product/123")

    found = await fetch(**NOWHERE)
    check("a barcode none of them knows is unknown", found, None)
    check(
        "...after asking all four",
        ASKED,
        [FOOD_HOST, BEAUTY_HOST, PET_HOST, THING_HOST],
    )

    # A re-lookup of something already known goes straight to its database.
    ANSWERS.clear()
    ANSWERS.update({THING_HOST: THING})
    ASKED.clear()
    found = await openfoodfacts.async_fetch(None, "123", "en", kind="product")
    check("a known thing is looked up where it was found", ASKED, [THING_HOST])
    check("...and comes back the same", found["kind"], "product")

    print("\nall lookup checks passed")


if __name__ == "__main__":
    asyncio.run(main())
