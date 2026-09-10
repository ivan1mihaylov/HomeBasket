Supports the reworked photo control in
[HomeBasket-Card](https://github.com/ivan1mihaylov/HomeBasket-Card) 0.3.0.

Saving a product can now clear a field rather than only set it, so removing a
picture in the card actually removes it. A field the card does not send keeps
whatever it had, so nothing changes for existing automations or for
`homebasket.add_mapping`.

Upgrade both parts together: the card's ✕ on a photo needs this version to
take effect.
