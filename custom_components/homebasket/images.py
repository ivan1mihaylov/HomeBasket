"""Product photos taken or uploaded by the user.

Photos live outside the mapping store so the dictionary itself stays small and
cheap to load. They are read back through the WebSocket API as data URLs, so
they are never served from an unauthenticated path.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from pathlib import Path

from homeassistant.core import HomeAssistant

# 4 MB of base64 is roughly a 3 MB photo - far more than the card ever sends,
# but enough of a ceiling to keep a malformed client from filling the disk.
MAX_DATA_URL_LENGTH = 4 * 1024 * 1024

DATA_URL = re.compile(
    r"^data:image/(?P<format>jpeg|jpg|png|webp);base64,(?P<payload>.+)$", re.DOTALL
)
SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
EXTENSIONS = {"jpeg": "jpg", "jpg": "jpg", "png": "png", "webp": "webp"}
MIME_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


class InvalidImage(ValueError):
    """The submitted data URL is not an image this integration accepts."""


def _decode(data_url: str) -> tuple[bytes, str]:
    """Turn a data URL into raw bytes and a file extension."""
    if len(data_url) > MAX_DATA_URL_LENGTH:
        raise InvalidImage("The image is too large")

    match = DATA_URL.match(data_url.strip())
    if match is None:
        raise InvalidImage("Expected a base64 data URL of a JPEG, PNG or WebP image")

    try:
        raw = base64.b64decode(match["payload"], validate=True)
    except (binascii.Error, ValueError) as err:
        raise InvalidImage("The image is not valid base64") from err

    if not raw:
        raise InvalidImage("The image is empty")
    return raw, EXTENSIONS[match["format"]]


class ImageStore:
    """Reads and writes the product photos on disk."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise the store."""
        self.hass = hass
        self._dir = Path(hass.config.path(".storage", "homebasket_images"))
        self._known: set[str] = set()

    @staticmethod
    def _stem(code: str) -> str:
        """Return a file name that is safe for any scanned code."""
        code = str(code).strip()
        if SAFE_NAME.match(code):
            return code
        return hashlib.sha1(code.encode("utf-8")).hexdigest()

    def _find(self, code: str) -> Path | None:
        return next(self._dir.glob(f"{self._stem(code)}.*"), None)

    async def async_load(self) -> None:
        """Read which codes have a photo, so the card can render placeholders."""

        def _scan() -> set[str]:
            if not self._dir.is_dir():
                return set()
            return {path.stem for path in self._dir.iterdir() if path.is_file()}

        self._known = await self.hass.async_add_executor_job(_scan)

    def has(self, code: str) -> bool:
        """Return whether a code has a locally stored photo."""
        return self._stem(code) in self._known

    async def async_get(self, code: str) -> str | None:
        """Return the photo as a data URL, or None when there is none."""
        if not self.has(code):
            return None

        def _read() -> tuple[bytes, str] | None:
            if (path := self._find(code)) is None:
                return None
            return path.read_bytes(), path.suffix.lstrip(".")

        if (result := await self.hass.async_add_executor_job(_read)) is None:
            return None

        raw, extension = result
        mime = MIME_TYPES.get(extension, "image/jpeg")
        return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"

    async def async_set(self, code: str, data_url: str) -> None:
        """Store a photo, replacing any previous one for the same code."""
        raw, extension = _decode(data_url)
        stem = self._stem(code)

        def _write() -> None:
            self._dir.mkdir(parents=True, exist_ok=True)
            for existing in self._dir.glob(f"{stem}.*"):
                existing.unlink(missing_ok=True)
            (self._dir / f"{stem}.{extension}").write_bytes(raw)

        await self.hass.async_add_executor_job(_write)
        self._known.add(stem)

    async def async_delete(self, code: str) -> bool:
        """Remove the photo of a code. Returns True when one was removed."""
        if not self.has(code):
            return False
        stem = self._stem(code)

        def _remove() -> None:
            for existing in self._dir.glob(f"{stem}.*"):
                existing.unlink(missing_ok=True)

        await self.hass.async_add_executor_job(_remove)
        self._known.discard(stem)
        return True
