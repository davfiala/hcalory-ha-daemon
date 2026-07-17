# Changelog

## 0.1.11

- Add precise voltage fields: `voltage_raw` and `voltage_v`.
- Include `protocol_version` in `pump_data` and log the active parser version on daemon start.
- Remove unverified altitude query/set commands and the old `hcalory_altitude_toggle` alias.
- Keep the confirmed `hcalory_highland_toggle` command and decoded `highland_mode` field.

## 0.1.10

- Add `hcalory_highland_toggle` as the explicit socket command for Highland mode.
- Keep `hcalory_altitude_toggle` as a compatibility alias.
- Decode `highland_mode` and `highland_mode_raw` from `pump_data`.

## 0.1.9

- Add experimental altitude query and set-altitude socket commands.
- Expose the raw high-altitude mode byte from `pump_data`.

## 0.1.8

- Add experimental Hcalory socket commands for direct gear, temperature, unit, mode, auto start/stop, and altitude toggles.
- Keep existing stable command names unchanged.

## 0.1.7

- Extend `pump_data` parsing with Hcalory status nibbles, running step, temperature unit, auto start/stop, and error code fields.
- Derive running, cooldown, and preheating flags from the decoded Hcalory status where available.

## 0.1.6

- Expand add-on documentation with setup steps, socket path guidance, and troubleshooting notes.
- Add more detailed configuration descriptions for the Home Assistant add-on settings page.
- Add Czech configuration translations.

## 0.1.5

- Limit pre-built GHCR image publishing to `amd64` and `aarch64`, matching the available Home Assistant base image platforms.

## 0.1.4

- Remove unsupported `armhf`/`linux/arm/v6` image build target from GHCR publishing.

## 0.1.3

- Publish the add-on as a pre-built GHCR image instead of relying only on local Supervisor builds.

## 0.1.2

- Recognize heater state value `1` as `standby`.
- Prevent valid standby frames from being treated as polling failures.

## 0.1.1

- Add missing `bluetooth-adapters` Python dependency required by `bleak-retry-connector`.

## 0.1.0

- Initial Home Assistant add-on packaging for the HCalory BLE daemon.
- Add configurable Bluetooth address, socket directory, polling interval, reconnect backoff, and debug logging.
