"""Public interface for other integrations.

Another integration reads HomeBasket's data through this object rather than by
reaching into the manager, so the internals can change without breaking it:

    from homeassistant.core import HomeAssistant

    api = hass.data.get("homebasket_api")
    if api is not None and api.api_version >= 1:
        for product in api.products:
            ...

Everything here is read-only apart from `async_resolve`, which is the same
pipeline a scan goes through. Listen for the `homebasket_updated` event to know
when the data changed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .manager import HomeBasketManager

# Bumped when the shape of what this returns changes in a breaking way.
API_VERSION = 1


class HomeBasketAPI:
    """A stable view of the products HomeBasket has learned."""

    def __init__(self, manager: HomeBasketManager) -> None:
        """Wrap a manager."""
        self._manager = manager

    @property
    def api_version(self) -> int:
        """Return the interface version, for consumers to check against."""
        return API_VERSION

    @property
    def todo_entity(self) -> str | None:
        """Return the to-do list scanned products are added to."""
        return self._manager.todo_entity

    @property
    def language(self) -> str:
        """Return the language product information is fetched in."""
        return self._manager.language

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------
    @property
    def products(self) -> list[dict[str, Any]]:
        """Return every known product.

        Each entry carries `code` (the product's first barcode), `codes`
        (all of them), `name`, `brand`, `category`, `image`, `source`,
        `scan_count` and `has_photo`.
        """
        return [self._decorate(item) for item in self._manager.store.as_list()]

    @property
    def pending(self) -> list[dict[str, Any]]:
        """Return the scanned codes that could not be identified."""
        return self._manager.store.pending_as_list()

    def get(self, code: str) -> dict[str, Any] | None:
        """Return the product a barcode belongs to, or None when unknown.

        Any of a product's barcodes returns the same product.
        """
        if (resolved := self._manager.store.resolve(code)) is None:
            return None
        primary, entry = resolved
        return self._decorate(
            {"code": primary, "codes": self._manager.store.codes_for(primary), **entry}
        )

    def find(self, text: str) -> list[dict[str, Any]]:
        """Return the products whose name, brand or category matches `text`."""
        needle = (text or "").strip().casefold()
        if not needle:
            return []
        return [
            product
            for product in self.products
            if any(
                needle in str(product.get(field) or "").casefold()
                for field in ("name", "brand", "category", "code")
            )
        ]

    def _decorate(self, item: dict[str, Any]) -> dict[str, Any]:
        return {**item, "has_photo": self._manager.images.has(item["code"])}

    # ------------------------------------------------------------------
    # Extras that need to be read from disk or the network
    # ------------------------------------------------------------------
    async def async_get_details(
        self, code: str, *, refresh: bool = False
    ) -> dict[str, Any] | None:
        """Return the full Open Food Facts record for a barcode.

        The cached copy is used unless `refresh` is set, so this is cheap to
        call. Returns None when Open Food Facts does not know the product.
        """
        if not refresh:
            if (cached := await self._manager.details.async_get(code)) is not None:
                return cached
            if not self._manager.use_openfoodfacts:
                return None
        return await self._manager.async_fetch_details(code)

    async def async_get_photo(self, code: str) -> str | None:
        """Return the photo stored for a barcode as a data URL, if any.

        This is the picture the user took or uploaded. The `image` field of a
        product is a remote Open Food Facts URL and needs no call.
        """
        return await self._manager.images.async_get(code)

    async def async_resolve(
        self, code: str, *, add_to_list: bool = False, source: str = "api"
    ) -> dict[str, Any]:
        """Resolve a barcode the way a scan does.

        Looks in the local dictionary, then Open Food Facts, remembering what
        it finds. With `add_to_list` the product also goes on the shopping
        list. Returns the same payload as the `homebasket_scanned` event.
        """
        return await self._manager.async_handle_code(
            code, add_to_list=add_to_list, source=source
        )

    async def async_link_code(self, code: str, product: str) -> str | None:
        """Attach another barcode to an existing product.

        `product` may be any of the product's barcodes. Returns the product's
        first barcode, or None when there is no such product.
        """
        return await self._manager.async_link_code(code, product)

    async def async_shopping_list(self) -> list[str]:
        """Return the open items on the configured shopping list."""
        return await self._manager.async_list_items()
