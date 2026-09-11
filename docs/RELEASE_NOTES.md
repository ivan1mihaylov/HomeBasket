**The integration carries its own icon now.** The basket travels inside the
integration, in `custom_components/homebasket/brand/`, so Home Assistant shows
it on the integrations page, in the add dialog and on the device page rather
than a blank placeholder.

Home Assistant 2026.3 and later serve brand images straight from a custom
integration and prefer them over the central brands repository, so nothing had
to be submitted anywhere. Older versions ignore the files and lose nothing.
