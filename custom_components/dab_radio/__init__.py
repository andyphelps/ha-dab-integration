"""The DAB Radio integration.

Talks to the DAB Radio add-on's controller REST API (see ha-dab-addon/) --
this integration has no idea whether that API is backed by welle-cli running
in a Docker add-on against a remote rtl_tcp source, or running bare-metal
right next to the dongle. It only needs a reachable host:port.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_HOST, CONF_PORT, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["media_player"]


class DabRadioCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the add-on's cheap /status + /stations endpoints.

    Does NOT trigger a channel scan itself -- that's the separate
    dab_radio.scan service, since a scan retunes through every configured
    channel and takes 30-90s.
    """

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=SCAN_INTERVAL))
        self.base_url = f"http://{host}:{port}"
        self.session = async_get_clientsession(hass)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            async with asyncio.timeout(10):
                status_resp = await self.session.get(f"{self.base_url}/status")
                status_resp.raise_for_status()
                status = await status_resp.json()

                stations_resp = await self.session.get(f"{self.base_url}/stations")
                stations_resp.raise_for_status()
                channels = (await stations_resp.json()).get("channels", {})
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"Error talking to the DAB Radio add-on: {err}") from err

        all_stations = [st for ch_data in channels.values() for st in ch_data.get("stations", [])]
        return {"status": status, "stations": all_stations}

    async def async_tune(self, station_query: str) -> dict[str, Any]:
        try:
            async with asyncio.timeout(30):
                resp = await self.session.post(f"{self.base_url}/tune", json={"station": station_query})
                data = await resp.json()
                if resp.status != 200:
                    raise UpdateFailed(data.get("error", f"tune failed with status {resp.status}"))
                return data
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"Error tuning DAB Radio: {err}") from err

    async def async_scan(self) -> None:
        try:
            async with asyncio.timeout(10):
                resp = await self.session.post(f"{self.base_url}/scan")
                if resp.status not in (200, 409):
                    raise UpdateFailed(f"scan request failed with status {resp.status}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"Error starting DAB Radio scan: {err}") from err


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = DabRadioCoordinator(hass, entry.data[CONF_HOST], entry.data[CONF_PORT])
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _handle_scan(call: ServiceCall) -> None:
        await coordinator.async_scan()

    hass.services.async_register(DOMAIN, "scan", _handle_scan)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "scan")
    return unload_ok
