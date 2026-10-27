# Resideo Native 0.3.1 — Sunday deletion and DHW time retest

The requester's 0.2.3 tests confirmed downstairs row/day deletion, DHW day
deletion and restoration, but almost every immediate readback comparison
errored. The 07:05 DHW change did not apply.

This build retries GET only, compares semantic values and returns unconfirmed
results as data. DHW uses the app's **10-minute grid**: 07:05 is now rejected
before PUT. Test **07:10** instead.

Run one block at a time in Developer Tools → Actions → YAML mode.
Keep `response_variable` aligned with `action`. Use a fresh revision from
that exact device for each write.

## Downstairs: read

```yaml
action: resideo_native.get_heating_schedule
target:
  entity_id: climate.downstaires
response_variable: downstairs_before
```

Save the whole response. Continue only if Sunday still has 08:00/19 °C,
10:00/16 °C, 17:00/21 °C and 23:00/16 °C. Otherwise use the owner's actual routine.

## Downstairs: remove 10:00, check, restore

```yaml
action: resideo_native.set_heating_schedule
target:
  entity_id: climate.downstaires
data:
  expected_revision: "PASTE_FRESH_DOWNSTAIRS_REVISION"
  days:
    Sunday:
      - time: "08:00"
        temperature: 19
      - time: "17:00"
        temperature: 21
      - time: "23:00"
        temperature: 16
response_variable: downstairs_result
```

Expect `verification_status: verified` once reads catch up.
Re-run GET, check the app and compare all other days. Restore Sunday in the app
and re-read the whole week before moving on.

Optional whole-Sunday deletion uses `days: {Sunday: []}` with another fresh
revision. Keep a populated Saturday, then restore and verify all days.

## DHW: read

```yaml
action: resideo_native.get_hot_water_schedule
target:
  entity_id: water_heater.downstaires_hot_water
response_variable: dhw_before
```

Confirm Sunday is 07:00 On, 08:00 Off, 16:00 On, 17:30 Off and the response has
`time_step_minutes: 10`. Save the entire response.

## DHW: change Sunday to 07:10, check, restore

```yaml
action: resideo_native.set_hot_water_schedule
target:
  entity_id: water_heater.downstaires_hot_water
data:
  expected_revision: "PASTE_FRESH_DHW_REVISION"
  days:
    Sunday:
      - time: "07:10"
        state: "On"
      - time: "08:00"
        state: "Off"
      - time: "16:00"
        state: "On"
      - time: "17:30"
        state: "Off"
response_variable: dhw_result
```

Re-run GET and check the app. Sunday must show 07:10 with the other transitions
unchanged. Compare all other days and heating zones. Restore 07:00 in the app,
then re-read the whole week.

The app picker establishes the grid, not live acceptance of this new edit.
Report the observed 07:10 result.

## Interpret the response

| Result | Meaning |
| --- | --- |
| `verification_status: verified` | Requested values were observed; compare app and whole week |
| `status: readback_unconfirmed` | PUT accepted, intended result not confirmed after bounded reads |
| `no write was sent` | Local validation/revision check blocked PUT |
| Delivery unknown / timeout | Check app and GET before retrying |

For unconfirmed results, include `days`, `requested_days`,
`mismatched_days` and attempts. Check the app and reload before another write.
Unconfirmed is not a passing test. No write is automatically repeated.

## Visual-editor test

The requester did not test visual deletion in 0.2.3. Click the new **Schedule
editor** entity, confirm 0.3.1, and repeat an eligible deletion through Review
& save. Check the whole week/app, then restore as above.

## Report

```text
Integration / editor: 0.3.1 / Editor 0.3.1
Downstairs row deletion: verification status / attempts:
Downstairs Sunday deletion (optional):
DHW 07:10: fresh GET and app agree:
Other days/devices preserved:
All originals restored; whole week checked:
Visual editor deletion:
Any readback_unconfirmed response:
Exact sanitized error:
```
