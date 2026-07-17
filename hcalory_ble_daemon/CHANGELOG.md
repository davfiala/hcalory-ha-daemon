# Changelog

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
