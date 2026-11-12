# Resideo Native v0.3.3 — changed file inventory

Relative to the public v0.3.2 release, this bundle deploys:

## Integration

- `custom_components/resideo_native/climate.py` — map `EquipmentOff` to `Idle`, prioritize configured `Off`, preserve real action statuses.
- `custom_components/resideo_native/const.py` — version 0.3.3.
- `custom_components/resideo_native/manifest.json` — version 0.3.3.
- `custom_components/resideo_native/www/schedule-editor.js` — editor version 0.3.3.
- `custom_components/resideo_native/www/schedule-entity.js` — editor caption/import version 0.3.3.

All other integration files are bundled unchanged from the uploaded v0.3.3 package.

## Tests and metadata

- `tests/test_hvac_action.py` **new** — 17 status variants and unavailable-device test.
- `tests/test_homeassistant.py`, `tests/test_packaging.py`, `tests/test_review_evidence.py` — expected version updated to 0.3.3.
- `tools/check_repository.py` — expected version updated to 0.3.3.
- `package.json`, `package-lock.json` — root test package version updated to 0.3.3.
- `.github/workflows/release.yml` — release name, concurrency and publishing gate updated to 0.3.3.
- `.github/workflows/validate.yml` — unchanged; automatically discovers the new Python regression test.

## Documentation

- `README.md` — add explanation of Heat versus Heating versus Idle; fix current editor link/version.
- `CHANGELOG.md` — prepend 0.3.3 release entry.
- `START_HERE.md` — add 0.3.3 update instructions, retain historical 0.3.2 details.
- `VALIDATION.md` — add v0.3.3 evidence and limits, retain past evidence.
- `HACS_PUBLISHING.md` — update publishing workflow instructions.
- `CHANGED_FILES.md` — replace current-version inventory with this file.
- `RELEASE_NOTES_0.3.3.md` **new** — complete notes.
- `docs/HVAC_IDLE_STATUS_v0.3.3.md` **new** — source evidence, mapping and diagnostics.

The included `tools/apply_release.py` performs these merges against a fresh clone
of the public repository to **preserve all unchanged repository files**, older
release notes, historical details, tests, workflows and UI assets.
