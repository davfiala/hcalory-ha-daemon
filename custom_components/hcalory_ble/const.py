"""Constants for the HCalory BLE integration."""

from __future__ import annotations

DOMAIN = "hcalory_ble"
NAME = "HCalory BLE"

DEFAULT_SOCKET_DIR = "/config/hcalory"
DEFAULT_POLL_INTERVAL = 1.0

STATIC_URL_PATH = "/hcalory_ble_static"
CARD_FILENAME = "hcalory-card.js"
CARD_RESOURCE_URL = f"{STATIC_URL_PATH}/{CARD_FILENAME}"

PLATFORMS = ["sensor", "binary_sensor", "button", "switch", "number"]


def socket_path_for_address(address: str, socket_dir: str = DEFAULT_SOCKET_DIR) -> str:
    """Build the daemon socket path for a heater BLE address."""
    clean = address.lower().replace(":", "_")
    return f"{socket_dir}/hcalory-control-{clean}.sock"
