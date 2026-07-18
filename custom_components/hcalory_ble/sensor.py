"""Sensor entities for HCalory BLE."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import UnitOfElectricPotential, UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .coordinator import HCaloryCoordinator
from .entity import HCaloryEntity

HEATER_ERROR_MESSAGES = {
    1: "General error",
    2: "Low / high voltage",
    3: "Glow plug",
    4: "Fuel pump",
    5: "Overheat",
    6: "Fan",
    7: "Communication",
    8: "No fuel / flame-out",
    9: "Sensor",
    10: "Ignition failure",
}


@dataclass(frozen=True, kw_only=True)
class HCalorySensorDescription(SensorEntityDescription):
    """Description for an HCalory sensor."""

    source_key: str | None = None
    requires_data_ok: bool = False


SENSORS: tuple[HCalorySensorDescription, ...] = (
    HCalorySensorDescription(key="heater_state", name="Heater state", icon="mdi:information-outline"),
    HCalorySensorDescription(key="heater_mode", name="Heater mode", icon="mdi:tune-variant"),
    HCalorySensorDescription(key="hcalory_status", name="Protocol status", icon="mdi:state-machine", entity_category=EntityCategory.DIAGNOSTIC),
    HCalorySensorDescription(key="hcalory_running_step", name="Running step", icon="mdi:stairs", entity_category=EntityCategory.DIAGNOSTIC),
    HCalorySensorDescription(key="heater_setting", name="Heater setting", icon="mdi:tune", requires_data_ok=True),
    HCalorySensorDescription(
        key="body_temperature",
        name="Body temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        requires_data_ok=True,
    ),
    HCalorySensorDescription(
        key="ambient_temperature",
        name="Ambient temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        requires_data_ok=True,
    ),
    HCalorySensorDescription(
        key="voltage",
        source_key="voltage_v",
        name="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        requires_data_ok=True,
    ),
    HCalorySensorDescription(key="daemon_status", name="Service status", icon="mdi:server-network", entity_category=EntityCategory.DIAGNOSTIC),
    HCalorySensorDescription(key="heater_status", name="BLE status", icon="mdi:bluetooth", entity_category=EntityCategory.DIAGNOSTIC),
    HCalorySensorDescription(key="data_status", name="Data status", icon="mdi:database-check", entity_category=EntityCategory.DIAGNOSTIC),
    HCalorySensorDescription(key="protocol_version", name="Protocol version", icon="mdi:code-json", entity_category=EntityCategory.DIAGNOSTIC),
    HCalorySensorDescription(key="voltage_raw", name="Voltage raw", icon="mdi:counter", entity_category=EntityCategory.DIAGNOSTIC),
    HCalorySensorDescription(key="error_code", name="Heater error code", icon="mdi:alert-outline", entity_category=EntityCategory.DIAGNOSTIC),
    HCalorySensorDescription(key="error_message", name="Heater error", icon="mdi:alert-circle-outline", entity_category=EntityCategory.DIAGNOSTIC),
    HCalorySensorDescription(key="last_success_age", name="Last success age", native_unit_of_measurement="s", icon="mdi:timer-outline", entity_category=EntityCategory.DIAGNOSTIC),
    HCalorySensorDescription(key="retry_in", name="Retry in", native_unit_of_measurement="s", icon="mdi:timer-sand", entity_category=EntityCategory.DIAGNOSTIC),
    HCalorySensorDescription(key="consecutive_failures", name="Consecutive failures", icon="mdi:counter", entity_category=EntityCategory.DIAGNOSTIC),
    HCalorySensorDescription(key="last_error", name="Last error", icon="mdi:alert-circle-outline", entity_category=EntityCategory.DIAGNOSTIC),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up HCalory sensors."""
    coordinator: HCaloryCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    unique_base = entry.unique_id or entry.entry_id
    async_add_entities(HCalorySensor(coordinator, unique_base, description) for description in SENSORS)


class HCalorySensor(HCaloryEntity, SensorEntity):
    """Sensor backed by daemon status data."""

    entity_description: HCalorySensorDescription

    def __init__(
        self,
        coordinator: HCaloryCoordinator,
        unique_base: str,
        description: HCalorySensorDescription,
    ) -> None:
        super().__init__(coordinator, unique_base, f"sensor_{description.key}", description.name or description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        key = self.entity_description.source_key or self.entity_description.key
        if key == "error_message":
            code = self.data.get("error_code")
            if not code:
                return "None"
            return HEATER_ERROR_MESSAGES.get(int(code), f"Unknown error {code}")
        return self.data.get(key)

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        key = self.entity_description.source_key or self.entity_description.key
        if self.entity_description.requires_data_ok and self.data.get("data_status") != "ok":
            return False
        return key in self.data and self.data.get(key) is not None
