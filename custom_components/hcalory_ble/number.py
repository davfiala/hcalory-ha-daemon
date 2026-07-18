"""Number entities for HCalory BLE."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import HCaloryCoordinator
from .daemon_client import DaemonClient
from .entity import HCaloryEntity

_LOGGER = logging.getLogger(__name__)

ADJUST_RETRY_DELAY = 8.0
ADJUST_POLL_DELAY = 0.5
GEAR_MIN = 1
GEAR_MAX = 6
THERMOSTAT_MIN = 15
THERMOSTAT_MAX = 28
AUTO_MODE_ENTITY_ID = "switch.hcalory_ble_auto_mode"


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up HCalory number entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: HCaloryCoordinator = data["coordinator"]
    client: DaemonClient = data["client"]
    unique_base = entry.unique_id or entry.entry_id
    async_add_entities([HCaloryRequestedSettingNumber(coordinator, client, unique_base)])


class HCaloryRequestedSettingNumber(HCaloryEntity, NumberEntity, RestoreEntity):
    """Desired setting synchronized through paced up/down commands."""

    _attr_icon = "mdi:tune"
    _attr_name = "Requested setting"
    _attr_native_step = 1
    _attr_should_poll = False

    def __init__(self, coordinator: HCaloryCoordinator, client: DaemonClient, unique_base: str) -> None:
        super().__init__(coordinator, unique_base, "number_requested_setting", "Requested setting")
        self._client = client
        self._targets: dict[str, int | None] = {"level": None, "thermostat": None}
        self._adjust_task: asyncio.Task | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the target and react to daemon data updates."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            try:
                self._targets["level"] = int(float(last_state.state))
            except (TypeError, ValueError):
                self._targets["level"] = None

        self.async_on_remove(
            self.coordinator.async_add_listener(
                lambda: self.hass.async_create_task(self._async_schedule_adjust())
            )
        )
        self.hass.async_create_task(self._async_schedule_adjust())

    @property
    def native_min_value(self) -> float:
        """Return min value for the currently meaningful setting."""
        return THERMOSTAT_MIN if self._setting_kind == "thermostat" else GEAR_MIN

    @property
    def native_max_value(self) -> float:
        """Return max value for the currently meaningful setting."""
        return THERMOSTAT_MAX if self._setting_kind == "thermostat" else GEAR_MAX

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit for thermostat mode."""
        return UnitOfTemperature.CELSIUS if self._setting_kind == "thermostat" else None

    @property
    def native_value(self) -> int | None:
        """Return desired value, falling back to the current heater value."""
        target = self._target
        return target if target is not None else self._actual

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose actual/target progress for cards and diagnostics."""
        actual = self._actual
        target = self._target
        return {
            "setting_kind": self._setting_kind,
            "actual_value": actual,
            "target_value": target,
            "adjusting": self._is_adjusting,
            "progress": f"{actual}>{target}" if actual is not None and target is not None and actual != target else None,
        }

    async def async_set_native_value(self, value: float) -> None:
        """Set a desired value and let the integration converge to it."""
        target = int(round(value))
        target = max(int(self.native_min_value), min(int(self.native_max_value), target))
        self._targets[self._setting_kind] = target
        self.async_write_ha_state()
        await self._async_schedule_adjust()

    @property
    def _mode(self) -> str | None:
        mode = self.data.get("heater_mode")
        return mode if isinstance(mode, str) else None

    @property
    def _setting_kind(self) -> str:
        """Return what the requested setting currently represents."""
        auto_state = self.hass.states.get(AUTO_MODE_ENTITY_ID)
        if auto_state is not None and auto_state.state == "on":
            return "level"
        return "thermostat" if self._mode == "thermostat" else "level"

    @property
    def _target(self) -> int | None:
        return self._targets[self._setting_kind]

    @property
    def _actual(self) -> int | None:
        value = self.data.get("heater_setting")
        try:
            return None if value is None else int(float(value))
        except (TypeError, ValueError):
            return None

    @property
    def _is_adjusting(self) -> bool:
        actual = self._actual
        return actual is not None and self._target is not None and actual != self._target and self._can_adjust

    @property
    def _can_adjust(self) -> bool:
        return self.data.get("data_status") == "ok" and self._mode in {"gear", "thermostat", "ventilation"}

    async def _async_schedule_adjust(self) -> None:
        if self._adjust_task is not None and not self._adjust_task.done():
            return
        self._adjust_task = self.hass.async_create_task(self._async_adjust_loop())

    async def _async_adjust_loop(self) -> None:
        while self._target is not None and self._can_adjust:
            actual = self._actual
            if actual is None or actual == self._target:
                self.async_write_ha_state()
                return

            command = "up" if actual < self._target else "down"
            expected_direction = 1 if command == "up" else -1
            try:
                await self._client.command(command)
                changed = await self._async_wait_for_setting_change(actual, expected_direction)
                if not changed:
                    _LOGGER.debug(
                        "Requested setting did not change from %s after %.1fs; retrying %s",
                        actual,
                        ADJUST_RETRY_DELAY,
                        command,
                    )
            except Exception as err:
                _LOGGER.warning("Requested setting adjustment failed: %s", err)
                return

    async def _async_wait_for_setting_change(self, previous: int, expected_direction: int) -> bool:
        """Wait until heater setting moves in the requested direction."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + ADJUST_RETRY_DELAY
        while loop.time() < deadline:
            await asyncio.sleep(ADJUST_POLL_DELAY)
            await self.coordinator.async_request_refresh()
            actual = self._actual
            self.async_write_ha_state()
            if actual is None:
                continue
            if (actual - previous) * expected_direction > 0:
                return True
            if self._target is not None and actual == self._target:
                return True
        return False
