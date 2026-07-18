"""UNIX socket client for the HCalory BLE daemon."""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any


class DaemonError(RuntimeError):
    """Raised when the daemon cannot be reached or returns invalid data."""


class DaemonClient:
    """Small async client for the daemon line-based UNIX socket protocol."""

    def __init__(self, socket_path: str, connect_timeout: float = 1.0) -> None:
        self.socket_path = socket_path
        self.connect_timeout = connect_timeout
        self._cache: dict[str, Any] | None = None
        self._cache_ts: float = 0.0

    async def _open_connection(self, timeout: float) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        if not os.path.exists(self.socket_path):
            raise DaemonError(f"Socket not found: {self.socket_path}")
        try:
            return await asyncio.wait_for(asyncio.open_unix_connection(self.socket_path), timeout=timeout)
        except (OSError, asyncio.TimeoutError) as err:
            raise DaemonError(f"Cannot open socket {self.socket_path}: {err}") from err

    async def _send_raw(self, payload: str, timeout: float = 3.0) -> str:
        reader, writer = await self._open_connection(timeout=self.connect_timeout)
        try:
            writer.write((payload + "\n").encode())
            await writer.drain()
            try:
                data = await asyncio.wait_for(reader.read(-1), timeout=timeout)
            except asyncio.TimeoutError as err:
                raise DaemonError("Timeout waiting for daemon response") from err
            if not data:
                raise DaemonError("Empty response from daemon")
            return data.decode().strip()
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _send_json(self, payload: str, timeout: float = 3.0) -> dict[str, Any]:
        text = await self._send_raw(payload, timeout=timeout)
        try:
            data = json.loads(text)
        except Exception as err:
            raise DaemonError(f"Invalid JSON from daemon: {err}; raw={text!r}") from err
        if not isinstance(data, dict):
            raise DaemonError(f"Unexpected JSON from daemon: {data!r}")
        return data

    async def command(self, cmd: str, timeout: float = 3.0) -> str:
        """Send a command and require OK/error style daemon response."""
        text = await self._send_raw(cmd, timeout=timeout)
        if text.startswith("OK:"):
            return text
        if text.startswith("ERROR:"):
            raise DaemonError(text)
        return text

    async def get_daemon_status(self, timeout: float = 2.0) -> dict[str, Any]:
        return await self._send_json("daemon_status", timeout=timeout)

    async def get_heater_status(self, timeout: float = 2.0) -> dict[str, Any]:
        return await self._send_json("heater_status", timeout=timeout)

    async def get_pump_data(self, force: bool = False, timeout: float = 3.0) -> dict[str, Any]:
        return await self._send_json("pump_data_force" if force else "pump_data", timeout=timeout)

    async def get_status(self, force: bool = False, timeout: float = 3.0) -> dict[str, Any]:
        """Return merged daemon, heater, and pump data."""
        now = time.time()
        if not force and self._cache is not None and (now - self._cache_ts) < 0.5:
            return self._cache

        data: dict[str, Any] = {}
        data.update(await self.get_daemon_status(timeout=timeout))
        data.update(await self.get_heater_status(timeout=timeout))

        pump_data = await self.get_pump_data(force=force, timeout=timeout)
        if "error" in pump_data:
            data["pump_data_error"] = pump_data.get("error")
        else:
            data.update(pump_data)

        self._cache = data
        self._cache_ts = now
        return data
