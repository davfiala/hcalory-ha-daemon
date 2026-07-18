"""Binary sensor entities for HCalory BLE."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .coordinator import HCaloryCoordinator
from .entity import HCaloryEntity


@dataclass(frozen=True, kw_only=True)
class HCaloryBinarySensorDescription(BinarySensorEntityDescription):
    """Description for an HCalory binary sensor."""

    source_key: str | None = None
    expected_value: object | None = None


BINARY_SENSORS: tuple[HCaloryBinarySensorDescription, ...] = (
    HCaloryBinarySensorDescription(key="daemon_online", source_key="daemon_status", expected_value="running", name="Service online", device_class=BinarySensorDeviceClass.CONNECTIVITY),
    HCaloryBinarySensorDescription(key="heater_connected", source_key="connected", name="BLE connected", device_class=BinarySensorDeviceClass.CONNECTIVITY),
    HCaloryBinarySensorDescription(key="heater_connecting", source_key="connecting", name="BLE connecting", icon="mdi:bluetooth-transfer", entity_category=EntityCategory.DIAGNOSTIC),
    HCaloryBinarySensorDescription(key="data_ok", source_key="data_status", expected_value="ok", name="Data OK", device_class=BinarySensorDeviceClass.CONNECTIVITY),
    HCaloryBinarySensorDescription(key="running", name="Running", device_class=BinarySensorDeviceClass.RUNNING),
    HCaloryBinarySensorDescription(key="cooldown", name="Cooldown", icon="mdi:fan"),
    HCaloryBinarySensorDescription(key="preheating", name="Preheating", icon="mdi:fire-alert"),
    HCaloryBinarySensorDescription(key="highland_mode", name="Highland mode", icon="mdi:image-filter-hdr"),
    HCaloryBinarySensorDescription(key="auto_start_stop", name="Auto Start/Stop", icon="mdi:autorenew", entity_category=EntityCategory.DIAGNOSTIC),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up HCalory binary sensors."""
    coordinator: HCaloryCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    unique_base = entry.unique_id or entry.entry_id
    async_add_entities(HCaloryBinarySensor(coordinator, unique_base, description) for description in BINARY_SENSORS)


class HCaloryBinarySensor(HCaloryEntity, BinarySensorEntity):
    """Binary sensor backed by daemon status data."""

    entity_description: HCaloryBinarySensorDescription

    def __init__(
        self,
        coordinator: HCaloryCoordinator,
        unique_base: str,
        description: HCaloryBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, unique_base, f"binary_sensor_{description.key}", description.name or description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        key = self.entity_description.source_key or self.entity_description.key
        value = self.data.get(key)
        if value is None:
            return None
        if self.entity_description.expected_value is not None:
            return value == self.entity_description.expected_value
        return bool(value)
