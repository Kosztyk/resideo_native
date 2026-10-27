# 0.3.1 — Geofencing switch, two popup flows and sleep

Use your existing thermostats one at a time. The maintainer uses
`climate.kosz_thermostat_2`; the requester has `climate.upstaires` and
`climate.downstaires`. Select the corresponding switch on each device page.
Hot-water schedules are outside this mode-switch test.

## Install and baseline

- [ ] Replace the complete integration folder, restart HA and refresh the browser.
- [ ] The old **Switch to Geofencing** Press entity is gone.
- [ ] **Switch to Geofencing** is a left/right switch beside **Heating schedule**.
- [ ] The popup/full page reports **Editor 0.3.1**.
- [ ] Record app schedule type, native schedule On/Off, holds and other zones.
- [ ] Export the full timed week before changing type. Keep the backup to restore.
- [ ] Phone geofencing is configured in the Resideo app.

The Heating schedule switch controls native enabled/disabled status. The
Geofencing switch selects type: On = Geofence, Off = Timed. It must not publish
a new type before confirmed cloud readback. App-side changes should be observed
by the once-per-minute type read or a fresh schedule action read.

## On: geofencing 1 → geofencing 2

1. From Timed, move **Switch to Geofencing** right/On.
2. Confirm a **Geofencing setup** popup opens over the current HA page.
3. The first screen has Home/Away temperatures. Returned values may be prefilled;
   omitted values must be blank. Enter your own values.
4. Click **Cancel** once. Confirm app and switch remain Timed/Off and periods match
   the backup. Reopen and ensure cancelled edits were not sent.
5. Enter values again. Optionally create sleep as below.
6. Click **Review & save**. This must show Home/Away (and sleep, if supplied), a
   type-change confirmation checkbox, **Back to draft** and **Save to Resideo**.
7. Go Back once and check the draft values remain. Return to review, confirm and
   Save once. Do not edit in the app while saving.
8. After verified readback, the popup closes and the switch reports On.
9. Refresh the official app. Confirm selected Geofence type, Home/Away/sleep
   values, native schedule status/hold and other zones. Record any discrepancy.

## Sleep settings in the popup

- [ ] Click **Create Sleep Settings** on the Home/Away screen.
- [ ] Enter Sleep start, Sleep end and Night temperature from your desired routine.
- [ ] An overnight period is accepted; equal start/end is rejected before writing.
- [ ] **Save sleep settings** returns to the profile draft and sends no cloud write.
- [ ] Review displays the intended start/end/night temperature.
- [ ] Final profile Save is verified against the app's Sleep screen.
- [ ] Reopen/Edit and check the returned sleep values match.

## Off: timed 1 → timed 2

1. From Geofence/On, move the same switch left/Off.
2. Confirm a **Timed schedule setup** popup opens on the current HA page.
3. It shows the week/period editor. Use returned inactive periods if present;
   otherwise enter your own routine. A backup can be imported through the full
   Schedule editor if you prefer. No sample routine should appear automatically.
4. Cancel once; verify the switch/app remain Geofence/On.
5. Reopen and enter/edit the week. Retain at least one populated weekday and
   one weekend day. Other days may be empty.
6. **Review & save** shows all seven day lists, the Timed confirmation checkbox,
   **Back to draft** and **Save to Resideo**. Nothing has been sent yet.
7. Confirm and Save once. Verified readback closes the popup and reports Off.
8. Check the whole week in the app against the intended week/backup; check other
   zones, native schedule On/Off and hold state too.

## Sleep in the existing editor

1. Open **Schedule editor**. Select Geofence, or use **Edit Geofencing settings**
   when Geofence is already active.
2. Create or edit sleep, then review and save the full profile.
3. Check start/end/night temperature against the app.
4. Remove sleep in the draft, review/save and check the app no longer shows it.
5. Restore the owner's intended profile and mode; fetch a fresh revision.

## Errors and cancellation

- [ ] Cancel/Escape changes no cloud mode or periods.
- [ ] Missing/invalid temperatures or sleep times stop before PUT.
- [ ] A revision conflict keeps the draft and does not replay the write.
- [ ] Unconfirmed readback keeps the popup/draft and requires reload after checking
      the app. It must not claim the requested mode was confirmed.
- [ ] A direct switch service call shows a setup link and leaves mode unchanged;
      automations use set_heating_schedule_mode with explicit fields instead.

## Result to share

```text
Integration/editor version:
Thermostat entity/model/firmware:
HA version:
Initial app mode and switch state:
On setup → review → Save:
On Cancel (no change):
Off setup → review → Save:
Off Cancel (no change):
Sleep create/edit/remove in popup:
Sleep create/edit/remove in full editor:
Whole timed week restored:
Other zones unchanged:
Native schedule On/Off / hold before and after:
Sanitized error or unconfirmed readback:
```
