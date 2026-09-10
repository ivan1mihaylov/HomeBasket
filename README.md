# HomeBasket

Scan a barcode, get the product on your Home Assistant shopping list.

HomeBasket keeps a local dictionary of `barcode → product name`. When a code it
does not know shows up, it asks [Open Food Facts](https://world.openfoodfacts.org/)
and remembers the answer, so the second scan of the same product is instant and
offline.

```
        scan
          │
          ▼
   known barcode? ──yes──▶ product name ─┐
          │ no                           │
          ▼                              │
   Open Food Facts ──found──▶ remember ──┤
          │ not found                    │
          ▼                              ▼
   waits in the card          todo.add_item  ──▶  ✅ shopping list
   until you name it          (duplicates skipped)
```

The dashboard card lives in a separate repository:
[**HomeBasket-Card**](https://github.com/ivan1mihaylov/HomeBasket-Card).

## Installation

### HACS (custom repository)

1. HACS → ⋮ → **Custom repositories**
2. URL `https://github.com/ivan1mihaylov/HomeBasket`, type **Integration**
3. Install **HomeBasket**, then restart Home Assistant
4. **Settings → Devices & Services → Add Integration → HomeBasket**

### Manual

Copy `custom_components/homebasket` into your `config/custom_components/` folder
and restart Home Assistant.

## Configuration

Everything is configured in the UI, and can be changed later through
**Configure** on the integration entry.

| Option | Meaning |
| --- | --- |
| **Shopping list** | The `todo.*` entity scanned products are added to. |
| **Look unknown barcodes up on Open Food Facts** | Turn off to run fully offline. |
| **Add unidentified barcodes to the list as-is** | Off by default; unidentified codes wait in the card instead of putting a raw number on your list. |
| **Preferred product name language** | Two letter code, e.g. `bg`. Falls back to the international name. |
| **Scanner events to listen for** | Comma separated. Default `barcode_scanned`. |

## Entities

| Entity | Description |
| --- | --- |
| `sensor.homebasket_last_scan` | The last scanned code, with the resolved product, status and whether it was added as attributes. |
| `sensor.homebasket_known_products` | How many products HomeBasket has learned, plus the codes still waiting for a name. |

## Actions

| Action | What it does |
| --- | --- |
| `homebasket.scan` | Full pipeline: resolve the code and add it to the list. |
| `homebasket.add_mapping` | Teach HomeBasket a `barcode → product` pair, optionally with a category. |
| `homebasket.remove_mapping` | Forget a barcode. |
| `homebasket.lookup` | Query Open Food Facts without changing anything. |
| `homebasket.import_mappings` | Import a JSON barcode dictionary (see below). |

All actions accept both `code` and the older `barcode` spelling, and
`add_mapping` accepts `name`, `product` or `product_name`.

```yaml
action: homebasket.scan
data:
  code: "3800123456789"
```

```yaml
action: homebasket.add_mapping
data:
  code: "3800123456789"
  name: Прясно мляко
  category: Млечни продукти
```

## Hardware scanners

Any scanner that can fire a Home Assistant event works. Fire
`barcode_scanned` with the code in one of `barcode`, `code`, `tag_id`, `text`
or `value`:

```yaml
automation:
  - triggers:
      - trigger: event
        event_type: esphome.barcode
    actions:
      - action: homebasket.scan
        data:
          code: "{{ trigger.event.data.barcode }}"
```

Or POST straight to the REST endpoint with a long-lived access token:

```bash
curl -X POST https://your-ha/api/homebasket/scan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"code": "3800123456789"}'
```

## Events

| Event | Fired when |
| --- | --- |
| `homebasket_scanned` | A code was processed. Payload: `code`, `name`, `brand`, `category`, `image`, `status`, `added`, `already_on_list`, `source`, `timestamp`. |
| `homebasket_updated` | The dictionary changed; the card refreshes on this. |

`status` is `known`, `looked_up` or `unknown`.

## Migrating an existing barcode dictionary

If you have been using another barcode integration, import its cache once:

```yaml
action: homebasket.import_mappings
data:
  path: /config/custom_components/beepbasket/barcode_cache.json
```

Both `{"3800...": "Мляко"}` and `{"3800...": {"name": "Мляко"}}` shapes are
understood, and existing HomeBasket entries are kept unless you pass
`overwrite: true`.

## More than one barcode per product

A product is stored under the barcode it was first scanned with. Any further
barcode for the same product is stored as a pointer to that one, so the same
yoghurt in two pack sizes is one product with two codes.

Every barcode of a product resolves to it: scanning, editing, `get_product`
and the API all accept any of them. `codes` on a product lists them all, and
`code` is the first. Deleting a product takes its other barcodes, its photo and
its cached records with it.

The card links and unlinks barcodes; from Python it is
`await api.async_link_code(code, product)`.

One physical label can also be reported two ways: a UPC-A barcode is twelve
digits, and the very same label read as EAN-13 comes back with a leading zero.
Which one you get depends on the scanner, so both readings resolve to the same
product — scanning something you already have opens it instead of creating a
second copy of it.

## Product details

Everything Open Food Facts returns for a barcode — scores, nutrition,
ingredients, allergens, labels, packaging, origin, stores — is stored the first
time the code is looked up, so the card can show it without going back to the
network. Only an explicit re-lookup (`homebasket.lookup`, or **Look up again**
in the card) refreshes that copy.

The cache lives in `.storage/homebasket.details` and is loaded the first time
something reads it rather than at startup, so it costs nothing until a product
is opened. Forgetting a product drops its record.

## Product photos

Open Food Facts usually supplies a product image, and HomeBasket stores its URL
alongside the name. For anything it does not cover — loose produce, a local
bakery, a own-brand item — the dashboard card can take or upload a photo.

Those photos are kept in Home Assistant's own storage
(`.storage/homebasket_images/`) and are read back over the authenticated
WebSocket API, so they are never exposed on a public path the way files in
`www/` are. Forgetting a product deletes its photo with it.

## Using HomeBasket from another integration

HomeBasket publishes what it knows so other custom integrations, scripts and
external tools can build on it. There are three ways in, all returning the same
product shape.

### From Python

A custom integration reads the object HomeBasket puts in `hass.data`. Do not
reach into `hass.data["homebasket"]` — that holds internals that will change.

```python
api = hass.data.get("homebasket_api")
if api is None:
    return  # HomeBasket is not installed or not set up yet

for product in api.products:
    print(product["code"], product["name"], product["category"])

milk = api.get("3800123456789")
details = await api.async_get_details("3800123456789")   # cached, no network
photo = await api.async_get_photo("3800123456789")       # data URL, or None
```

| Member | Returns |
| --- | --- |
| `api_version` | `1` today. Check it before relying on the shape. |
| `products` | Every product: `code`, `name`, `brand`, `category`, `image`, `source`, `scan_count`, `has_photo`. |
| `pending` | Scanned codes that could not be identified. |
| `get(code)` | One product, or `None`. |
| `find(text)` | Products matching a name, brand, category or code. |
| `await async_get_details(code, refresh=False)` | The full Open Food Facts record from the cache; `refresh=True` re-queries. |
| `await async_get_photo(code)` | A user photo as a data URL, or `None`. `image` on a product is a remote URL and needs no call. |
| `await async_resolve(code, add_to_list=False)` | Run a barcode through the scan pipeline. |
| `await async_shopping_list()` | The open items on the configured list. |
| `todo_entity`, `language` | The current configuration. |

Everything returned is a copy, so a consumer cannot corrupt the stored data.
Listen for the `homebasket_updated` event to know when to re-read.

### From an automation or a script

```yaml
action: homebasket.get_product
data:
  code: "3800123456789"
  include_details: true
response_variable: result
```

`homebasket.get_products` returns them all, and takes `query` or `category` to
narrow the list. Both leave the data untouched.

### Over HTTP

```bash
curl https://your-ha/api/homebasket/product/3800123456789 \
  -H "Authorization: Bearer $TOKEN"
```

`?details=0` drops the Open Food Facts record, `?photo=1` adds the stored photo.
`/api/homebasket/mappings` returns the whole dictionary.

## Development

The barcode dictionary has a test that runs without Home Assistant:

```bash
python3 tests/test_store.py
```

It covers what a scan resolves to, including the same label read as UPC-A and
as EAN-13.

## Credits

HomeBasket is an independent implementation, written from scratch. The idea of
beeping barcodes straight into a Home Assistant shopping list comes from
[BeepBasket](https://github.com/meijerwynand/beepbasket) by Wynand Meijer — no
code from that project is used here.

Product data comes from [Open Food Facts](https://world.openfoodfacts.org/),
an open database licensed under ODbL.

## License

[MIT](LICENSE)
