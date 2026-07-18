"""Switch entities for HCalory BLE."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Callable

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import HCaloryCoordinator
from .daemon_client import DaemonClient
from .entity import HCaloryEntity

_LOGGER = logging.getLogger(__name__)

AUTO_TARGET_ENTITY_ID = "input_number.hcalory_target_temperature"
AUTO_HYSTERESIS_ENTITY_ID = "input_number.hcalory_hysteresis"


StateFn = Callable[[dict], bool | None]

MODE_OFF = "off"
MODE_HEATING = "heating"
MODE_AUTO = "auto"
MODE_VENTILATION = "ventilation"


@dataclass(frozen=True, kw_only=True)
class HCalorySwitchDescription(SwitchEntityDescription):
    """Description for an HCalory switch."""

    on_command: str
    off_command: str | None = None
    state_fn: StateFn
    control_mode: str | None = None


def _power_state(data: dict) -> bool | None:
    if data.get("data_status") != "ok":
        return None
    return bool(data.get("running") or data.get("preheating") or data.get("cooldown"))


def _ventilation_state(data: dict) -> bool | None:
    if data.get("data_status") != "ok":
        return None
    return data.get("heater_mode") == "ventilation"


def _highland_state(data: dict) -> bool | None:
    value = data.get("highland_mode")
    return None if value is None else bool(value)


SWITCHES: tuple[HCalorySwitchDescription, ...] = (
    HCalorySwitchDescription(
        key="power",
        name="Heating",
        icon="mdi:fire",
        on_command="start_heat",
        off_command="stop_heat",
        state_fn=_power_state,
        control_mode=MODE_HEATING,
    ),
    HCalorySwitchDescription(
        key="ventilation",
        name="Ventilation",
        icon="mdi:fan",
        on_command="ventilation",
        off_command="ventilation",
        state_fn=_ventilation_state,
        control_mode=MODE_VENTILATION,
    ),
    HCalorySwitchDescription(
        key="highland_mode",
        name="Highland mode",
        icon="mdi:image-filter-hdr",
        on_command="hcalory_highland_toggle",
        off_command="hcalory_highland_toggle",
        state_fn=_highland_state,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up HCalory switches."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: HCaloryCoordinator = data["coordinator"]
    client: DaemonClient = data["client"]
    unique_base = entry.unique_id or entry.entry_id
    mode_state = data.setdefault("mode_state", {"active_mode": MODE_OFF})
    entities = [HCalorySwitch(coordinator, client, unique_base, description, mode_state) for description in SWITCHES]
    entities.append(HCaloryAutoModeSwitch(hass, coordinator, client, unique_base, mode_state))
    async_add_entities(entities)


class HCalorySwitch(HCaloryEntity, SwitchEntity):
    """Switch that maps state plus daemon commands."""

    entity_description: HCalorySwitchDescription

    def __init__(
        self,
        coordinator: HCaloryCoordinator,
        client: DaemonClient,
        unique_base: str,
        description: HCalorySwitchDescription,
        mode_state: dict,
    ) -> None:
        super().__init__(coordinator, unique_base, f"switch_{description.key}", description.name or description.key)
        self.entity_description = description
        self._client = client
        self._mode_state = mode_state

    @property
    def is_on(self) -> bool | None:
        if self.entity_description.control_mode is not None:
            return self._mode_state.get("active_mode") == self.entity_description.control_mode
        return self.entity_description.state_fn(self.data)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        if self.is_on is True:
            return
        if self.entity_description.control_mode is not None:
            await self._leave_current_mode()
        await self._client.command(self.entity_description.on_command)
        if self.entity_description.control_mode is not None:
            self._mode_state["active_mode"] = self.entity_description.control_mode
            self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        if self.is_on is False:
            return
        command = self.entity_description.off_command or self.entity_description.on_command
        await self._client.command(command)
        if self.entity_description.control_mode is not None:
            self._mode_state["active_mode"] = MODE_OFF
            self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def _leave_current_mode(self) -> None:
        """Stop the currently selected exclusive control mode."""
        current = self._mode_state.get("active_mode", MODE_OFF)
        target = self.entity_description.control_mode
        if current in {MODE_OFF, target}:
            return

        if current == MODE_VENTILATION:
            await self._client.command("ventilation")
        elif current in {MODE_HEATING, MODE_AUTO}:
            await self._client.command("stop_heat")

        self._mode_state["active_mode"] = MODE_OFF
        await asyncio.sleep(0.2)
        await self.coordinator.async_request_refresh()


class HCaloryAutoModeSwitch(HCaloryEntity, SwitchEntity, RestoreEntity):
    """Integration-managed automatic heating mode."""

    _attr_icon = "mdi:autorenew"
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: HCaloryCoordinator,
        client: DaemonClient,
        unique_base: str,
        mode_state: dict,
    ) -> None:
        super().__init__(coordinator, unique_base, "switch_auto_mode", "Auto mode")
        self._hass = hass
        self._client = client
        self._mode_state = mode_state
        self._evaluating = False

    async def async_added_to_hass(self) -> None:
        """Restore Auto state and subscribe to daemon data updates."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            if last_state.state == "on":
                self._mode_state["active_mode"] = MODE_AUTO
            self.async_write_ha_state()

        self.async_on_remove(
            self.coordinator.async_add_listener(
                lambda: self._hass.async_create_task(self._async_evaluate())
            )
        )

        if self.is_on:
            self._hass.async_create_task(self._async_evaluate())

    @property
    def is_on(self) -> bool:
        """Return whether automatic mode is enabled."""
        return self._mode_state.get("active_mode") == MODE_AUTO

    async def async_turn_on(self, **kwargs) -> None:
        """Enable automatic mode and immediately evaluate conditions."""
        if self.is_on:
            return
        await self._leave_current_mode()
        self._mode_state["active_mode"] = MODE_AUTO
        self.async_write_ha_state()
        await self._async_evaluate(force_refresh=True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable automatic mode without changing the heater state."""
        if not self.is_on:
            return
        self._mode_state["active_mode"] = MODE_OFF
        self.async_write_ha_state()

    async def _async_evaluate(self, force_refresh: bool = False) -> None:
        """Apply Auto mode rules after daemon data updates."""
        if not self.is_on or self._evaluating:
            return

        self._evaluating = True
        try:
            if force_refresh:
                await self.coordinator.async_request_refresh()

            data = self.data
            if data.get("data_status") != "ok":
                return

            if data.get("heater_mode") == "ventilation":
                await self._client.command("ventilation")
                await asyncio.sleep(0.2)
                await self.coordinator.async_request_refresh()
                data = self.data

            ambient = self._float_data(data, "ambient_temperature")
            target = self._float_state(AUTO_TARGET_ENTITY_ID)
            hysteresis = self._float_state(AUTO_HYSTERESIS_ENTITY_ID)
            if ambient is None or target is None or hysteresis is None:
                return

            heating_active = bool(data.get("running") or data.get("preheating") or data.get("cooldown"))
            if ambient <= target - hysteresis and not heating_active:
                await self._client.command("start_heat")
                await asyncio.sleep(0.2)
                await self._client.command("gear")
                await self.coordinator.async_request_refresh()
            elif ambient >= target + hysteresis and heating_active:
                await self._client.command("stop_heat")
                await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.warning("Auto mode evaluation failed: %s", err)
        finally:
            self._evaluating = False

    async def _leave_current_mode(self) -> None:
        """Stop any active manual mode before Auto takes control."""
        current = self._mode_state.get("active_mode", MODE_OFF)
        if current in {MODE_OFF, MODE_AUTO}:
            return

        data = self.data
        if current == MODE_VENTILATION or data.get("heater_mode") == "ventilation":
            await self._client.command("ventilation")
        elif current == MODE_HEATING or data.get("running") or data.get("preheating") or data.get("cooldown"):
            await self._client.command("stop_heat")

        self._mode_state["active_mode"] = MODE_OFF
        await asyncio.sleep(0.2)
        await self.coordinator.async_request_refresh()

    def _float_state(self, entity_id: str) -> float | None:
        state = self._hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _float_data(data: dict, key: str) -> float | None:
        value = data.get(key)
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None
