# Resideo Native v0.3.5

## Schedule editor

- Hour and minute dropdowns replace the time picker that crashes the Home Assistant macOS app. They cover Timed heating, domestic hot water and Geofencing Sleep. Thanks to Alex-ley-scrub for the fix and macOS app test. [PR #10](https://github.com/Kosztyk/resideo_native/pull/10)
- The Timed setup popup stacks fields at narrow widths so both digits remain visible. Sleep changes are captured even when the browser sends only a change event.
- Stored times outside the permitted minute increment stay visible. The editor asks for a valid minute before saving an affected draft.

## T9 and T10 wireless room sensors

- Each accessory reports its own temperature, humidity and motion. Missing individual values remain unknown, and explicit false motion still appears as Off. Thanks to adam0white for the report and fixture. [Issue #11](https://github.com/Kosztyk/resideo_native/issues/11)
- Priority-exclusion flags stay with the accessory that supplied them. Room discovery skips malformed list entries so the remaining accessories can be updated.

## Updating

Update Resideo Native in HACS and restart Home Assistant. For a manual install,
replace `/config/custom_components/resideo_native/` with the complete
`resideo_native` folder from the Home Assistant ZIP. Keep the existing account
configuration. After restarting, refresh Home Assistant and look for
**Editor 0.3.5** in the schedule editor.

[Schedule guide](docs/SCHEDULES.md) · [Room sensor guide](docs/ROOM_SENSORS.md) · [Validation evidence](VALIDATION.md)
