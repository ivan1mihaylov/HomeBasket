"""Serve the barcode reader the card falls back to.

Chrome, Edge and the Android Companion app read barcodes themselves, through
the browser's `BarcodeDetector`. Safari - and therefore every iPhone - has no
such thing, so the card needs a library to do it instead.

It is shipped here rather than fetched from a CDN: the camera is pointed at
what is in your kitchen, and nothing about that should have to leave the house
for a third party to serve a script. The card loads it from this address only
when the browser has no reader of its own.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ZXING_FILE = "zxing.min.js"
ZXING_URL = f"/{DOMAIN}/{ZXING_FILE}"
_REGISTERED = f"{DOMAIN}_zxing_registered"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Publish the barcode reader for the card to fall back to."""
    if hass.data.get(_REGISTERED):
        return

    path = Path(__file__).parent / "frontend" / ZXING_FILE
    if not path.is_file():
        _LOGGER.warning(
            "The barcode reader is missing at %s. Browsers without one of "
            "their own - Safari and iOS - will not be able to scan",
            path,
        )
        return

    hass.data[_REGISTERED] = True
    await hass.http.async_register_static_paths(
        [StaticPathConfig(ZXING_URL, str(path), True)]
    )
