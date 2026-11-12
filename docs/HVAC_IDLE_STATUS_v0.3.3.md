# Honeywell T6/Jasper HVAC activity states (v0.3.3)

The thermostat's **configured mode** (`changeableValues.mode`) and **active equipment state** (`operationStatus.mode`) are independent.

| Configured HVAC mode | Resideo `operationStatus.mode` | HA `hvac_action` |
| --- | --- | --- |
| Heat | Heat / Heating | heating |
| Heat | EquipmentOff / Idle / Off / None | idle |
| Cool | Cool / Cooling | cooling |
| Heat or Cool | Fan | fan |
| Off | Any status (even stale Heat) | off |
| Heat or Cool | Unknown / missing | unknown (`None`) |

Example: 25 °C in the room with a 16 °C setpoint, heating mode still selected:

```json
{"mode":"Heat", "operation_status":"EquipmentOff"}
```

Expected display: **Idle (Heat)**, subject to Home Assistant UI language/card formatting.

### Why no temperature-based inference?

Honeywell T6 thermostats can cycle heat demand as part of their control algorithm, including hysteresis/TPI behavior. A comparison like `current_temperature > setpoint` cannot reliably prove equipment relay state. This integration relies on Resideo's device-reported `operationStatus` and does not override it using setpoint differences.

### Test evidence and limitations

- Home Assistant 2026.11.1 diagnostics from a real Jasper/T6 running **v0.3.2** showed `mode: Heat` and `operation_status: EquipmentOff`, with `last_update_success: true`. This demonstrates that the API provides the exact status missing from the old mapping.
- The v0.3.3 code now recognizes that status; the included regression test cases cover known, unknown, and Off-mode statuses.
- There is no confirmed physical-device post-install result for v0.3.3 in the supplied evidence. Nor does this change the thermostat's physical display or boiler controls.
- If the API returns `Heat` despite the equipment being inactive, a different investigation and time-sequenced diagnostics are needed.

### Safe troubleshooting procedure

1. Open **Developer Tools → States** and locate the `climate` entity.
2. Observe `hvac_action`, `operation_status`, `resideo_mode`, `temperature`, and `current_temperature` after a regular account poll.
3. Compare with the official Resideo app and physical thermostat. Do not publish access tokens or raw account/network captures.
4. Attach redacted integration diagnostics to [issue #7](https://github.com/Kosztyk/resideo_native/issues/7) if the discrepancy persists.
