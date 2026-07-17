# Changelog

## 0.1.2

- Recognize heater state value `1` as `standby`.
- Prevent valid standby frames from being treated as polling failures.

## 0.1.1

- Add missing `bluetooth-adapters` Python dependency required by `bleak-retry-connector`.

## 0.1.0

- Initial Home Assistant add-on packaging for the HCalory BLE daemon.
- Add configurable Bluetooth address, socket directory, polling interval, reconnect backoff, and debug logging.
