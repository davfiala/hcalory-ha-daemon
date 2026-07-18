"""HCalory BLE integration using a persistent daemon socket."""

from __future__ import annotations

from pathlib import Path
import logging

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CARD_FILENAME, DEFAULT_POLL_INTERVAL, DOMAIN, PLATFORMS, STATIC_URL_PATH, socket_path_for_address
from .coordinator import HCaloryCoordinator
from .daemon_client import DaemonClient

_LOGGER = logging.getLogger(__name__)
_STATIC_REGISTERED = f"{DOMAIN}_static_registered"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HCalory BLE from a config entry."""
    if not hass.data.get(_STATIC_REGISTERED):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    STATIC_URL_PATH,
                    str(Path(__file__).parent / "static"),
                    False,
                )
            ]
        )
        hass.data[_STATIC_REGISTERED] = True

    socket_path = entry.data.get("socket_path")
    if not socket_path and entry.data.get("address"):
        socket_path = socket_path_for_address(entry.data["address"])

    if not socket_path:
        _LOGGER.error("No daemon socket path configured")
        return False

    client = DaemonClient(socket_path)
    interval = float(entry.options.get("poll_interval", DEFAULT_POLL_INTERVAL))
    coordinator = HCaloryCoordinator(hass, client, interval)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.warning("Initial refresh failed: %s", err)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("HCalory card resource available at %s/%s", STATIC_URL_PATH, CARD_FILENAME)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
