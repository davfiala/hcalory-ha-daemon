"""Config flow for HCalory BLE."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_POLL_INTERVAL, DEFAULT_SOCKET_DIR, DOMAIN, socket_path_for_address
from .daemon_client import DaemonClient


async def _test_connection(hass: HomeAssistant, socket_path: str) -> None:
    """Verify that the daemon socket responds."""
    client = DaemonClient(socket_path)
    await client.get_daemon_status(timeout=2.0)


class HCaloryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HCalory BLE."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return HCaloryOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input.get("address", "").strip()
            socket_path = user_input.get("socket_path", "").strip()
            poll_interval = float(user_input.get("poll_interval", DEFAULT_POLL_INTERVAL))

            if not socket_path and address:
                socket_path = socket_path_for_address(address)

            if not socket_path:
                errors["base"] = "missing_socket"
            else:
                try:
                    await _test_connection(self.hass, socket_path)
                except Exception:
                    errors["base"] = "cannot_connect"

            if not errors:
                await self.async_set_unique_id(address.lower() if address else socket_path)
                self._abort_if_unique_id_configured()
                title = f"HCalory {address}" if address else "HCalory Heater"
                return self.async_create_entry(
                    title=title,
                    data={
                        "address": address,
                        "socket_path": socket_path,
                    },
                    options={"poll_interval": poll_interval},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional("address", default=""): str,
                    vol.Optional("socket_path", default=""): str,
                    vol.Optional("poll_interval", default=DEFAULT_POLL_INTERVAL): vol.Coerce(float),
                }
            ),
            errors=errors,
            description_placeholders={"default_socket_dir": DEFAULT_SOCKET_DIR},
        )


class HCaloryOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle HCalory BLE options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={"poll_interval": float(user_input["poll_interval"])},
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "poll_interval",
                        default=self.config_entry.options.get("poll_interval", DEFAULT_POLL_INTERVAL),
                    ): vol.Coerce(float),
                }
            ),
        )
