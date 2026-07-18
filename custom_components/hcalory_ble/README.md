# HCalory BLE

Socket-based Home Assistant integration for the HCalory BLE daemon.

The current first release provides working basic heater control, ventilation
mode, Highland mode, status monitoring, and a compact Lovelace card backed by
the daemon socket.

> First release note: this integration is still young and may have bugs. It has
> been tested against one known HCalory BLE heater/protocol variant. If your
> heater behaves differently, enable debug logging on the add-on and compare the
> daemon `pump_data` fields before relying on unattended control.

The integration expects the daemon add-on to provide a UNIX socket and exposes:

- status sensors for heater state, mode, setting, temperatures, voltage, and diagnostics
- heater error code diagnostics exposed as `sensor.hcalory_ble_heater_error_code`
- binary sensors for service/BLE/data connectivity and heater runtime states
- switches for exclusive Heating, Auto, Ventilation, and Highland mode
- buttons for mode changes, setting up/down, and forced refresh
- a requested-setting number entity with paced background convergence
- `custom:hcalory-card`, a compact Lovelace control card

## Architecture

The integration does not talk to Bluetooth directly. It connects to the add-on
daemon UNIX socket and merges three daemon responses:

- `daemon_status`: process/socket health
- `heater_status`: BLE connection state
- `pump_data`: cached heater frame and parsed values

This keeps Home Assistant responsive even when the heater is powered off,
booting, or temporarily not advertising.

`sensor.hcalory_ble_heater_error_code` is parsed from the heater frame and
represents heater-side errors such as `E-01`/`E-02` style codes. It is separate
from `sensor.hcalory_ble_last_error`, which reports daemon/socket/BLE
communication errors.

Known heater error meanings:

| Code | Meaning |
| --- | --- |
| `E-01` | General error |
| `E-02` | Low / high voltage |
| `E-03` | Glow plug |
| `E-04` | Fuel pump |
| `E-05` | Overheat |
| `E-06` | Fan |
| `E-07` | Communication |
| `E-08` | No fuel / flame-out |
| `E-09` | Sensor |
| `E-10` | Ignition failure |

## Control modes

The three main control modes are exclusive:

- `switch.hcalory_ble_heating`
- `switch.hcalory_ble_auto_mode`
- `switch.hcalory_ble_ventilation`

Turning one on first leaves the previous mode. This prevents situations where
Auto mode and Ventilation both try to control the heater.

`switch.hcalory_ble_heating` means "manual heating mode is selected". The
physical runtime state is still exposed separately by binary sensors such as
`binary_sensor.hcalory_ble_running`, `binary_sensor.hcalory_ble_cooldown`, and
`binary_sensor.hcalory_ble_preheating`.

## Auto mode

Auto mode is handled by the integration. It uses the ambient temperature from
the daemon and these helper entities:

```text
input_number.hcalory_target_temperature
input_number.hcalory_hysteresis
```

The thresholds are:

- start heating at or below `target - hysteresis`
- stop heating at or above `target + hysteresis`

When Auto starts the heater it requests gear/power mode. The desired power level
comes from:

```text
number.hcalory_ble_requested_setting
```

## Requested setting workflow

The heater only has reliable `up` and `down` controls for fan level, heating
power, and thermostat temperature. The integration therefore exposes a desired
setting as a `number` entity:

```text
number.hcalory_ble_requested_setting
```

The entity is optimistic: the target value is shown immediately in the UI. The
integration then adjusts the real heater value in the background:

1. read current `heater_setting`
2. send one `up` or `down` command
3. wait until `pump_data` shows that the setting moved
4. send the next step only after that movement is observed
5. retry the same step if no movement is seen after the timeout

This avoids flooding the BLE module with writes while still making the UI feel
responsive.

The requested setting represents different physical values depending on mode:

- Ventilation: fan level `1..6`
- Heating power: power level `1..6`
- Thermostat: temperature `15..28 °C`
- Auto: heating power level `1..6`

Minimal card configuration:

```yaml
type: custom:hcalory-card
```

Auto mode helper defaults:

```yaml
input_number.hcalory_target_temperature
input_number.hcalory_hysteresis
```
