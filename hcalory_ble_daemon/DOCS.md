# HCalory BLE Daemon

This add-on runs a small persistent daemon for HCalory Bluetooth diesel heaters.
It keeps Bluetooth handling outside the Home Assistant integration, maintains a
cached `pump_data` response, and exposes a UNIX socket that the integration can
query without repeatedly reconnecting to the heater.

## What it provides

- One long-running BLE polling loop for the heater.
- Automatic reconnects when the heater is powered off, out of range, or slow to
  wake up.
- A UNIX socket under `/config/hcalory` by default.
- Lightweight status commands for the companion integration:
  `daemon_status`, `heater_status`, and `pump_data`.
- Quiet normal logging, with optional debug output when needed.

## Installation

1. Add this GitHub repository as a Home Assistant add-on repository.
2. Install **HCalory BLE Daemon**.
3. Open the add-on **Configuration** tab.
4. Set `address` to the Bluetooth MAC address of the heater.
5. Start the add-on.
6. Check the log for a line similar to:

```text
Daemon listening on /config/hcalory/hcalory-control-ec_b1_b6_05_fb_2a.sock
```

## Companion integration socket path

The companion custom integration should connect to the socket created by the
add-on.

For address `EC:B1:B6:05:FB:2A`, use:

```text
/config/hcalory/hcalory-control-ec_b1_b6_05_fb_2a.sock
```

The socket name is created from the MAC address by lowercasing it and replacing
colons with underscores:

```text
EC:B1:B6:05:FB:2A -> ec_b1_b6_05_fb_2a
```

## Configuration

### Required

| Option | Default | Description |
| --- | --- | --- |
| `address` | `null` | Bluetooth MAC address of the heater, for example `EC:B1:B6:05:FB:2A`. The add-on cannot start without this value. |

### Socket and polling

| Option | Default | Description |
| --- | --- | --- |
| `socket_dir` | `/config/hcalory` | Directory where the UNIX socket is created. Keep this under `/config` so the Home Assistant companion integration can reach it. |
| `interval` | `2.0` | Seconds between regular `pump_data` polls while the heater is reachable. Lower values make the UI react faster but increase BLE traffic. |

### Bluetooth timing

| Option | Default | Description |
| --- | --- | --- |
| `connect_attempts` | `3` | Number of BLE connection attempts in one reconnect cycle. Increasing this can help with weak signal, but each failed cycle takes longer. |
| `bluetooth_timeout` | `8.0` | Timeout in seconds for a BLE connection attempt. Use a higher value only if the heater is known to connect slowly. |
| `scan_timeout` | `5.0` | Time spent looking for the heater before treating it as not found. A short value keeps reconnect cycles responsive after power-on. |
| `read_timeout` | `5.0` | Time to wait for a response after sending a command or `pump_data` request. Increase only if responses are valid but consistently slow. |

### Reconnect behavior

| Option | Default | Description |
| --- | --- | --- |
| `reconnect_backoff` | `5.0` | Initial delay after a failed poll or connection attempt. |
| `reconnect_backoff_max` | `60.0` | Maximum delay after repeated failures that are not a simple "heater not found" case. |
| `not_found_backoff_max` | `10.0` | Maximum delay when the heater is powered off or not advertising. Keeping this lower helps the daemon reconnect sooner after the heater is powered on again. |

### Logging

| Option | Default | Description |
| --- | --- | --- |
| `debug` | `false` | Enables verbose logs with socket commands, raw frames, and cached responses. Leave disabled for normal use, especially on systems with limited storage or memory. |

## Notes

The add-on needs access to the host Bluetooth stack through D-Bus and network
capabilities. This is why the add-on requests `host_dbus`, `NET_ADMIN`, and
`NET_RAW`.

## Troubleshooting

### The add-on starts, but the integration has no data

Check that the integration socket path exactly matches the add-on address. The
MAC address part must be lowercase and use underscores instead of colons.

### The heater is powered off

This is expected to show as disconnected or not found. The daemon keeps running
and retries periodically. With the default `not_found_backoff_max` of `10`
seconds, it should notice the heater again shortly after power is restored.

### The log is too noisy

Disable `debug`. Normal operation should only log startup, reconnects, warnings,
and sent control commands.

### The first connection takes longer after power-on

Some heater BLE modules advertise intermittently while booting. The daemon may
need one or more reconnect cycles before the module is ready. If this happens
often, keep `not_found_backoff_max` low and avoid setting `scan_timeout` too
high.
