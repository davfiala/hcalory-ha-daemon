# HCalory Home Assistant

Work-in-progress Home Assistant support for HCalory BLE diesel heaters.

This repository currently contains:

- `hcalory_ble_daemon/`: Home Assistant add-on skeleton for the persistent BLE daemon.
- `heater_slower_socket.py`: standalone daemon source used by the add-on and manual systemd installs.
- `BACKLOG.md`: future improvements.

## Add-on

Add this repository as a Home Assistant add-on repository, then install
**HCalory BLE Daemon**.

The add-on writes its UNIX socket to `/config/hcalory` by default.

## Credits

The HCalory BLE protocol work is based on and inspired by Evan Foster's
projects:

- `evanfoster/hcalory-control`
- `evanfoster/hcalory-ble`

See `NOTICE.md` before publishing.
