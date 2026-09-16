"""Media player platform for DAB Radio.

Exposes one media_player entity representing the tuner. Selecting a source
(or calling play_media with a station label/sid) tunes the shared receiver --
there's only one dongle, so this isn't "this speaker plays station X", it's
"the receiver is now on station X", with media_content_id set to welle-cli's
stream URL so the frontend (or media_player.play_media targeting a real
speaker) can actually fetch and play the audio.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DabRadioCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DabRadioCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DabRadioMediaPlayer(coordinator, entry.entry_id)])


class DabRadioMediaPlayer(CoordinatorEntity[DabRadioCoordinator], MediaPlayerEntity):
    _attr_has_entity_name = True
    _attr_name = "DAB Radio"
    _attr_supported_features = MediaPlayerEntityFeature.SELECT_SOURCE | MediaPlayerEntityFeature.PLAY_MEDIA
    _attr_media_content_type = MediaType.MUSIC
    # RECEIVER (not the default/unset) so HA's HomeKit Bridge exposes this as
    # a proper Television/Remote-style accessory with a real source picker,
    # instead of falling back to a plain "series of switches" -- HomeKit
    # only does that upgrade for TV/RECEIVER/PROJECTOR device classes (see
    # homeassistant/components/homekit/accessories.py). RECEIVER fits a
    # radio tuner better than TV semantically, and both hit the same richer
    # accessory path.
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER

    def __init__(self, coordinator: DabRadioCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_tuner"

    @property
    def _current_station(self) -> dict[str, Any] | None:
        return self.coordinator.data.get("status", {}).get("current_station")

    @property
    def source_list(self) -> list[str]:
        seen: set[str] = set()
        labels: list[str] = []
        for st in self.coordinator.data.get("stations", []):
            label = st.get("label")
            if label and label not in seen:
                seen.add(label)
                labels.append(label)
        return sorted(labels)

    @property
    def source(self) -> str | None:
        station = self._current_station
        return station.get("label") if station else None

    @property
    def state(self) -> MediaPlayerState:
        return MediaPlayerState.PLAYING if self._current_station else MediaPlayerState.IDLE

    @property
    def media_title(self) -> str | None:
        return self.source

    @property
    def media_content_id(self) -> str | None:
        station = self._current_station
        return station.get("stream_url") if station else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self.coordinator.data.get("status", {})
        return {
            "current_channel": status.get("current_channel"),
            "welle_running": status.get("welle_running"),
            "scanning": status.get("scanning"),
        }

    async def async_select_source(self, source: str) -> None:
        await self.coordinator.async_tune(source)
        await self.coordinator.async_request_refresh()

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        await self.coordinator.async_tune(media_id)
        await self.coordinator.async_request_refresh()
