# Fan control (introduced in v0.3.6)

## Native protocol and scope

Android 6.21.2 `Dd/d.c` constructs `POST api/v2/locations/{locationId}/devices/{deviceId}/fan/changeableValues` with `{"mode":"On"}` (or `Auto`, `Circulate`). `y9/u.c` applies model-specific hold handling; Jasper uses the mode-only path. Optional `HoldStatus` and `HoldUntil` are omitted here. Never use the thermostat changeableValues endpoint as fallback. No separate developer key or login is required. The existing HTTP client, lock and authentication are reused. Read-back checks the reported fan mode with the existing bounded GET retries, without replaying the write for stale state. The existing authentication retry policy is unchanged.

Home Assistant Core Lyric 2026.11.0 maps `Circulate` to `diffuse`, and aiolyric 2.2.1 sends a mode-only body to its separate public API endpoint. Resideo Native instead uses the native mobile endpoint above. `settings.fan.allowedModes` and `settings.fan.changeableValues.mode` are read from the existing locations response. Only explicitly identified Jasper with at least one recognized advertised mode receives writable climate fan modes. A generic deviceType (for example Thermostat or Unknown) may fall back to an exact Jasper deviceModel; a known conflicting family or an unrecognized non-generic deviceType blocks writes. Malformed identifiers are rejected. Unknown or malformed capabilities are ignored; `FollowSchedule` and fan speed are not writable. Other models may have different hold semantics and are intentionally not given fan-mode controls. No additional polling endpoint is introduced.

`settings.fan.fanRunning` is used only when it is a JSON boolean. A binary sensor appears when a valid value is first observed; missing later values are unknown. `thermostat.operationStatus.fanRequest` and `circulationFanRequest` are whitelisted in diagnostics but not treated as actual motor activity. When HVAC is enabled, heating/cooling take precedence and a known idle equipment status plus explicit fanRunning=true becomes HVAC fan action. When configured HVAC is Off, explicit fanRunning=true reports Fan without changing the configured mode; otherwise Off suppresses stale operation status. Other models can expose read-only activity if the same schema is present.

## Manual test plan for issue #13

Install the current validated stable release through HACS, or use the manual installation ZIP from [GitHub Releases](https://github.com/Kosztyk/resideo_native/releases) after backing up the previous component. Restart HA. Choose one Jasper thermostat initially. Record firmware, fan modes, current fan, HVAC mode, target temperatures, hold status, hold expiration and schedule status. Do not edit the schedule while testing a fan command.

1. With Permanent Hold active, change Auto → On → Circulate (`diffuse`) → Auto via `climate.set_fan_mode`. After each change, wait for fresh polling and verify in the official app and HA that only fan mode changed. Repeat with Temporary Hold/HoldUntil and while following schedule, if safe and appropriate. Test Heat, Cool, Heat/Cool and Off only where supported and appropriate.
2. Change fan mode at the wall and in the app; HA must reflect the new supported mode after a fresh poll. Check that an unsupported or missing fan capability does not create a writable selector.
3. During Circulate, observe actual fan-running indication if the cloud supplies it. Heating/cooling should take precedence over fan action; when HVAC is enabled but idle, or configured HVAC is Off, explicit fanRunning=true should show Fan without changing HVAC mode. Missing status is unknown, never inferred from Circulate or fanRequest.
4. Confirm room priority, individual room readings, setpoints, holds, schedule editor and DHW continue to work on applicable devices. Stop and report if hold or setpoints change unexpectedly. Do not automatically restore a hold because another user may have intentionally changed it.
5. Share sanitized diagnostics and relevant logs, not tokens, account identifiers or raw responses. Note model, firmware, region and which tests passed/failed. Restore the v0.3.5 component folder and restart to roll back if needed.

Example service call (replace the entity ID):

```yaml
action: climate.set_fan_mode
target:
  entity_id: climate.thermostat
data:
  fan_mode: diffuse
```

## Hardware evidence (v0.3.6b1, issue #13)

The reporter tested three Jasper heat/cool thermostats on HA 2026.11.0 (Docker, US account). All showed Auto/On/Diffuse correctly. Tested transitions were Auto → On → Diffuse → Auto and Diffuse → On → Diffuse. Confirmation took about 10–20 seconds with no warnings. Permanent Hold, Heat and setpoints remained unchanged; a temporarily raised setpoint was preserved, and setpoint changes with fan On retained Permanent Hold. No fan-running binary sensor appeared and HVAC action did not report Fan during Circulate. This suggests no usable fanRunning telemetry was reported; no raw diagnostics were supplied. The optional sensor is not required for mode control.

The mode-only POST is unchanged in v0.3.6. Cooling operation, Temporary Hold/HoldUntil, scheduled operation, external change propagation after initial discovery, the expanded model fallback and Off-mode positive telemetry behavior are not separately confirmed on hardware. Synthetic tests do not establish those real-world behaviors.
