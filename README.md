# HCalory Home Assistant Add-on

Home Assistant support for HCalory Bluetooth diesel heaters.

The main component is **HCalory BLE Daemon**, a Home Assistant add-on that keeps
one persistent BLE polling loop alive and exposes a UNIX socket for a companion
custom integration. This avoids opening a new Bluetooth connection for every
sensor update or command.

This repository contains:

- `hcalory_ble_daemon/`: Home Assistant add-on for the persistent BLE daemon.
- `heater_slower_socket.py`: standalone daemon source used by the add-on and manual systemd installs.
- `BACKLOG.md`: future improvements.

## Add-on

Add this repository as a Home Assistant add-on repository, then install
**HCalory BLE Daemon**.

The add-on writes its UNIX socket to `/config/hcalory` by default. For a heater
with address `EC:B1:B6:05:FB:2A`, the companion integration should use:

```text
/config/hcalory/hcalory-control-ec_b1_b6_05_fb_2a.sock
```

## Configuration

The add-on configuration page contains detailed descriptions for every runtime
parameter. In most installations only `address` needs to be changed.

Recommended defaults:

- `interval`: `2.0`
- `connect_attempts`: `3`
- `bluetooth_timeout`: `8.0`
- `scan_timeout`: `5.0`
- `read_timeout`: `5.0`
- `not_found_backoff_max`: `10.0`
- `debug`: `false`

## Credits

The HCalory BLE protocol work is based on and inspired by Evan Foster's
projects:

- `evanfoster/hcalory-control`
- `evanfoster/hcalory-ble`

See `NOTICE.md` before publishing.
