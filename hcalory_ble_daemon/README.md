# HCalory BLE Daemon

Persistent Bluetooth daemon for HCalory diesel heaters in Home Assistant.

The add-on keeps a single BLE connection and polling loop alive, then exposes
the current heater state through a UNIX socket. The companion Home Assistant
integration can read from that socket quickly without opening a new Bluetooth
connection for every command or sensor update.

## Why this add-on exists

Some HCalory Bluetooth modules are slow to accept connections and can disappear
briefly while the heater is powered off or waking up. A persistent daemon makes
the system calmer: it handles reconnects in one place, caches the last valid
`pump_data`, and reports whether the daemon, the heater connection, and the
latest data are healthy.

## Quick start

1. Install the add-on from this repository.
2. Open the add-on **Configuration** tab.
3. Set `address` to the heater Bluetooth MAC address, for example
   `EC:B1:B6:05:FB:2A`.
4. Start the add-on and check the log for `Daemon listening on ...`.
5. Point the companion custom integration to the socket path shown below.

For the companion custom integration, use this socket path:

```text
/config/hcalory/hcalory-control-ec_b1_b6_05_fb_2a.sock
```

Replace the MAC address part with your heater address in lowercase and colons
changed to underscores.

Example:

```text
EC:B1:B6:05:FB:2A -> /config/hcalory/hcalory-control-ec_b1_b6_05_fb_2a.sock
```

## Recommended defaults

The bundled defaults are intentionally conservative and work well for a heater
that may be power-cycled:

- Poll every `2` seconds while the heater is reachable.
- Try up to `3` BLE connection attempts per reconnect cycle.
- Retry quickly when the heater is simply not advertising yet.
- Keep normal logs quiet; enable `debug` only while diagnosing a problem.

Detailed descriptions for every option are available on the add-on
**Configuration** tab.
