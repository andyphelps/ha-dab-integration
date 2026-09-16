"""Config flow for DAB Radio."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_HOST, CONF_PORT, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class CannotConnect(Exception):
    """Could not reach the DAB Radio add-on's controller API."""


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> str:
    session = async_get_clientsession(hass)
    url = f"http://{data[CONF_HOST]}:{data[CONF_PORT]}/health"
    try:
        async with asyncio.timeout(10):
            resp = await session.get(url)
            if resp.status != 200:
                raise CannotConnect
            body = await resp.json()
            if not body.get("ok"):
                raise CannotConnect
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        raise CannotConnect from err

    return f"DAB Radio ({data[CONF_HOST]})"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DAB Radio."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]})
            try:
                title = await _validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors)
