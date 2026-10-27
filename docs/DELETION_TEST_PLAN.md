# Resideo Native 0.3.1 — period deletion test

**Focus:** existing Timed routines. The previous “Monday: enter 1–6 periods”
message was local validation. This build allows clearing an individual day but
keeps the minimum observed in the native app: at least one populated weekday
and one populated weekend day. It does not permit deleting the whole heating week.

## Prepare

1. Install the complete 0.3.1 folder, restart HA and refresh the browser.
2. Click the thermostat's **Schedule editor entity** and confirm **Editor 0.3.1**.
3. Select the device, load the current cloud routine and **Export cloud backup**.
4. Compare it with the app. Keep the real values; no test routine is installed.

For the maintainer use `climate.kosz_thermostat_2`. The requester's IDs are
`climate.upstaires`, `climate.downstaires` and
`water_heater.downstaires_hot_water`.

## A — Remove one row from a populated day

1. Choose a day with multiple rows and delete one.
2. Open **Review & save**. Check only the intended day changed.
3. Save once. Check readback and the same day in the official app.
4. Check remaining rows, other days and other devices match the baseline.
5. Restore the deleted row in the app, then **Load from Resideo** in HA.

## B — Clear one heating day

Use a day whose removal still leaves another populated weekday and a weekend
day. Do not alter unrelated days just to make a test possible.

1. Delete all rows of that day. Its counter should show **0 / 6**.
2. Review: **Draft after** should show **No timed periods**, with the removal
   explained.
3. Choose **Back to draft** once. The empty day remains and no write is sent.
4. Review and save once. Confirm the day is empty in readback and the app.
5. Compare all other days/devices, then restore the original row(s) in the app
   and reload in HA, or import the saved backup and review/save it.

Clearing a day removes its transitions; the last applicable target may continue
from the previous day. Turn the **Heating schedule** switch Off without removing
the routine, or the thermostat's HVAC mode to turn heating off.

## C — Minimum-week protection (draft only)

If a spare draft can be made without changing the cloud:

1. In the draft, remove the last populated weekday, keeping a weekend day.
2. Review must be blocked with the weekday/weekend minimum message.
3. Discard/reload. Repeat by removing the last weekend day instead.
4. Confirm no Save was possible and the cloud/app schedule is unchanged.

An already empty/sparse Timed week is readable. Repair it with your own periods
so both day groups are populated before saving period edits. The editor does not
invent replacement temperatures. Mark this case **Not tested** if unavailable.

The 0.2.3 requester confirmed downstairs Sunday row/day deletion and DHW
Sunday deletion/restoration through actions, without testing visual deletion.
This test supplies that missing UI coverage.

## DHW

Repeat A on `water_heater.downstaires_hot_water`, preserving intended On/Off
transitions. The heating minimum does not apply to DHW. Only test an empty DHW
day if that is a routine the owner intends to use; the requester confirmed a cleared Sunday through actions; visual-editor
acceptance still needs checking. Check both heating zones remain unchanged.

## Results

```text
Integration / editor: 0.3.1 / Editor 0.3.1
Entity:
Delete one row; remaining rows preserved: Passed / Failed / Not tested
Clear an eligible day; readback and app match: Passed / Failed / Not tested
Last weekday/weekend blocked before write: Passed / Failed / Not tested
Other days and other devices preserved:
Original routine restored:
Exact sanitized error:
```

If delivery/readback is uncertain, check the app and reload before retrying.
No failed write is replayed automatically. First-time creation is outside this test.
