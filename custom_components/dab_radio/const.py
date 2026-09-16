"""Constants for the DAB Radio integration."""

DOMAIN = "dab_radio"

CONF_HOST = "host"
CONF_PORT = "port"

DEFAULT_PORT = 9000

# /status and /stations are cheap calls against the add-on's own cache --
# this just polls that cache, it does NOT trigger a channel scan (that's a
# separate, explicit dab_radio.scan service, since a scan takes 30-90s).
SCAN_INTERVAL = 30
