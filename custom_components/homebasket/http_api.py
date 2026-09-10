"""REST endpoints for scanners that cannot fire Home Assistant events."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback

from .const import DATA_API, DOMAIN
from .manager import HomeBasketManager

_REGISTERED = f"{DOMAIN}_http_registered"

SCAN_SCHEMA = vol.Schema(
    {
        vol.Required("code"): vol.Coerce(str),
        vol.Optional("add_to_list", default=True): bool,
    }
)


@callback
def async_register_http_api(hass: HomeAssistant) -> None:
    """Register the HTTP views once."""
    if hass.data.get(_REGISTERED):
        return
    hass.data[_REGISTERED] = True
    hass.http.register_view(HomeBasketScanView)
    hass.http.register_view(HomeBasketMappingsView)
    hass.http.register_view(HomeBasketProductView)


def _manager(request: web.Request) -> HomeBasketManager | None:
    """Return the active manager for a request."""
    hass: HomeAssistant = request.app["hass"]
    managers = list(hass.data.get(DOMAIN, {}).values())
    return managers[0] if managers else None


class HomeBasketScanView(HomeAssistantView):
    """POST a barcode straight into the pipeline."""

    url = f"/api/{DOMAIN}/scan"
    name = f"api:{DOMAIN}:scan"

    async def post(self, request: web.Request) -> web.Response:
        """Handle a scanned code."""
        if (manager := _manager(request)) is None:
            return self.json_message("HomeBasket is not set up", 503)

        try:
            data: dict[str, Any] = SCAN_SCHEMA(await request.json())
        except (ValueError, vol.Invalid) as err:
            return self.json_message(f"Invalid payload: {err}", 400)

        result = await manager.async_handle_code(
            data["code"], add_to_list=data["add_to_list"], source="rest"
        )
        return self.json(result)


class HomeBasketMappingsView(HomeAssistantView):
    """Read the learned barcode dictionary."""

    url = f"/api/{DOMAIN}/mappings"
    name = f"api:{DOMAIN}:mappings"

    async def get(self, request: web.Request) -> web.Response:
        """Return every mapping."""
        if (manager := _manager(request)) is None:
            return self.json_message("HomeBasket is not set up", 503)
        return self.json(
            {
                "mappings": manager.store.as_list(),
                "pending": manager.store.pending_as_list(),
            }
        )


class HomeBasketProductView(HomeAssistantView):
    """Read one product, with its Open Food Facts record."""

    url = f"/api/{DOMAIN}/product/{{code}}"
    name = f"api:{DOMAIN}:product"

    async def get(self, request: web.Request, code: str) -> web.Response:
        """Return a single product."""
        hass: HomeAssistant = request.app["hass"]
        if (api := hass.data.get(DATA_API)) is None:
            return self.json_message("HomeBasket is not set up", 503)

        if (product := api.get(code)) is None:
            return self.json_message(f"No product for {code}", 404)

        if request.query.get("details", "1") not in ("0", "false", "no"):
            product["details"] = await api.async_get_details(code)
        if request.query.get("photo") in ("1", "true", "yes"):
            product["photo"] = await api.async_get_photo(code)
        return self.json(product)
