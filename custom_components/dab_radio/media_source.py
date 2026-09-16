"""Expose DAB Radio stations as a browsable media source.

Lets stations show up in Home Assistant's Media Browser panel (the same
place Radio Browser, Plex, local media etc. live), so you can browse
DAB Radio -> a channel -> a station and hit "Play on" a real speaker
directly, instead of going through the dab_radio media_player entity's
own select_source UI.

Resolving a station (picking "Play") retunes the shared receiver, the same
as media_player.dab_radio's select_source/play_media does -- there's one
dongle behind all of this, so "playing" a station here means "the receiver
is now on this station", same as anywhere else in this integration.
"""
from __future__ import annotations

from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant

from . import DabRadioCoordinator
from .const import DOMAIN

# The add-on always serves stations as MP3 (see ha-dab-addon's controller.py --
# output codec is a fixed add-on-wide welle-cli setting, not per-station), so
# this can be a constant rather than something resolved per station.
MIME_TYPE = "audio/mpeg"


async def async_get_media_source(hass: HomeAssistant) -> DabRadioMediaSource:
    """Set up the DAB Radio media source."""
    # Only one dongle, only one config entry is supported (see manifest.json's
    # single_config_entry) -- safe to grab the first/only one.
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator: DabRadioCoordinator = hass.data[DOMAIN][entry.entry_id]
    return DabRadioMediaSource(coordinator)


class DabRadioMediaSource(MediaSource):
    """Provide DAB stations, grouped by channel, as browsable media."""

    name = "DAB Radio"

    def __init__(self, coordinator: DabRadioCoordinator) -> None:
        super().__init__(DOMAIN)
        self.coordinator = coordinator

    def _stations(self) -> list[dict]:
        return self.coordinator.data.get("stations", [])

    def _channels(self) -> dict[str, list[dict]]:
        channels: dict[str, list[dict]] = {}
        for station in self._stations():
            channels.setdefault(station["channel"], []).append(station)
        return channels

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a station identifier to a stream URL, tuning the receiver to it."""
        channel, _, sid = (item.identifier or "").partition("/")
        station = next(
            (s for s in self._stations() if s["channel"] == channel and s["sid"] == sid),
            None,
        )
        if station is None:
            raise Unresolvable(f"Unknown DAB station: {item.identifier}")

        data = await self.coordinator.async_tune(station["sid"])
        await self.coordinator.async_request_refresh()
        return PlayMedia(data["tuned"]["stream_url"], MIME_TYPE)

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return the browsable DAB Radio tree: root -> channel -> station."""
        channels = self._channels()

        if item.identifier:
            stations = channels.get(item.identifier, [])
            # Group title is the ensemble name only -- the underlying DAB
            # channel/multiplex code (e.g. "10B") is internal plumbing the
            # identifier still carries, not something to surface in the UI.
            title = stations[0]["ensemble"] if stations else "DAB Radio"
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=item.identifier,
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.MUSIC,
                title=title,
                can_play=False,
                can_expand=True,
                children=[
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"{station['channel']}/{station['sid']}",
                        media_class=MediaClass.MUSIC,
                        media_content_type=MIME_TYPE,
                        title=station["label"],
                        can_play=True,
                        can_expand=False,
                    )
                    for station in stations
                ],
            )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.MUSIC,
            title="DAB Radio",
            can_play=False,
            can_expand=True,
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=channel,
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title=stations[0]["ensemble"],
                    can_play=False,
                    can_expand=True,
                )
                for channel, stations in channels.items()
                if stations
            ],
        )
