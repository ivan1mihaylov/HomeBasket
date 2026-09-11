**Scanning with the camera now works on an iPhone.**

Safari has no barcode reader of its own, so until now the cards could only
scan there if you found a ZXing build, hosted it yourself and pointed the card
at it with `zxing_url`. A reader is shipped with the integration now and served
from your own installation at `/homebasket/zxing.min.js`. The cards load it
only when the browser has none of its own — Chrome, Edge and the Android
Companion app never touch it — and nothing is ever fetched from a CDN.

`zxing_url` still works, for a build of your own.

Needs HomeBasket Card 0.9.4.
