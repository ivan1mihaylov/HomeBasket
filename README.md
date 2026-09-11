# HomeBasket

Scan a barcode, get the product on your Home Assistant shopping list.

HomeBasket keeps a local dictionary of `barcode → product name`. When a code it
does not know shows up, it asks the whole Open Food Facts family — then
remembers the answer, so the second scan of the same product is instant and
offline.

| Asked in order | Knows | Kind |
| --- | --- | --- |
| [Open Food Facts](https://world.openfoodfacts.org/) | groceries | `food` |
| [Open Beauty Facts](https://world.openbeautyfacts.org/) | cosmetics | `beauty` |
| [Open Pet Food Facts](https://world.openpetfoodfacts.org/) | what the cat eats | `petfood` |
| [Open Products Facts](https://world.openproductsfacts.org/) | everything else | `product` |

Which one knew the barcode is what a product turns out to be: it carries that as
its **kind**, and the card shows each one the fields it actually has —
Nutri-Score and nutrition for a yoghurt, ingredients for a shampoo, origin and
packaging for a lamp. A re-lookup goes straight back to the database that knew
it. A product learned before kinds existed gets one the next time it is
scanned, once, and keeps it.

```
        scan
          │
          ▼
   known barcode? ──yes──▶ product name ─┐
          │ no                           │
          ▼                              │
   the Open Food Facts ──found──▶ remember ┤
   family, in turn                        │
          │ not found                    │
          ▼                              ▼
   waits in the card            shopping list  ──▶  ✅
   until you name it      (a to-do entity, or a HomeBasket
                           Lists list that counts repeats)
```

The dashboard card lives in a separate repository:
[**HomeBasket-Card**](https://github.com/ivan1mihaylov/HomeBasket-Card).

## The three parts

| | What it is |
| --- | --- |
| **HomeBasket** | Scanning, and the products it learns: names, barcodes, pictures, everything the databases know. Everything else reads from here. |
| **[HomeBasket Card](https://github.com/ivan1mihaylov/HomeBasket-Card)** | Scanning with a phone, for when there is no scanner on a shelf — and the place to look after the products themselves. |
| **[HomeBasket Lists](https://github.com/ivan1mihaylov/HomeBasket-Lists)** | Shopping lists and tasks, using what HomeBasket knows. |

A scan is a scan wherever it is made — the card, a hardware scanner, the button
on a list — and it lands in the same place: the product is remembered here, and
it shows in the card's recent scans either way.

## Languages

The integration's own interface — setup, options and the names of its entities
— is translated into **Bulgarian** and **English**, and follows the language of
the person using Home Assistant. Anything else falls back to English.

Product names are a separate matter: **Preferred product name language** in the
settings is the language asked of Open Food Facts (`bg`, `en`, `de`, …), and it
falls back to the international name when that language has none. Names you
type in yourself are kept exactly as typed, in any language.

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
| **Shopping list** | The `todo.*` entity scanned products are added to. Can be left empty when a HomeBasket Lists list is chosen instead. |
| **HomeBasket Lists list** | Only shown when [HomeBasket Lists](https://github.com/ivan1mihaylov/HomeBasket-Lists) is installed: scans go on that list instead of the to-do entity. |
| **Look unknown barcodes up on Open Food Facts** | Off runs fully offline. On, a barcode is looked for in all four databases above, in that order. |
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
| `homebasket.get_product` | Return one product, optionally with its Open Food Facts record. Changes nothing. |
| `homebasket.get_products` | Return every product, narrowed by `query` or `category`. Changes nothing. |

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
  name: Fresh milk
  category: Dairy
```

## With HomeBasket Lists

HomeBasket works on its own, and so does
[HomeBasket Lists](https://github.com/ivan1mihaylov/HomeBasket-Lists) — neither
needs the other installed. When both are there, a scan goes on a HomeBasket
Lists list rather than a to-do entity, and **scanning the same product again
counts one more of it** instead of repeating the line: two bottles of milk
become *milk, 2 pcs*. That is the list's own setting, so a list can be told to
keep what it has or to write a second line instead; HomeBasket reports whichever
happened in `added`, `increased` and `already_on_list`.

The list is picked in HomeBasket's settings. With exactly one list and nothing
chosen, that one is used. With several and none chosen, the to-do entity is
used, so nothing changes behind your back. If HomeBasket Lists is removed, or
is an older version without the door to write through, scans fall back to the
to-do entity by themselves.

## Products without a barcode

Not everything you buy has a barcode you ever scan — bread from the bakery,
tomatoes, a line someone typed on a shopping list. HomeBasket keeps those too,
under a key of its own rather than a barcode, and the card shows them as **No
barcode**.

They arrive on their own: whenever something to buy is configured on a
HomeBasket Lists list — its name, its picture, the kind of shop it comes from —
the list hands it over, so the next time you start typing that name anywhere,
it is offered with everything it already knows. Renaming it there renames it
here; products a database named are left alone.

A product's sheet has a field to **attach a barcode by hand**. Type one in and
it belongs to that product from then on, so scanning it finds the name, the
picture and the shop you already set — and it is the same product, not a second
one.

## Which shop a product is bought in

Every product belongs to a kind of shop, because that is what decides where it
is worth reminding you about it. There are eight:

| Category | Where a scan puts it |
| --- | --- |
| Groceries | everything Open Food Facts and Open Products Facts know |
| Bakery | — |
| Greengrocer | — |
| Butcher | — |
| Cosmetics | everything Open Beauty Facts knows |
| Medicines | — |
| Pet shop | everything Open Pet Food Facts knows |
| Building supplies | — |

The database that knew the barcode decides where a product starts; the ones
with no default are for the things you add yourself. Any product can be moved
afterwards in its sheet in the card, and it stays where it is put however often
it is looked up again.

A shopping list uses this to decide where to remind you: HomeBasket Lists takes
each category and the zones it is worth a reminder in, so the butcher's is not
where you are told about shampoo.

## Scanning on an iPhone

Chrome, Edge and the Android Companion app read barcodes themselves. Safari —
and therefore every iPhone — cannot, so a reader is shipped with this
integration and served from your own installation at
`/homebasket/zxing.min.js`. The cards load it only when the browser has no
reader of its own, so nothing is ever fetched from a CDN and there is nothing
to set up. Both cards take a `zxing_url` option for a build of your own.

The reader is [zxing-js/library](https://github.com/zxing-js/library); its
licence travels with it in `custom_components/homebasket/frontend/`.

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
| `homebasket_scanned` | A code was processed. Payload: `code`, `product_code`, `name`, `brand`, `category`, `image`, `status`, `added`, `increased`, `already_on_list`, `quantity`, `list`, `source`, `timestamp`. |
| `homebasket_updated` | The dictionary changed; the card refreshes on this. |

`status` is `known`, `looked_up` or `unknown`. `added` means a new line on the
shopping list, `increased` that the count of one already there went up (a
HomeBasket Lists list can do that), `already_on_list` that it was left alone;
`list` says where it went.

## Migrating an existing barcode dictionary

If you have been using another barcode integration, import its cache once:

```yaml
action: homebasket.import_mappings
data:
  path: /config/custom_components/beepbasket/barcode_cache.json
```

Both `{"3800...": "Milk"}` and `{"3800...": {"name": "Milk"}}` shapes are
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

## Recent scans

The last few scans are kept by the integration, not by whatever did the
scanning, so the card shows a scan made anywhere: on the phone, by a hardware
scanner, or by the scan button on a HomeBasket Lists list. Dismissing one from
the card takes it off that list; the product itself stays.

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
| `products` | Every product: `code`, `name`, `brand`, `category`, `image`, `kind`, `source`, `scan_count`, `has_photo`. |
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
python3 tests/test_store.py          # what a barcode resolves to
python3 tests/test_lookup.py         # which database a barcode is looked for in
python3 tests/test_shopping_list.py  # where a scanned product ends up
```

The first covers the same label read as UPC-A and as EAN-13. The second walks a
scan onto a to-do list, onto a HomeBasket Lists list, and through every way
HomeBasket Lists can be missing, old or broken.

## Credits

HomeBasket is an independent implementation, written from scratch. The idea of
beeping barcodes straight into a Home Assistant shopping list comes from
[BeepBasket](https://github.com/meijerwynand/beepbasket) by Wynand Meijer — no
code from that project is used here.

Product data comes from [Open Food Facts](https://world.openfoodfacts.org/),
an open database licensed under ODbL.

## License

[MIT](LICENSE)
