A barcode is now looked for in the whole Open Food Facts family, in this order:

| Database | Knows | Kind |
| --- | --- | --- |
| [Open Food Facts](https://world.openfoodfacts.org/) | groceries | `food` |
| [Open Beauty Facts](https://world.openbeautyfacts.org/) | cosmetics | `beauty` |
| [Open Pet Food Facts](https://world.openpetfoodfacts.org/) | what the cat eats | `petfood` |
| [Open Products Facts](https://world.openproductsfacts.org/) | everything else | `product` |

Asking stops at the first one that answers, and a re-lookup goes straight back
to the database that knew the product, so nothing walks the family twice.

Which one knew the barcode is kept on the product as its **kind**, and travels
with it: the card shows each product the fields it actually has, and a scan that
lands on a HomeBasket Lists list arrives as the right kind of item rather than
as whatever the list defaults to. A product named by hand learns its kind the
first time something looks it up, without its name or source being rewritten.
