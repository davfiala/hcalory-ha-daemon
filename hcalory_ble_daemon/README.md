# HCalory BLE Daemon

Persistent BLE daemon for HCalory diesel heaters.

This add-on keeps one Bluetooth connection/polling loop alive and exposes a
UNIX socket for the Home Assistant integration.

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
