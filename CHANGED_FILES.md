# Resideo Native v0.3.5 changed files

- `www/schedule-editor.js` renders hour/minute dropdowns, handles Sleep selection events, and responds to the width available in the editor and setup popup.
- `protocol/rooms.py` keeps measurements and priority-exclusion flags tied to their wireless accessory and skips malformed accessory entries.
- `const.py`, `manifest.json` and the two frontend modules use the stable version. `package.json`, `package-lock.json` and `.github/workflows/release.yml` use the same release version.
- `tools/check_repository.py` accepts stable and prerelease manifest versions. The tests cover metadata, diagnostics, the browser popup, and individual room readings and flags.
- `README.md`, `START_HERE.md`, `CHANGELOG.md`, `VALIDATION.md`, `HACS_PUBLISHING.md`, `docs/SCHEDULES.md`, `docs/ROOM_SENSORS.md` and `RELEASE_NOTES_0.3.5.md` document the changes and update instructions.
