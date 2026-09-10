First release of the HomeBasket integration.

Scan a barcode and the product lands on your Home Assistant shopping list.
HomeBasket keeps a local `barcode → product` dictionary; a code it does not
know is looked up on Open Food Facts and remembered, so the second scan of the
same product is instant and works offline.

### What's in it

- Config flow: pick the to-do list, the lookup language, and which scanner
  events to listen for
- Actions: `scan`, `add_mapping`, `remove_mapping`, `lookup`, `import_mappings`
- Product names, brands, categories and images from Open Food Facts
- Photos you take or upload yourself, kept in Home Assistant's own storage and
  served only over the authenticated WebSocket API
- Duplicate protection — an item already on the list is not added twice
- Codes that stay unidentified wait to be named instead of putting a raw
  number on the shopping list
- `sensor.homebasket_last_scan` and `sensor.homebasket_known_products`
- REST endpoint `POST /api/homebasket/scan` and the `barcode_scanned` event for
  hardware scanners
- English and Bulgarian translations

### Requirements

Home Assistant 2025.1 or newer. The dashboard card is a separate download:
[HomeBasket-Card](https://github.com/ivan1mihaylov/HomeBasket-Card).

### Migrating from another barcode integration

```yaml
action: homebasket.import_mappings
data:
  path: /config/custom_components/beepbasket/barcode_cache.json
```
