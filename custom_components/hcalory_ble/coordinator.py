"""Coordinator for HCalory BLE daemon data."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import NAME
from .daemon_client import DaemonClient

_LOGGER = logging.getLogger(__name__)


class HCaloryCoordinator(DataUpdateCoordinator[dict]):
    """Fetch merged status from the HCalory daemon."""

    def __init__(self, hass: HomeAssistant, client: DaemonClient, interval: float) -> None:
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            name=NAME,
            update_interval=timedelta(seconds=interval),
        )

    async def _async_update_data(self) -> dict:
        try:
            return await self.client.get_status(force=False, timeout=3.0)
        except Exception as err:
            raise UpdateFailed(err) from err
