Products can now carry more than one barcode, and everything Open Food Facts
knows about them is kept for the card to show.

### More than one barcode per product

The same yoghurt in a 400 g and a 900 g tub belongs on a shopping list once. A
product is stored under the barcode it was first scanned with; any further
barcode points at it. Every barcode resolves to the product, so scanning,
editing, `get_product` and the API all accept any of them — `codes` lists them
all and `code` is the first. Deleting a product takes its other barcodes, its
photo and its cached records with it.

### The full Open Food Facts record

The lookup a scan already makes now asks for everything: Nutri-Score, NOVA and
Eco-Score, nutriments, ingredients, allergens, labels, packaging, origin and
stores. It is cached in `.storage/homebasket.details`, loaded only when
something reads it, so the card's details sheet costs no network request. Only
an explicit re-lookup refreshes it.

### An interface for other integrations

`hass.data["homebasket_api"]` exposes a versioned, read-only view of the
products, their cached records and their photos, plus the scan pipeline itself.
The same data is reachable from automations through `homebasket.get_product`
and `homebasket.get_products`, and over HTTP at
`/api/homebasket/product/<code>`. Everything handed out is a copy.

### Also

- Better category picking: Open Food Facts mixes written-out names with slugs
  left over from other languages, and the slugs are now dropped rather than
  becoming a product's category
- Scores reading `unknown` or `not-applicable` are treated as absent
- A scanned code waiting to be named can be dismissed on its own, without
  removing any product
- Saving a product can clear a field rather than only set it

Pair with [HomeBasket-Card](https://github.com/ivan1mihaylov/HomeBasket-Card)
0.5.0.
