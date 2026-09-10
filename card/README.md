# HomeBasket Card

The dashboard card for the [HomeBasket](https://github.com/ivan1mihaylov/HomeBasket)
Home Assistant integration. Scan a barcode with your phone camera, or type it
in, and the product goes onto your shopping list.

<p>
  <img src="docs/card.png" alt="The card in the light theme" width="45%">
  <img src="docs/card-dark.png" alt="The card in the dark theme" width="45%">
</p>

The card is written against plain DOM APIs on purpose. It uses **no Home
Assistant frontend internals** — no `ha-textfield`, no `ha-dialog`, no Lit — so
a rename inside the Home Assistant frontend cannot leave you with an invisible
input field or a missing button. It ships as a single file, so there are no
sub-modules that can get stuck in a browser cache.

## Requirements

The [HomeBasket integration](https://github.com/ivan1mihaylov/HomeBasket) has
to be installed and configured first — the card talks to it over the Home
Assistant WebSocket API.

## Installation

### HACS (custom repository)

1. HACS → ⋮ → **Custom repositories**
2. URL `https://github.com/ivan1mihaylov/HomeBasket-card`, type **Dashboard**
3. Install **HomeBasket Card**
4. Add the card to a dashboard: **Add card → HomeBasket**

### Manual

Copy `dist/homebasket-card.js` to `config/www/homebasket/homebasket-card.js`
and register it under **Settings → Dashboards → Resources**:

```
URL:  /local/homebasket/homebasket-card.js?v=0.1.0
Type: JavaScript Module
```

Bump the `?v=` value whenever you edit the file, otherwise the browser and the
companion app will keep serving the cached copy.

## Configuration

```yaml
type: custom:homebasket-card
title: Shopping
```

| Option | Default | Description |
| --- | --- | --- |
| `title` | `HomeBasket` | Card heading. |
| `add_on_scan` | `true` | Put recognised products on the shopping list immediately. Turn off to only build the product dictionary. |
| `show_table` | `true` | Show the table of learned products. |
| `show_pending` | `true` | Show codes that are waiting for a name. |
| `zxing_url` | `null` | Only for browsers without a built-in barcode detector — see below. |

All options are also editable in the visual card editor.

## How a scan flows

```
        type or scan a barcode
                  │
                  ▼
        known ──yes──▶ product name ──▶ shopping list
          │ no
          ▼
   Open Food Facts ──found──▶ remembered ──▶ shopping list
          │ not found
          ▼
   the card asks you for a name, then remembers it
```

The second scan of the same product never asks again — it goes straight to the
list, offline.

## Camera support

The camera uses the browser's built-in `BarcodeDetector`, which is available in
Chrome, Edge and the **Android** Home Assistant Companion app. Two things are
required for it to work at all:

- an **HTTPS** connection (Nabu Casa, a reverse proxy, or a local certificate);
- camera permission for Home Assistant.

**Safari and iOS** have no `BarcodeDetector`. You can either type the code in,
use a hardware scanner, or point the card at a ZXing build you host yourself:

```yaml
type: custom:homebasket-card
zxing_url: /local/homebasket/zxing.min.js
```

Nothing is loaded from a third party unless you set that option.

## License

[MIT](LICENSE)
