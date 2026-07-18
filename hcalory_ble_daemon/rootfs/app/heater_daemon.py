#!/usr/bin/env python3
"""
UNIX-socket daemon for HCalory heater control.

The daemon keeps one BLE connection/polling loop alive in the background and
serves Home Assistant quickly from cached state over a UNIX socket.
"""
from __future__ import annotations

import argparse
import asyncio
import enum
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from typing import Any

import bleak
import bleak_retry_connector


logger = logging.getLogger("hcalory-control")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


COMMAND_HEADER = bytes.fromhex("000200010001000e040000090000000000000000")
HCALORY_CMD_SET_GEAR = 0x0607
HCALORY_CMD_SET_TEMP = 0x0706
HCALORY_CMD_POWER = 0x0E04
HCALORY_POWER_AUTO_TOGGLE = 0x05
HCALORY_POWER_MODE_TEMP = 0x06
HCALORY_POWER_MODE_LEVEL = 0x07
HCALORY_POWER_CELSIUS = 0x0A
HCALORY_POWER_FAHRENHEIT = 0x0B
HCALORY_POWER_HIGHLAND_TOGGLE = 0x09
HCALORY_PROTOCOL_VERSION = "hcalory-power-v1_0_12"
DEFAULT_SOCKET_DIR = "/var/lib/homeassistant/homeassistant/hcalory"
DEFAULT_READ_TIMEOUT = 5.0
DEFAULT_SCAN_TIMEOUT = 5.0


class ListableEnum(enum.Enum):
    @classmethod
    def list(cls) -> list[str]:
        return list(cls.__members__.keys())


class Command(bytes, ListableEnum):
    stop_heat = COMMAND_HEADER + bytes.fromhex("010e")
    start_heat = COMMAND_HEADER + bytes.fromhex("020f")
    up = COMMAND_HEADER + bytes.fromhex("0310")
    down = COMMAND_HEADER + bytes.fromhex("0411")
    gear = COMMAND_HEADER + bytes.fromhex("0714")
    thermostat = COMMAND_HEADER + bytes.fromhex("0613")
    pump_data = COMMAND_HEADER + bytes.fromhex("000d")
    ventilation = COMMAND_HEADER + bytes.fromhex("0815")


def build_hcalory_command(cmd_type: int, payload: bytes) -> bytes:
    cmd_hi = (cmd_type >> 8) & 0xFF
    cmd_lo = cmd_type & 0xFF
    payload_for_checksum = bytes([cmd_lo, 0x00, 0x00, len(payload)]) + payload
    checksum = sum(payload_for_checksum) & 0xFF
    return bytes([0x00, 0x02, 0x00, 0x01, 0x00, 0x01, 0x00, cmd_hi]) + payload_for_checksum + bytes([checksum])


def build_hcalory_power_action(action: int) -> bytes:
    return build_hcalory_command(HCALORY_CMD_POWER, bytes([0, 0, 0, 0, 0, 0, 0, 0, action]))


class SocketCommand(str, enum.Enum):
    daemon_status = "daemon_status"
    heater_status = "heater_status"
    pump_data = "pump_data"
    pump_data_force = "pump_data_force"


class HeaterState(int, ListableEnum):
    off = 0
    standby = 1
    cooldown = 65
    cooldown_starting = 67
    cooldown_received = 69
    ignition_received = 128
    ignition_starting = 129
    igniting = 131
    running = 133
    heating = 135
    fan_starting = 192
    fan_only = 193
    error26 = 26
    error255 = 255


class HeaterMode(int, ListableEnum):
    off = 0
    thermostat = 1
    gear = 2
    ventilation = 3
    ignition_failed = 8
    unknown = 92


HCALORY_STATUS_NAMES = {
    0x0: "off",
    0x4: "turning_off",
    0x8: "heating",
    0xC: "ventilation",
    0xF: "error",
}

HCALORY_RUNNING_STEP_NAMES = {
    0x0: "inactive",
    0x1: "fan",
    0x3: "ignition",
    0x4: "cooldown",
    0x5: "running",
    0x7: "standby",
}

TEMPERATURE_UNIT_NAMES = {
    0: "celsius",
    1: "fahrenheit",
}


def enum_name(value: enum.Enum | None) -> str | None:
    return value.name if value is not None else None


def read_u16_tenths(raw: bytes) -> int | None:
    if len(raw) != 2:
        return None
    return int.from_bytes(raw, byteorder="big") // 10


class HeaterResponse:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.header = raw[0:20]
        self.end_junk = raw[33:40]

        self.heater_state_raw = raw[20] if len(raw) > 20 else None
        self.heater_mode_raw = raw[21] if len(raw) > 21 else None
        self.heater_setting = raw[22] if len(raw) > 22 else None
        self.mystery = raw[23] if len(raw) > 23 else None
        self.auto_start_stop_raw = raw[23] if len(raw) > 23 else None
        self.voltage_raw = raw[25] if len(raw) > 25 else None
        self._body_temperature = raw[27:29]
        self._ambient_temperature = raw[30:32]
        self.highland_mode_raw = raw[36] if len(raw) > 36 else None
        self.temperature_unit_raw = raw[37] if len(raw) > 37 else None
        self._hcalory_status_raw = None if self.heater_state_raw is None else (self.heater_state_raw & 0xF0) >> 4
        self._hcalory_running_step_raw = None if self.heater_state_raw is None else self.heater_state_raw & 0x0F

        self.heater_state = self._parse_enum(
            HeaterState,
            self.heater_state_raw,
            warn_unknown=self._hcalory_status_raw not in HCALORY_STATUS_NAMES,
        )
        self.heater_mode = self._parse_enum(HeaterMode, self.heater_mode_raw)

    @staticmethod
    def _parse_enum(
        enum_type: type[enum.Enum],
        value: int | None,
        *,
        warn_unknown: bool = True,
    ) -> enum.Enum | None:
        if value is None:
            return None
        try:
            return enum_type(value)
        except ValueError:
            if warn_unknown:
                logger.warning("Unknown %s value: %s", enum_type.__name__, value)
            return None

    @property
    def valid(self) -> bool:
        return (
            (self.heater_state is not None or self.hcalory_status_raw in HCALORY_STATUS_NAMES)
            and self.heater_mode is not None
            and self.voltage is not None
            and self.body_temperature is not None
            and self.ambient_temperature is not None
        )

    @property
    def voltage(self) -> int | None:
        return None if self.voltage_raw is None else self.voltage_raw // 10

    @property
    def voltage_v(self) -> float | None:
        return None if self.voltage_raw is None else self.voltage_raw / 10.0

    @property
    def body_temperature(self) -> int | None:
        return read_u16_tenths(self._body_temperature)

    @property
    def ambient_temperature(self) -> int | None:
        return read_u16_tenths(self._ambient_temperature)

    @property
    def hcalory_status_raw(self) -> int | None:
        return self._hcalory_status_raw

    @property
    def hcalory_status(self) -> str | None:
        raw = self.hcalory_status_raw
        return None if raw is None else HCALORY_STATUS_NAMES.get(raw, f"unknown_{raw}")

    @property
    def hcalory_running_step_raw(self) -> int | None:
        return self._hcalory_running_step_raw

    @property
    def hcalory_running_step(self) -> str | None:
        raw = self.hcalory_running_step_raw
        return None if raw is None else HCALORY_RUNNING_STEP_NAMES.get(raw, f"unknown_{raw}")

    @property
    def temperature_unit(self) -> str | None:
        raw = self.temperature_unit_raw
        return None if raw is None else TEMPERATURE_UNIT_NAMES.get(raw, f"unknown_{raw}")

    @property
    def highland_mode(self) -> bool | None:
        if self.highland_mode_raw == 1:
            return True
        if self.highland_mode_raw == 0:
            return False
        return None

    @property
    def auto_start_stop(self) -> bool | None:
        if self.auto_start_stop_raw == 1:
            return True
        if self.auto_start_stop_raw == 2:
            return False
        return None

    @property
    def error_code(self) -> int:
        if self.hcalory_status_raw == 0xF:
            return self.heater_setting or 0
        if self.heater_state in (HeaterState.error26, HeaterState.error255):
            return self.heater_state_raw or 0
        return 0

    @property
    def cooldown(self) -> bool:
        return self.hcalory_status_raw == 0x4 or self.heater_state in (
            HeaterState.cooldown_received,
            HeaterState.cooldown_starting,
            HeaterState.cooldown,
        )

    @property
    def preheating(self) -> bool:
        return self.hcalory_running_step_raw == 0x3 or self.heater_state in (
            HeaterState.ignition_received,
            HeaterState.ignition_starting,
            HeaterState.igniting,
            HeaterState.heating,
        )

    @property
    def running(self) -> bool:
        return self.hcalory_status_raw == 0x8 or self.heater_state in (
            HeaterState.ignition_received,
            HeaterState.ignition_starting,
            HeaterState.igniting,
            HeaterState.running,
            HeaterState.heating,
        )

    def asdict(self) -> dict[str, Any]:
        return {
            "protocol_version": HCALORY_PROTOCOL_VERSION,
            "valid": self.valid,
            "heater_state": enum_name(self.heater_state),
            "heater_state_raw": self.heater_state_raw,
            "hcalory_status": self.hcalory_status,
            "hcalory_status_raw": self.hcalory_status_raw,
            "hcalory_running_step": self.hcalory_running_step,
            "hcalory_running_step_raw": self.hcalory_running_step_raw,
            "heater_mode": enum_name(self.heater_mode),
            "heater_mode_raw": self.heater_mode_raw,
            "heater_setting": self.heater_setting,
            "auto_start_stop": self.auto_start_stop,
            "auto_start_stop_raw": self.auto_start_stop_raw,
            "highland_mode": self.highland_mode,
            "highland_mode_raw": self.highland_mode_raw,
            "temperature_unit": self.temperature_unit,
            "temperature_unit_raw": self.temperature_unit_raw,
            "error_code": self.error_code,
            "voltage": self.voltage,
            "voltage_v": self.voltage_v,
            "voltage_raw": self.voltage_raw,
            "body_temperature": self.body_temperature,
            "ambient_temperature": self.ambient_temperature,
            "running": self.running,
            "cooldown": self.cooldown,
            "preheating": self.preheating,
            "raw": self.raw.hex(" "),
        }


@dataclass
class RuntimeStatus:
    started_at: float
    last_success: float = 0.0
    last_attempt: float = 0.0
    last_error_at: float = 0.0
    last_error: str | None = None
    consecutive_failures: int = 0
    connected: bool = False
    connecting: bool = False
    next_retry_at: float = 0.0

    def mark_connected(self, connected: bool) -> None:
        self.connected = connected
        if connected:
            self.connecting = False

    def mark_connecting(self, connecting: bool) -> None:
        self.connecting = connecting
        if connecting:
            self.last_attempt = time.time()

    def mark_success(self) -> None:
        now = time.time()
        self.last_success = now
        self.last_attempt = now
        self.last_error = None
        self.consecutive_failures = 0
        self.connecting = False
        self.next_retry_at = 0.0

    def mark_failure(self, exc: Exception | str) -> None:
        now = time.time()
        self.last_attempt = now
        self.last_error_at = now
        self.last_error = str(exc)
        self.consecutive_failures += 1
        self.connecting = False

    def schedule_retry(self, delay: float) -> None:
        self.next_retry_at = time.time() + max(0.0, delay)

    def retry_delay(self, base_delay: float, max_delay: float) -> float:
        exponent = min(max(self.consecutive_failures - 1, 0), 6)
        return min(max_delay, base_delay * (2 ** exponent))

    def retry_delay_for_error(
        self,
        error: Exception | str,
        base_delay: float,
        max_delay: float,
        not_found_max_delay: float,
    ) -> float:
        message = str(error).lower()
        if "not found" in message or "device disappeared" in message:
            return self.retry_delay(base_delay, not_found_max_delay)
        return self.retry_delay(base_delay, max_delay)

    def retry_in(self) -> float | None:
        if self.next_retry_at <= 0:
            return None
        return max(0.0, self.next_retry_at - time.time())

    def daemon_status(self) -> dict[str, Any]:
        now = time.time()
        return {
            "daemon_status": "running",
            "alive": True,
            "timestamp": now,
            "uptime": now - self.started_at,
        }

    def heater_status(self, max_age: float, has_valid_data: bool) -> dict[str, Any]:
        now = time.time()
        last_success_age = None if self.last_success == 0 else now - self.last_success

        if self.connecting:
            heater_status = "connecting"
            data_status = "unavailable"
        elif not self.connected:
            heater_status = "disconnected"
            data_status = "unavailable"
        elif self.consecutive_failures > 0:
            heater_status = "error"
            data_status = "error"
        elif not has_valid_data:
            heater_status = "connected_no_data"
            data_status = "missing"
        elif last_success_age is not None and last_success_age > max_age:
            heater_status = "stale"
            data_status = "stale"
        else:
            heater_status = "ok"
            data_status = "ok"

        return {
            "heater_status": heater_status,
            "connected": self.connected,
            "connecting": self.connecting,
            "data_status": data_status,
            "last_success": self.last_success or None,
            "last_success_age": last_success_age,
            "last_attempt": self.last_attempt or None,
            "last_error_at": self.last_error_at or None,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
            "next_retry_at": self.next_retry_at or None,
            "retry_in": self.retry_in(),
        }


class HCaloryHeater:
    write_characteristic_id = "0000fff2-0000-1000-8000-00805f9b34fb"
    read_characteristic_id = "0000fff1-0000-1000-8000-00805f9b34fb"

    def __init__(
        self,
        address: str,
        status: RuntimeStatus,
        bluetooth_timeout: float = 30.0,
        scan_timeout: float = DEFAULT_SCAN_TIMEOUT,
        max_bluetooth_retry_attempts: int = 20,
    ):
        self.address = address
        self.status = status
        self.bluetooth_timeout = bluetooth_timeout
        self.scan_timeout = scan_timeout
        self.max_bluetooth_retry_attempts = max_bluetooth_retry_attempts
        self.bleak_client: bleak.BleakClient | None = None
        self._write_characteristic: bleak.BleakGATTCharacteristic | None = None
        self._read_characteristic: bleak.BleakGATTCharacteristic | None = None
        self._data_queue: asyncio.Queue[bytearray] = asyncio.Queue()
        self._connect_lock = asyncio.Lock()
        self._command_lock = asyncio.Lock()
        self._intentional_disconnect = False
        self.heater_response: HeaterResponse | None = None

    @property
    def is_connected(self) -> bool:
        return bool(self.bleak_client and self.bleak_client.is_connected)

    async def _ensure_connection(self, reason: str = "") -> None:
        if self.is_connected:
            self.status.mark_connected(True)
            return

        async with self._connect_lock:
            if self.is_connected:
                self.status.mark_connected(True)
                return

            logger.info("Connecting to heater %s %s", self.address, reason)
            self.status.mark_connecting(True)
            device = await bleak.BleakScanner.find_device_by_address(self.address, timeout=self.scan_timeout)
            if device is None:
                self.status.mark_connecting(False)
                self.status.mark_connected(False)
                self.bleak_client = None
                self._read_characteristic = None
                self._write_characteristic = None
                raise RuntimeError(f"Heater {self.address} not found")

            try:
                self.bleak_client = await bleak_retry_connector.establish_connection(
                    bleak.BleakClient,
                    device,
                    self.address,
                    self.handle_disconnect,
                    use_services_cache=True,
                    max_attempts=self.max_bluetooth_retry_attempts,
                    timeout=self.bluetooth_timeout,
                )
                await self.bleak_client.start_notify(self.read_characteristic, self._data_handler)
                self.status.mark_connected(True)
                logger.info("Connected to heater %s", self.address)
            except Exception:
                self.status.mark_connecting(False)
                self.status.mark_connected(False)
                self.bleak_client = None
                self._read_characteristic = None
                self._write_characteristic = None
                raise

    @property
    def read_characteristic(self) -> bleak.BleakGATTCharacteristic:
        if self._read_characteristic is None:
            assert self.bleak_client is not None
            characteristic = self.bleak_client.services.get_characteristic(self.read_characteristic_id)
            if characteristic is None:
                raise RuntimeError(f"Read characteristic {self.read_characteristic_id} not found")
            self._read_characteristic = characteristic
        return self._read_characteristic

    @property
    def write_characteristic(self) -> bleak.BleakGATTCharacteristic:
        if self._write_characteristic is None:
            assert self.bleak_client is not None
            characteristic = self.bleak_client.services.get_characteristic(self.write_characteristic_id)
            if characteristic is None:
                raise RuntimeError(f"Write characteristic {self.write_characteristic_id} not found")
            self._write_characteristic = characteristic
        return self._write_characteristic

    def handle_disconnect(self, client: bleak.BleakClient) -> None:
        if not self._intentional_disconnect:
            if self.status.connecting:
                logger.debug("Disconnect while connecting to %s", self.address)
            else:
                logger.warning("Encountered unintentional disconnect from %s", self.address)
        self.status.mark_connected(False)
        self._read_characteristic = None
        self._write_characteristic = None

    async def _data_handler(self, _: bleak.BleakGATTCharacteristic, data: bytearray) -> None:
        logger.debug("RX RAW (%d): %s", len(data), data.hex(" "))
        await self._data_queue.put(data)

    async def send_command(self, cmd: Command) -> None:
        async with self._command_lock:
            await self._ensure_connection(f"(send {cmd.name})")
            assert self.bleak_client is not None
            if cmd is Command.pump_data:
                logger.debug("TX %-12s %s", cmd.name, cmd.hex(" "))
            else:
                logger.info("TX %-12s %s", cmd.name, cmd.hex(" "))
            await self.bleak_client.write_gatt_char(self.write_characteristic, cmd)

    async def send_raw_command(self, cmd_id: int) -> None:
        if not 0 <= cmd_id <= 0xFF:
            raise ValueError("Raw command id must be in range 00..FF")

        cmd = COMMAND_HEADER + bytes([cmd_id, (cmd_id + 0x0D) & 0xFF])
        await self.send_packet(f"raw {cmd_id:02X}", cmd)

    async def send_packet(self, name: str, packet: bytes) -> None:
        async with self._command_lock:
            await self._ensure_connection(f"(send {name})")
            assert self.bleak_client is not None
            logger.info("TX %-12s %s", name, packet.hex(" "))
            await self.bleak_client.write_gatt_char(self.write_characteristic, packet)

    async def send_hcalory_set_gear(self, level: int) -> None:
        if not 1 <= level <= 10:
            raise ValueError("Gear level must be in range 1..10")
        await self.send_packet("hcalory_gear", build_hcalory_command(HCALORY_CMD_SET_GEAR, bytes([level])))

    async def send_hcalory_set_temperature(self, temperature: int, unit: int | None = None) -> None:
        if unit is None:
            unit = self.heater_response.temperature_unit_raw if self.heater_response else 0
        if unit == 0 and not 0 <= temperature <= 40:
            raise ValueError("Celsius temperature must be in range 0..40")
        if unit == 1 and not 32 <= temperature <= 104:
            raise ValueError("Fahrenheit temperature must be in range 32..104")
        if unit not in (0, 1):
            raise ValueError("Temperature unit must be 0/celsius or 1/fahrenheit")
        await self.send_packet("hcalory_temp", build_hcalory_command(HCALORY_CMD_SET_TEMP, bytes([temperature, unit])))

    async def send_hcalory_power_action(self, name: str, action: int) -> None:
        await self.send_packet(name, build_hcalory_power_action(action))

    async def start_heat(self) -> None:
        await self.send_command(Command.start_heat)

    async def stop_heat(self) -> None:
        await self.send_command(Command.stop_heat)

    async def toggle_ventilation(self) -> None:
        await self.send_command(Command.ventilation)

    async def change_setting_up(self) -> None:
        await self.send_command(Command.up)

    async def change_setting_down(self) -> None:
        await self.send_command(Command.down)

    async def set_gear_mode(self) -> None:
        await self.send_command(Command.gear)

    async def set_thermostat_mode(self) -> None:
        await self.send_command(Command.thermostat)

    def _drain_data_queue(self) -> None:
        while True:
            try:
                self._data_queue.get_nowait()
            except asyncio.QueueEmpty:
                return

    async def get_data(self, timeout: float = DEFAULT_READ_TIMEOUT) -> HeaterResponse:
        self._drain_data_queue()
        await self.send_command(Command.pump_data)
        raw = await asyncio.wait_for(self._data_queue.get(), timeout=timeout)
        resp = HeaterResponse(bytes(raw))
        self.heater_response = resp
        if not resp.valid:
            raise RuntimeError(f"Received invalid pump_data frame: {resp.raw.hex(' ')}")
        self.status.mark_success()
        self.status.mark_connected(True)
        return resp

    async def disconnect(self) -> None:
        self._intentional_disconnect = True
        if self.bleak_client:
            try:
                await self.bleak_client.disconnect()
            except Exception as exc:
                logger.debug("Disconnect error: %s", exc)
            self.bleak_client = None
            self._read_characteristic = None
            self._write_characteristic = None
        self.status.mark_connected(False)


def socket_path_for_address(address: str, socket_dir: str = DEFAULT_SOCKET_DIR) -> str:
    clean = address.lower().replace(":", "_")
    return os.path.join(socket_dir, f"hcalory-control-{clean}.sock")


def json_line(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, sort_keys=True) + "\n").encode()


def parse_temperature_unit(value: str) -> int:
    normalized = value.strip().lower()
    if normalized in ("0", "c", "celsius"):
        return 0
    if normalized in ("1", "f", "fahrenheit"):
        return 1
    raise ValueError("Temperature unit must be celsius or fahrenheit")


async def run_daemon(
    address: str,
    interval: float,
    debug: bool,
    max_age: float,
    socket_dir: str,
    read_timeout: float,
    bluetooth_timeout: float,
    scan_timeout: float,
    connect_attempts: int,
    reconnect_backoff: float,
    reconnect_backoff_max: float,
    not_found_backoff_max: float,
) -> None:
    socket_path = socket_path_for_address(address, socket_dir)
    os.makedirs(os.path.dirname(socket_path), exist_ok=True)

    if os.path.exists(socket_path):
        os.remove(socket_path)

    status = RuntimeStatus(started_at=time.time())
    logger.info("Using HCalory protocol parser %s", HCALORY_PROTOCOL_VERSION)
    heater = HCaloryHeater(
        address,
        status,
        bluetooth_timeout=bluetooth_timeout,
        scan_timeout=scan_timeout,
        max_bluetooth_retry_attempts=connect_attempts,
    )
    poll_lock = asyncio.Lock()

    async def poll_once() -> HeaterResponse | None:
        async with poll_lock:
            try:
                logger.debug("Polling pump_data")
                resp = await heater.get_data(timeout=read_timeout)
                if debug:
                    print(json.dumps(resp.asdict(), indent=4, sort_keys=True))
                return resp
            except Exception as exc:
                status.mark_failure(exc)
                status.mark_connected(heater.is_connected)
                max_delay = reconnect_backoff_max if status.connected else not_found_backoff_max
                delay = status.retry_delay_for_error(
                    exc,
                    reconnect_backoff,
                    max_delay,
                    not_found_backoff_max,
                )
                status.schedule_retry(delay)
                logger.warning("Polling failed: %s; retrying in %.1fs", exc, delay)
                return None

    async def poll_loop() -> None:
        while True:
            retry_in = status.retry_in()
            if retry_in is not None and retry_in > 0:
                await asyncio.sleep(min(retry_in, interval))
                continue

            resp = await poll_once()
            if resp is None:
                await asyncio.sleep(min(status.retry_in() or interval, interval))
            else:
                await asyncio.sleep(interval)

    poll_task = asyncio.create_task(poll_loop())

    command_mapping = {
        "start_heat": heater.start_heat,
        "stop_heat": heater.stop_heat,
        "up": heater.change_setting_up,
        "down": heater.change_setting_down,
        "gear": heater.set_gear_mode,
        "thermostat": heater.set_thermostat_mode,
        "ventilation": heater.toggle_ventilation,
    }

    async def write_response(writer: asyncio.StreamWriter, payload: bytes) -> None:
        writer.write(payload)
        await writer.drain()

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            data = await reader.read(1024)
            if not data:
                return

            cmd = data.decode(errors="replace").strip()
            logger.debug("Socket received command: %s", cmd)

            if cmd == SocketCommand.daemon_status.value:
                await write_response(writer, json_line(status.daemon_status()))
                return

            if cmd == SocketCommand.heater_status.value:
                has_valid_data = bool(heater.heater_response and heater.heater_response.valid)
                await write_response(writer, json_line(status.heater_status(max_age, has_valid_data)))
                return

            if cmd == SocketCommand.pump_data.value:
                if heater.heater_response is None:
                    await write_response(writer, json_line({"error": "no cached pump_data"}))
                    return
                logger.debug("Serving cached pump_data")
                await write_response(writer, json_line(heater.heater_response.asdict()))
                return

            if cmd == SocketCommand.pump_data_force.value:
                logger.debug("Serving forced pump_data refresh")
                if poll_lock.locked():
                    payload = status.heater_status(max_age, bool(heater.heater_response and heater.heater_response.valid))
                    payload["poll_in_progress"] = True
                    await write_response(writer, json_line(payload))
                    return
                resp = await poll_once()
                if resp is None:
                    await write_response(writer, json_line(status.heater_status(max_age, False)))
                    return
                await write_response(writer, json_line(resp.asdict()))
                return

            if cmd.lower().startswith("raw "):
                value = int(cmd.split(maxsplit=1)[1], 16)
                await heater.send_raw_command(value)
                await write_response(writer, f"OK: raw {value:02X}\n".encode())
                return

            parts = cmd.split()
            hcalory_cmd = parts[0].lower() if parts else ""

            if hcalory_cmd == "hcalory_set_gear":
                if len(parts) != 2:
                    raise ValueError("Usage: hcalory_set_gear <1..10>")
                level = int(parts[1], 10)
                await heater.send_hcalory_set_gear(level)
                await write_response(writer, f"OK: hcalory_set_gear {level}\n".encode())
                return

            if hcalory_cmd == "hcalory_set_temp":
                if len(parts) not in (2, 3):
                    raise ValueError("Usage: hcalory_set_temp <temperature> [celsius|fahrenheit]")
                temperature = int(parts[1], 10)
                unit = parse_temperature_unit(parts[2]) if len(parts) == 3 else None
                await heater.send_hcalory_set_temperature(temperature, unit)
                await write_response(writer, f"OK: hcalory_set_temp {temperature}\n".encode())
                return

            if hcalory_cmd == "hcalory_set_unit":
                if len(parts) != 2:
                    raise ValueError("Usage: hcalory_set_unit <celsius|fahrenheit>")
                unit = parse_temperature_unit(parts[1])
                action = HCALORY_POWER_FAHRENHEIT if unit == 1 else HCALORY_POWER_CELSIUS
                await heater.send_hcalory_power_action("hcalory_unit", action)
                await write_response(writer, f"OK: hcalory_set_unit {parts[1].lower()}\n".encode())
                return

            if hcalory_cmd == "hcalory_set_mode":
                if len(parts) != 2 or parts[1].lower() not in ("gear", "thermostat"):
                    raise ValueError("Usage: hcalory_set_mode <gear|thermostat>")
                action = HCALORY_POWER_MODE_TEMP if parts[1].lower() == "thermostat" else HCALORY_POWER_MODE_LEVEL
                await heater.send_hcalory_power_action("hcalory_mode", action)
                await write_response(writer, f"OK: hcalory_set_mode {parts[1].lower()}\n".encode())
                return

            if hcalory_cmd == "hcalory_auto_toggle":
                if len(parts) != 1:
                    raise ValueError("Usage: hcalory_auto_toggle")
                await heater.send_hcalory_power_action("hcalory_auto", HCALORY_POWER_AUTO_TOGGLE)
                await write_response(writer, b"OK: hcalory_auto_toggle\n")
                return

            if hcalory_cmd == "hcalory_highland_toggle":
                if len(parts) != 1:
                    raise ValueError("Usage: hcalory_highland_toggle")
                await heater.send_hcalory_power_action("hcalory_highland", HCALORY_POWER_HIGHLAND_TOGGLE)
                await write_response(writer, b"OK: hcalory_highland_toggle\n")
                return

            func = command_mapping.get(cmd)
            if func is None:
                await write_response(writer, f"ERROR: unknown command: {cmd}\n".encode())
                return

            await func()
            await write_response(writer, f"OK: {cmd}\n".encode())
        except Exception as exc:
            logger.exception("Error handling socket client")
            try:
                await write_response(writer, f"ERROR: {exc}\n".encode())
            except (ConnectionResetError, BrokenPipeError):
                pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    server = await asyncio.start_unix_server(handle_client, path=socket_path)
    logger.info("Daemon listening on %s", socket_path)

    stop = asyncio.Event()

    def _stop(*_: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    async with server:
        await stop.wait()
        logger.info("Daemon shutting down...")
        server.close()
        await server.wait_closed()
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass
        await heater.disconnect()
        if os.path.exists(socket_path):
            os.remove(socket_path)
        logger.info("Daemon stopped.")


async def cli_send(address: str, command: str, socket_dir: str) -> int:
    socket_path = socket_path_for_address(address, socket_dir)
    if not os.path.exists(socket_path):
        print("ERROR: daemon not running (socket not found)", file=sys.stderr)
        return 2

    try:
        reader, writer = await asyncio.open_unix_connection(socket_path)
    except Exception as exc:
        print(f"ERROR: cannot connect to daemon: {exc}", file=sys.stderr)
        return 2

    try:
        writer.write((command + "\n").encode())
        await writer.drain()
        resp = await reader.read(-1)
        if not resp:
            print("ERROR: empty response", file=sys.stderr)
            return 2
        print(resp.decode().strip())
        return 0
    finally:
        writer.close()
        await writer.wait_closed()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="hcalory-control")
    parser.add_argument("--address", required=True, help="Bluetooth MAC address of heater")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon and poll data continuously")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging and polling prints")
    parser.add_argument("--max-age", type=float, default=5.0, help="Age in seconds before cached data is stale")
    parser.add_argument("--read-timeout", type=float, default=DEFAULT_READ_TIMEOUT, help="pump_data response timeout")
    parser.add_argument("--bluetooth-timeout", type=float, default=10.0, help="BLE connection timeout per attempt")
    parser.add_argument("--scan-timeout", type=float, default=DEFAULT_SCAN_TIMEOUT, help="BLE scan timeout before device is treated as not found")
    parser.add_argument("--connect-attempts", type=int, default=5, help="BLE connection attempts per polling cycle")
    parser.add_argument("--reconnect-backoff", type=float, default=5.0, help="Initial delay after failed polling/connect")
    parser.add_argument("--reconnect-backoff-max", type=float, default=60.0, help="Maximum delay after repeated failures")
    parser.add_argument("--not-found-backoff-max", type=float, default=20.0, help="Maximum delay when the heater is not advertising")
    parser.add_argument("--socket-dir", default=DEFAULT_SOCKET_DIR, help="Directory for the daemon UNIX socket")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to send in CLI mode")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)

    if args.daemon:
        try:
            asyncio.run(
                run_daemon(
                    args.address,
                    args.interval,
                    args.debug,
                    args.max_age,
                    args.socket_dir,
                    args.read_timeout,
                    args.bluetooth_timeout,
                    args.scan_timeout,
                    args.connect_attempts,
                    args.reconnect_backoff,
                    args.reconnect_backoff_max,
                    args.not_found_backoff_max,
                )
            )
        except KeyboardInterrupt:
            pass
        return

    if not args.command:
        print("ERROR: command required in CLI mode", file=sys.stderr)
        sys.exit(2)

    command = " ".join(args.command)
    code = asyncio.run(cli_send(args.address, command, args.socket_dir))
    sys.exit(code)


if __name__ == "__main__":
    main()
