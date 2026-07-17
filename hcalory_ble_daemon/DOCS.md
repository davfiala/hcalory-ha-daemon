# HCalory BLE Daemon

## Configuration

Required:

- `address`: Bluetooth MAC address of the heater.

Useful defaults:

- `socket_dir`: `/config/hcalory`
- `interval`: `2.0`
- `connect_attempts`: `3`
- `bluetooth_timeout`: `8.0`
- `scan_timeout`: `5.0`
- `read_timeout`: `5.0`
- `reconnect_backoff`: `5.0`
- `reconnect_backoff_max`: `60.0`
- `not_found_backoff_max`: `10.0`

## Home Assistant integration

The companion integration should connect to the socket created by the add-on.
For address `EC:B1:B6:05:FB:2A`, use:

```text
/config/hcalory/hcalory-control-ec_b1_b6_05_fb_2a.sock
```

## Notes

The add-on needs access to the host Bluetooth stack through D-Bus and network
capabilities. This is why the add-on requests `host_dbus`, `NET_ADMIN`, and
`NET_RAW`.
