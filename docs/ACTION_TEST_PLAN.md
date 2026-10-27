# Resideo Native — Schedule Test Guide

**Version:** 0.3.1  ·  **Devices:** Upstairs heating, downstairs heating and hot water

Read the current schedule, change one Monday entry, check Home Assistant and the Resideo app, then restore the original entry **in the app**. This checks synchronization in both directions without installing a fixed routine.

> The schedules below are test examples based on your supplied readings. They are not integration defaults. If the fresh GET differs, preserve the actual periods returned by your account rather than overwriting them with these examples.

## Before you start

1. Install **Resideo Native 0.3.1**, fully restart Home Assistant and refresh the browser.
2. Open **Developer Tools → Actions → YAML mode**. Paste and run **one YAML block at a time**, using **Perform action**. These are action snippets, not complete `scripts.yaml` definitions.
3. Confirm the supplied entity IDs in **Developer Tools → States**. Replace them only if your installation uses different names.
4. Save each device's initial GET response. Its `revision` belongs to that device's schedule. Copy it into that device's SET action; do not reuse a revision from another device or from an earlier change.
5. Complete and restore one device before testing the next. During each SET/readback check, avoid simultaneous edits in the app.

| Device | Entity used in the examples | What to replace/check |
| --- | --- | --- |
| Upstairs heating | `climate.upstaires` | Confirm the supplied upstairs Resideo Native entity |
| Downstairs heating | `climate.downstaires` | Confirm the supplied downstairs Resideo Native entity |
| Hot water | `water_heater.downstaires_hot_water` | This is the previously reported entity; confirm the spelling on your system |

If testing your own single thermostat, use `climate.kosz_thermostat_2` in the upstairs test **only if its Monday readings match**. That does not test the requester's separate upstairs/downstairs addressing or DHW hardware.

**Keep `response_variable` in every block.** The schedule actions return data and require it when run as script actions. The variable names below are local to each execution; copy the displayed revision manually into the SET block.

### Test plan

| Test | One deliberate change | Expected preserved data |
| --- | --- | --- |
| Upstairs | Monday 06:30: **19 → 19.5 °C** | Other Monday periods; Tuesday–Sunday; downstairs and hot water |
| Downstairs | Monday 08:00: **16 → 16.5 °C** | Three Monday periods stay three; Tuesday–Sunday; upstairs and hot water |
| Hot water | Monday first On: **07:00 → 07:10** | Off at 08:00; 16:00–17:30 interval; Tuesday–Sunday; both heating zones |

Temperatures in this guide assume the GET response says **Celsius**. Times are thermostat-local wall-clock times. For this user's system, that is the UK schedule, not UTC.

---

## 1. Upstairs heating

### A — Read and save the baseline

```yaml
action: resideo_native.get_heating_schedule
target:
  entity_id: climate.upstaires
response_variable: upstairs_schedule
```

Compare all seven days with the app before continuing. Based on your readings:

| Days | Expected periods |
| --- | --- |
| Monday–Friday | 06:30 → 19 °C; 08:00 → 16 °C; 18:00 → 21 °C; 22:30 → 16 °C |
| Saturday–Sunday | 08:00 → 19 °C; 10:00 → 16 °C; 17:00 → 21 °C; 23:00 → 16 °C |

Copy the **`revision`** from this response for step B. If the response contains `status: unrecognized_response`, an error, or different periods, stop here and send the result before attempting this example change.

### B — Change one entry from Home Assistant

This replaces **Monday’s complete period list**, changing only Monday at **06:30** from **19 °C to 19.5 °C**. Other days are supplied from the latest cloud schedule by the integration.

```yaml
action: resideo_native.set_heating_schedule
target:
  entity_id: climate.upstaires
data:
  expected_revision: "PASTE_FRESH_UPSTAIRS_REVISION_HERE"
  days:
    Monday:
      - time: "06:30"
        temperature: 19.5
      - time: "08:00"
        temperature: 16
      - time: "18:00"
        temperature: 21
      - time: "22:30"
        temperature: 16
response_variable: upstairs_change_result
```

Save the returned response or full error. Expect `verification_status: verified`. If `status: readback_unconfirmed`, inspect actual/requested values and the app, then reload before retrying.

### C — Read back and check the official app

Run a separate GET after SET:

```yaml
action: resideo_native.get_heating_schedule
target:
  entity_id: climate.upstaires
response_variable: upstairs_schedule
```

Check the result:

- [ ] Monday 06:30 is **19.5 °C** in the returned schedule.
- [ ] The other Monday periods remain 08:00 / 16 °C, 18:00 / 21 °C and 22:30 / 16 °C.
- [ ] Tuesday–Sunday match the saved baseline, including the different weekend routine.
- [ ] The downstairs and hot-water schedules remain unchanged.
- [ ] Refresh/reopen the schedule in the **Resideo app**; it shows the same change.
- [ ] No schedule-action error appears in the Home Assistant log.

### D — Restore in the app and check the reverse direction

Restore **Monday 06:30 to 19 °C in the Resideo app**, leaving the other periods alone.

Save in the app, then **run the same GET from step C again**. The complete schedule should match the baseline saved in step A. This confirms **app → Home Assistant** reading as well as **Home Assistant → app** writing.

A revision is a fingerprint, not an increasing counter. It can return to the original value after restoring the original schedule. Always use the revision from the latest GET for a later SET.

**Result:**

- [ ] Initial read matches the app.
- [ ] HA change is visible in a fresh GET and in the app.
- [ ] Other days and other devices are unchanged.
- [ ] App-side restoration is visible in HA and matches the baseline.

---

## 2. Downstairs heating

### A — Read and save the baseline

```yaml
action: resideo_native.get_heating_schedule
target:
  entity_id: climate.downstaires
response_variable: downstairs_schedule
```

Compare all seven days with the app before continuing. Based on your readings:

| Days | Expected periods |
| --- | --- |
| Monday–Friday | 08:00 → 16 °C; 18:00 → 21 °C; 22:30 → 16 °C (**three periods**) |
| Saturday–Sunday | 08:00 → 19 °C; 10:00 → 16 °C; 17:00 → 21 °C; 23:00 → 16 °C |

Copy the **`revision`** from this response for step B. If the response contains `status: unrecognized_response`, an error, or different periods, stop here and send the result before attempting this example change.

### B — Change one entry from Home Assistant

This replaces **Monday’s complete period list**, changing only Monday at **08:00** from **16 °C to 16.5 °C**. Other days are supplied from the latest cloud schedule by the integration.

```yaml
action: resideo_native.set_heating_schedule
target:
  entity_id: climate.downstaires
data:
  expected_revision: "PASTE_FRESH_DOWNSTAIRS_REVISION_HERE"
  days:
    Monday:
      - time: "08:00"
        temperature: 16.5
      - time: "18:00"
        temperature: 21
      - time: "22:30"
        temperature: 16
response_variable: downstairs_change_result
```

Save the returned response or full error. Expect `verification_status: verified`. If `status: readback_unconfirmed`, inspect actual/requested values and the app, then reload before retrying.

### C — Read back and check the official app

Run a separate GET after SET:

```yaml
action: resideo_native.get_heating_schedule
target:
  entity_id: climate.downstaires
response_variable: downstairs_schedule
```

Check the result:

- [ ] Monday 08:00 is **16.5 °C** in the returned schedule.
- [ ] Monday still has exactly **three periods**; no 06:30 period has been added.
- [ ] Monday 18:00 / 21 °C and 22:30 / 16 °C are unchanged.
- [ ] Tuesday–Sunday match the saved baseline, including the four-period weekend routine.
- [ ] The upstairs and hot-water schedules remain unchanged.
- [ ] Refresh/reopen the schedule in the **Resideo app**; it shows the same change.
- [ ] No schedule-action error appears in the Home Assistant log.

### D — Restore in the app and check the reverse direction

Restore **Monday 08:00 to 16 °C in the Resideo app**, keeping exactly three Monday periods.

Save in the app, then **run the same GET from step C again**. The complete schedule should match the baseline saved in step A. This confirms **app → Home Assistant** reading as well as **Home Assistant → app** writing.

A revision is a fingerprint, not an increasing counter. It can return to the original value after restoring the original schedule. Always use the revision from the latest GET for a later SET.

**Result:**

- [ ] Initial read matches the app.
- [ ] HA change is visible in a fresh GET and in the app.
- [ ] Other days and other devices are unchanged.
- [ ] App-side restoration is visible in HA and matches the baseline.

---

## 3. Hot-water schedule

### A — Read and save the baseline

```yaml
action: resideo_native.get_hot_water_schedule
target:
  entity_id: water_heater.downstaires_hot_water
response_variable: hot_water_schedule
```

Compare all seven days with the app before continuing. Based on your readings:

| Days | Expected On/Off transitions |
| --- | --- |
| Every day | 07:00 On → 08:00 Off; 16:00 On → 17:30 Off |

Copy the **`revision`** from this response for step B. If the response contains `status: unrecognized_response`, an error, or different periods, stop here and send the result before attempting this example change.

### B — Change one entry from Home Assistant

This replaces **Monday’s complete period list**, changing only Monday’s first **On** time from **07:00 to 07:10**. Other days are supplied from the latest cloud schedule by the integration.

```yaml
action: resideo_native.set_hot_water_schedule
target:
  entity_id: water_heater.downstaires_hot_water
data:
  expected_revision: "PASTE_FRESH_HOT_WATER_REVISION_HERE"
  days:
    Monday:
      - time: "07:10"
        state: "On"
      - time: "08:00"
        state: "Off"
      - time: "16:00"
        state: "On"
      - time: "17:30"
        state: "Off"
response_variable: hot_water_change_result
```

Save the returned response or full error. Expect `verification_status: verified`. If `status: readback_unconfirmed`, inspect actual/requested values and the app, then reload before retrying.

### C — Read back and check the official app

Run a separate GET after SET:

```yaml
action: resideo_native.get_hot_water_schedule
target:
  entity_id: water_heater.downstaires_hot_water
response_variable: hot_water_schedule
```

Check the result:

- [ ] Monday transitions are **07:10 On, 08:00 Off, 16:00 On, 17:30 Off**.
- [ ] Tuesday–Sunday remain **07:00–08:00 and 16:00–17:30**.
- [ ] Both heating schedules remain unchanged.
- [ ] Refresh/reopen the schedule in the **Resideo app**; it shows the same change.
- [ ] No schedule-action error appears in the Home Assistant log.

### D — Restore in the app and check the reverse direction

Restore **Monday’s first On time to 07:00 in the Resideo app**. Keep Off at 08:00 and the second interval at 16:00–17:30.

Save in the app, then **run the same GET from step C again**. The complete schedule should match the baseline saved in step A. This confirms **app → Home Assistant** reading as well as **Home Assistant → app** writing.

A revision is a fingerprint, not an increasing counter. It can return to the original value after restoring the original schedule. Always use the revision from the latest GET for a later SET.

**Result:**

- [ ] Initial read matches the app.
- [ ] HA change is visible in a fresh GET and in the app.
- [ ] Other days and other devices are unchanged.
- [ ] App-side restoration is visible in HA and matches the baseline.

---

DHW uses the Android app's **10-minute grid**. The old 07:05 example was outside
that grid and is now rejected before PUT. This guide uses 07:10.

## What to do if a step fails

| Result | Next step |
| --- | --- |
| Revision conflict | Fetch the schedule again, review it, and use that device's fresh revision. |
| `response_variable` required | Keep the final `response_variable:` line at the top YAML level, aligned with `action:`. |
| Entity not found / unavailable | Check that the ID belongs to Resideo Native and is currently available. A heating-only thermostat cannot run the DHW test. |
| HTTP 400 or another API rejection | Stop that test and send the **complete action error** and matching `resideo_native` log entry. Do not repeatedly change the payload. |
| `status: readback_unconfirmed` | Check the app and run GET before retrying; the schedule may already have changed. Restore the baseline in the app if needed. |
| Unrecognized schedule response | Send the safe structural diagnostic response. Do not treat it as an empty schedule. |

The GET/SET period actions in this guide edit the cloud routine. They do not themselves issue a heating-mode, boost or hold command. For these tests, compare **schedule pages and GET responses**; do not infer success only from the current thermostat target or whether the boiler is running.

## First-time creation and conversion

First-time creation remains outside the current focus. The new native schedule On/Off
and Timed ↔ Geofence controls have a separate
[read/check/restore guide](SCHEDULE_CONTROLS_TEST_PLAN.md). Use the
[period-deletion test](DELETION_TEST_PLAN.md) for existing routines; heating
must keep at least one populated weekday and one populated weekend day.

## Send back the results

Copy this short report and attach the initial/readback/restored GET responses for each tested device. Review schedules before posting; they describe your household routine. Do not include passwords, access tokens, refresh tokens or login callback URLs.

```text
Resideo Native version: 0.3.1
Home Assistant version:
Thermostat model / firmware:

UPSTAIRS
- Initial read matches app: Yes / No
- Monday 06:30 changed to 19.5 °C in app: Yes / No
- Other days and other devices unchanged: Yes / No
- Restored to 19 °C in app and confirmed by HA GET: Yes / No
- Errors:

DOWNSTAIRS
- Initial read matches app: Yes / No
- Monday 08:00 changed to 16.5 °C in app: Yes / No
- Monday still has three periods: Yes / No
- Other days and other devices unchanged: Yes / No
- Restored to 16 °C in app and confirmed by HA GET: Yes / No
- Errors:

HOT WATER
- Initial read matches app: Yes / No
- Monday first On changed to 07:10 in app: Yes / No
- Other transitions/days and heating zones unchanged: Yes / No
- Restored to 07:00 in app and confirmed by HA GET: Yes / No
- Errors:

FIRST-TIME CREATION
- Recognized empty schedule available: Yes / No / Not tested
- GET response attached if available:
```
