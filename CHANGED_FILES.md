# Resideo Native v0.3.6 changes since v0.3.6b1

- `custom_components/resideo_native/protocol/device.py`: explicit Jasper fallback, conflicting/malformed identifier rejection, reverse fan mapping.
- `custom_components/resideo_native/climate.py`: confirmed fan activity while configured Off, reverse mapping and imports.
- `custom_components/resideo_native/binary_sensor.py`: typed fan sensor property and discovery callback; no entity ID changes.
- `tests/test_protocol.py`, `tests/test_homeassistant.py`, `tests/test_hvac_action.py`, `tests/test_review_evidence.py`: new regressions and release gate checks.
- `custom_components/resideo_native/const.py`, `manifest.json` (in component), `www/schedule-editor.js`, `www/schedule-entity.js`, `package.json`, `package-lock.json`: stable version synchronization only.
- `.github/workflows/release.yml`: exact stable 0.3.6 publication gate; current-main and successful-validation safeguards retained.
- `README.md`, `START_HERE.md`, `CHANGELOG.md`, `VALIDATION.md`, `HACS_PUBLISHING.md`, `docs/SCHEDULES.md`, `docs/FAN_CONTROL.md`, `RELEASE_NOTES_0.3.6b1.md`, `RELEASE_NOTES_0.3.6.md`, `CHANGED_FILES.md`: documentation and reported hardware evidence.

All other files retain the supplied v0.3.6b1 contents, including `protocol/client.py`, `coordinator.py`, authentication, hot-water, room priority and schedule logic. No repository change or publication was made.
