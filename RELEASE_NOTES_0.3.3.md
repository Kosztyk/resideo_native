# Resideo Native v0.3.3 — Correct HVAC Idle reporting on Honeywell T6

## Fixed

- Recognize `thermostat.operationStatus.mode = "EquipmentOff"` and report Home Assistant `HVACAction.IDLE` while the thermostat's configured HVAC mode remains enabled.
- When the configured HVAC mode is `Off`, report `HVACAction.OFF` even if the last cloud equipment status has not yet caught up.
- Keep the cloud-provided `Heat`/`Heating`, `Cool`/`Cooling`, and `Fan` statuses mapped to the corresponding active actions.
- Preserve unknown or missing equipment status as unknown instead of guessing an action from room and target temperatures.
- Align the visual schedule editor assets and displayed version with **0.3.3**, including the versioned import URL.

## Root cause and evidence

The Resideo API separates configured mode (`changeableValues.mode`) from current equipment activity (`operationStatus.mode`). Before this fix, v0.3.2 recognized `Heat` but not `EquipmentOff`, so a T6 returning the latter could show only **Heat** in Home Assistant rather than **Idle (Heat)**.

In the owner's Home Assistant 2026.11.1 diagnostics, a physical Jasper/T6 reported:

```json
{
  "mode": "Heat",
  "operation_status": "EquipmentOff",
  "units": "Celsius",
  "api_temperature_units": "Fahrenheit",
  "hold_status": "TemporaryHold",
  "online": true
}
```

This confirms the missing input value against a real device. It does **not** yet confirm v0.3.3 displaying `Idle` on that device after installation. The user-provided screenshots show heating state changing as different setpoints were selected, but the diagnostics are a single snapshot, not a time series.

No thermostat commands, scheduling behavior, network endpoints, credentials, or polling intervals were changed.

## Changed runtime files

- `custom_components/resideo_native/climate.py` — map equipment state to HVAC action.
- `custom_components/resideo_native/const.py` — integration version `0.3.3`.
- `custom_components/resideo_native/manifest.json` — integration version `0.3.3`.
- `custom_components/resideo_native/www/schedule-editor.js` — editor version `0.3.3`.
- `custom_components/resideo_native/www/schedule-entity.js` — version caption and editor import URL `0.3.3`.

## Tests

- `tests/test_hvac_action.py`: 16 parametrized status cases plus unavailable-thermostat check (17 tests total).
- CI also runs the existing Python/HA, editor/browser, HACS and Hassfest checks.

The packaged code was checked for Python syntax, JavaScript syntax and archive integrity. The complete Home Assistant suite and physical post-install behavior must be verified in a suitable environment; do not describe these as passed until they have actually run.

## Installing

**HACS:** update Resideo Native to v0.3.3 after the release is published, then restart Home Assistant and refresh your browser.

**Manual:** replace `/config/custom_components/resideo_native/` with the complete `custom_components/resideo_native/` directory, restart Home Assistant and refresh the browser. Existing account configuration and device entities are retained.

In Developer Tools → States, compare the thermostat's `operation_status` attribute with `hvac_action`. For `mode=Heat` and `operation_status=EquipmentOff`, the expected values are HVAC mode `heat` and HVAC action `idle`.

Related: [issue #7](https://github.com/Kosztyk/resideo_native/issues/7).

## Publication

The existing repository has an Actions workflow which publishes a GitHub Release **only after the current `main` push passes validation**. The publishing script included in the deployment bundle updates its 0.3.2-only gate to 0.3.3. It does not manually create a tag or bypass CI.
