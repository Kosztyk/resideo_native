# Resideo Native 0.3.1 — heating/DHW schedules and visual controls

Adds heating and hot-water cloud schedule management, consolidating today's
local builds into the first GitHub release after 0.1.8.

- Read/edit schedules through Home Assistant actions or the visual editor;
  add/remove periods, clear eligible days, copy routines and export/import backups.
- A visible Schedule editor entity, native Heating schedule On/Off switch,
  Geofencing left/right switch with setup/review popups and optional sidebar
  shortcut (Off by default).
- Shared Home/Away and sleep editing, with the final Android trigger-based
  sleep serializer corrected from 0.3.0.
- EMEA field filtering, DHW 10-minute validation, fresh revisions, per-day
  merging and bounded GET verification after a single PUT.
- Error drafts remain available; opening setup or editing a draft sends no command.
  No default household routine is installed and uncertain PUTs are not replayed.

## Hardware verification

ryanpalfrey confirms 0.3.1 on **two UK/EMEA Lyric T6R T6H700RW4011 thermostats,
firmware 6.0.1.50, HA OS 2026.10.4**, with real downstairs hot water:

- Heating reads, period/day deletion and restoration: verified writes, other
  days unchanged, restored weeks compared to baseline.
- DHW 07:00 → 07:10 edit, day clearing/restoration: applied and verified;
  07:05 rejected before sending.
- An HA-started DHW boost ran normally; auto/off were exercised.
- Real HVAC Off was accepted and reported on both heating zones.

The maintainer separately reports working Geofencing. The requester's visual
editor/popup, Geofencing/sleep and first-time creation/conversion were not tested.
Specific live sleep acceptance, individual boost durations and explicit boost
cancellation remain outside the supplied evidence. The reported permanent-hold
workaround is temperature first, then Permanent hold; no new fix is claimed.

Frost protection remains the thermostat's native Off behavior. No frost switch,
substitute heat hold or invented cloud frost reading is added.

[Complete implementation/test summary and evidence links](https://github.com/Kosztyk/resideo_native/blob/v0.3.1/docs/TESTING_2026-10-27.md)

## Install

Update through HACS, or replace the complete
`/config/custom_components/resideo_native/` folder. Restart Home Assistant and
refresh the browser; confirm **Editor 0.3.1**. Keep the existing account entry.
The obsolete Geofencing Press entity is removed; the native left/right switch
provides the reviewed setup flows. Phone geofencing stays configured in the app.

Local validation: **230 Python/HA tests plus 55 subtests, 36 JavaScript tests,
49 Chromium checks**, packaging and compilation. HACS/Hassfest and the full
remote validation run must pass before this release is published. The exact
validated commit and run are appended below by the release workflow.
