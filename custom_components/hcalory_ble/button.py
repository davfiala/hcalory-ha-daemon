"""Button entities for HCalory BLE."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .coordinator import HCaloryCoordinator
from .daemon_client import DaemonClient
from .entity import HCaloryEntity


@dataclass(frozen=True, kw_only=True)
class HCaloryButtonDescription(ButtonEntityDescription):
    """Description for an HCalory button."""

    command: str


BUTTONS: tuple[HCaloryButtonDescription, ...] = (
    HCaloryButtonDescription(key="start_heat", name="Start heat", icon="mdi:fire", command="start_heat"),
    HCaloryButtonDescription(key="stop_heat", name="Stop heat", icon="mdi:fire-off", command="stop_heat"),
    HCaloryButtonDescription(key="up", name="Increase setting", icon="mdi:chevron-up", command="up"),
    HCaloryButtonDescription(key="down", name="Decrease setting", icon="mdi:chevron-down", command="down"),
    HCaloryButtonDescription(key="gear", name="Gear mode", icon="mdi:fire-circle", command="gear"),
    HCaloryButtonDescription(key="thermostat", name="Thermostat mode", icon="mdi:thermostat", command="thermostat"),
    HCaloryButtonDescription(key="refresh", name="Refresh data", icon="mdi:refresh", command="pump_data_force", entity_category=EntityCategory.DIAGNOSTIC),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up HCalory buttons."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: HCaloryCoordinator = data["coordinator"]
    client: DaemonClient = data["client"]
    unique_base = entry.unique_id or entry.entry_id
    async_add_entities(HCaloryButton(coordinator, client, unique_base, description) for description in BUTTONS)


class HCaloryButton(HCaloryEntity, ButtonEntity):
    """Button that sends a daemon command."""

    entity_description: HCaloryButtonDescription

    def __init__(
        self,
        coordinator: HCaloryCoordinator,
        client: DaemonClient,
        unique_base: str,
        description: HCaloryButtonDescription,
    ) -> None:
        super().__init__(coordinator, unique_base, f"button_{description.key}", description.name or description.key)
        self.entity_description = description
        self._client = client
        self._attr_should_poll = False

    async def async_press(self) -> None:
        """Send the button command."""
        if self.entity_description.command == "pump_data_force":
            await self._client.get_pump_data(force=True)
        else:
            await self._client.command(self.entity_description.command)
        await self.coordinator.async_request_refresh()
