Scans can now go on a [HomeBasket Lists](https://github.com/ivan1mihaylov/HomeBasket-Lists)
list instead of a to-do entity, and **scanning the same product again counts one
more of it** rather than repeating the line: two bottles of milk become
*milk, 2 pcs*. What a repeat means is the list's own setting, so it can be told
to keep what it has or to write a second line instead; the scan result reports
which of the three happened in `added`, `increased` and `already_on_list`.

The list is chosen in HomeBasket's settings, and the field only appears when
HomeBasket Lists is installed. With exactly one list and nothing chosen, that
one is used; with several and none chosen, the to-do entity is, so nothing moves
behind your back. Neither integration needs the other: without HomeBasket Lists
— or with a version too old to be written to — scans fall back to the to-do
entity by themselves, which is also why the to-do entity is no longer required.
