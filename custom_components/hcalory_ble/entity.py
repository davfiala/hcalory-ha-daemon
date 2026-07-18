"""Shared entity helpers for HCalory BLE."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import HCaloryCoordinator


def normalize_unique_id(value: str) -> str:
    """Normalize a stable config-entry id for entity unique ids."""
    return (
        value.lower()
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace(" ", "_")
    )


class HCaloryEntity(CoordinatorEntity[HCaloryCoordinator]):
    """Base class for all HCalory entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HCaloryCoordinator, unique_base: str, suffix: str, name: str) -> None:
        super().__init__(coordinator)
        device_id = normalize_unique_id(unique_base)
        self._attr_name = name
        self._attr_unique_id = f"{device_id}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=NAME,
            manufacturer="HCalory",
            model="Bluetooth diesel heater",
        )

    @property
    def data(self) -> dict:
        """Return latest coordinator data."""
        return self.coordinator.data or {}
