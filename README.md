# HCalory Home Assistant

Home Assistant support for HCalory Bluetooth diesel heaters. The current first
release provides working basic heater control, ventilation mode, Highland mode,
status monitoring, and a compact Lovelace card.

> **First release:** this project is an early, field-tested first release. It
> works with the author's HCalory heater setup, but the Chinese diesel heater
> BLE ecosystem is inconsistent and protocol variants may exist. Expect rough
> edges, keep backups of your Home Assistant configuration, and watch the logs
> when testing new hardware or control flows.

The main component is **HCalory BLE Daemon**, a Home Assistant add-on that keeps
one persistent BLE polling loop alive and exposes a UNIX socket for a companion
custom integration. This avoids opening a new Bluetooth connection for every
sensor update or command.

This repository contains:

- `hcalory_ble_daemon/`: Home Assistant add-on for the persistent BLE daemon.
- `custom_components/hcalory_ble/`: HACS custom integration and compact Lovelace card.
- `heater_slower_socket.py`: standalone daemon source used by the add-on and manual systemd installs.
- `BACKLOG.md`: future improvements.

## How it works

The project is split into three cooperating pieces:

1. **Add-on daemon**  
   Runs next to Home Assistant, owns the Bluetooth connection, polls
   `pump_data`, caches the latest heater frame, and exposes a small UNIX socket
   API. This keeps the heater from being flooded with repeated BLE connects.

2. **Custom integration**  
   Talks only to the daemon socket. It exposes native Home Assistant entities
   for status, diagnostics, control modes, Highland mode, and requested output.
   Home Assistant never needs to open its own BLE connection to the heater.

3. **Lovelace card**  
   Provides a compact dashboard control surface. The card sets desired states;
   the integration then performs the slower physical heater changes in the
   background.

### Control workflow

`Heating`, `Auto`, and `Ventilation` are treated as exclusive control modes.
Turning one mode on first leaves the previously selected mode, then starts the
new one. This prevents Auto and Ventilation from fighting each other.

Auto mode is implemented in the integration, not in a YAML automation. It uses:

- `input_number.hcalory_target_temperature`
- `input_number.hcalory_hysteresis`
- `number.hcalory_ble_requested_setting`

The Auto thresholds are:

- start heating when `ambient <= target - hysteresis`
- stop heating when `ambient >= target + hysteresis`

The requested heater setting is intentionally optimistic. When you set a fan
level, heating power level, or thermostat temperature, the value is shown
immediately as the target. The integration then converges the real heater value
with paced `up`/`down` commands. It sends one step, waits until the daemon data
shows that the heater setting moved, and retries the same step after a timeout
if no change is observed. This protects the BLE module from write flooding while
keeping the UI responsive.

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

## HACS integration

The `hcalory_ble` custom integration talks to the daemon socket and exposes
native Home Assistant sensors, binary sensors, switches, buttons, and a compact
dashboard card.

After installing the repository through HACS and restarting Home Assistant, add
the **HCalory BLE** integration from the UI. With the add-on defaults, enter the
heater BLE address and leave `socket_path` empty.

The included Lovelace card is served by the integration at:

```text
/hcalory_ble_static/hcalory-card.js
```

Card example:

```yaml
type: custom:hcalory-card
```

The card uses the integration entities by default and can also be pointed at
custom helper entities for Auto mode target temperature and hysteresis.

The default card workflow expects these entities:

- `switch.hcalory_ble_heating`
- `switch.hcalory_ble_auto_mode`
- `switch.hcalory_ble_ventilation`
- `number.hcalory_ble_requested_setting`
- `input_number.hcalory_target_temperature`
- `input_number.hcalory_hysteresis`

## Credits

The HCalory BLE protocol work is based on and inspired by Evan Foster's
projects:

- `evanfoster/hcalory-control`
- `evanfoster/hcalory-ble`

See `NOTICE.md` before publishing.
