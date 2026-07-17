# HCalory Backlog

## Future improvements

1. Add `binary_sensor.py` to the Home Assistant integration.
   Move boolean states from normal sensors/template YAML to native `BinarySensorEntity`: `connected`, `connecting`, `running`, `cooldown`, `preheating`, `daemon_online`, `data_ok`.

2. Mark value sensors unavailable when data is stale or invalid.
   When `data_status != ok`, temperature, voltage, and setting sensors should probably be unavailable instead of showing old cached values.

3. Move more state logic from YAML into the integration.
   Consider exposing `connection_display`, `data_ok`, translated states, and data availability directly from the integration.

4. Revisit `hcalory_ble.*` services.
   They are fine for one heater. If multiple heaters are added later, services need target/config-entry support, or control should stay button-only.

5. Improve daemon transition logging.
   Log disconnect only on a real `connected -> disconnected` transition, not on every BLE callback.

6. Tune the systemd unit.
   Consider:

   ```ini
   Restart=always
   RestartSec=5
   StartLimitIntervalSec=0
   ```

7. Add daemon socket permissions.
   Add a parameter such as `--socket-mode 660` or `--socket-mode 666` so Home Assistant socket access can be controlled explicitly.

8. Refine dashboard status text.
   Replace the generic "Topeni vypnute nebo neni spojeni" with more specific states like daemon offline, BLE disconnected, waiting for data.

9. Fix YAML diacritics in Home Assistant File Editor.
   Text added through the Windows mount was intentionally written without Czech diacritics to avoid encoding issues.
