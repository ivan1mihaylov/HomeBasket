"""Sensors exposing the HomeBasket state."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_UPDATED, VERSION
from .manager import HomeBasketManager


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the HomeBasket sensors."""
    manager: HomeBasketManager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [HomeBasketLastScanSensor(manager, entry), HomeBasketProductsSensor(manager, entry)]
    )


class HomeBasketEntity(SensorEntity):
    """Common base for the HomeBasket sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: HomeBasketManager, entry: ConfigEntry) -> None:
        """Initialise the entity."""
        self._manager = manager
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="HomeBasket",
            manufacturer="HomeBasket",
            entry_type=DeviceEntryType.SERVICE,
            sw_version=VERSION,
        )

    async def async_added_to_hass(self) -> None:
        """Refresh whenever the manager reports a change."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATED, self._handle_update)
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class HomeBasketLastScanSensor(HomeBasketEntity):
    """The most recently scanned barcode."""

    _attr_translation_key = "last_scan"
    _attr_icon = "mdi:barcode-scan"

    def __init__(self, manager: HomeBasketManager, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_scan"

    @property
    def native_value(self) -> str | None:
        """Return the last scanned code."""
        if not (scan := self._manager.last_scan):
            return None
        return scan.get("code")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the details of the last scan."""
        scan = self._manager.last_scan or {}
        return {
            "product": scan.get("name"),
            "brand": scan.get("brand"),
            "image": scan.get("image"),
            "status": scan.get("status"),
            "added_to_list": scan.get("added"),
            "already_on_list": scan.get("already_on_list"),
            "scan_source": scan.get("source"),
            "timestamp": scan.get("timestamp"),
        }


class HomeBasketProductsSensor(HomeBasketEntity):
    """How many products HomeBasket has learned."""

    _attr_translation_key = "known_products"
    _attr_icon = "mdi:database"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "products"

    def __init__(self, manager: HomeBasketManager, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_known_products"

    @property
    def native_value(self) -> int:
        """Return the number of known mappings."""
        return len(self._manager.store.mappings)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the pending, unidentified codes."""
        return {
            "unidentified": len(self._manager.store.pending),
            "unidentified_codes": list(self._manager.store.pending),
        }
