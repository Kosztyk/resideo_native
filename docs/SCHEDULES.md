# Schedule editor — Resideo Native 0.3.1

## Open the visible entity

Replace the complete integration folder, restart HA and refresh the browser.
Open **Settings → Devices & services → Resideo Native → your thermostat** and
click **Schedule editor**, the entity with a calendar/edit icon and Open state.
It opens that thermostat's page. Confirm **Editor 0.3.1**.

Each supported thermostat has **Heating schedule**, **Add scheduler to sidebar**
and **Switch to Geofencing** switches on its device page. They can be added to a
dashboard. The sidebar switch is Off by default and saves one account preference.

The Geofencing switch is a left/right control. On opens the Home/Away popup;
Off opens the timed-week popup. Each follows **setup → review → confirmed Save**.
Cancel leaves the current cloud mode and observed switch state unchanged.
The popup stays on the current HA page and sends no command just by opening.
The old Press entity is removed during integration setup after a restart.

Sleep is optional: use **Create Sleep Settings**, enter Sleep start, Sleep end
and Night temperature, then **Save sleep settings** into the draft. Continue
through the main profile review and Save to apply it. Overnight periods are
allowed; identical start/end times are rejected. Use **Edit sleep settings** or
**Remove sleep settings** for an existing draft/profile. The full editor has
these same controls; **Edit Geofencing settings** opens an already active profile.

Export a timed backup before changing type. If Resideo omits the inactive timed
routine, import a backup through the full editor or enter your own periods in
the popup. Missing Home/Away and sleep values stay blank. Phone registration
and location permissions stay in the official app.

Direct `switch.turn_on/off` calls cannot collect form inputs. They create a
setup notification/link and do not change the cloud mode. Automations should
use `set_heating_schedule_mode` with explicit parameters. The observed mode is
read at startup, once per minute and on schedule-action readback.

The integration loads its local
navigation module automatically; no manual dashboard resource is needed for
entity navigation. It only handles its own marked editor entities on normal
taps; unrelated entity popups and explicit entity settings are left alone.

The Configure gear keeps HA's native poll/default-hold/sidebar options.
**Integration settings** on the editor is an alternative. The visible **Add
scheduler to sidebar** toggle at the top of the editor is Off by default.
Click to enable it; click again to disable this account's preference. It uses
HA's options flow and applies without reloading the thermostat integration.
Save/discard a schedule draft before toggling it. With multiple accounts the
shared shortcut is visible while any account enables it. The preference applies
to Home Assistant users, not just this browser. Editor links scope the picker to their account and selected
thermostat. Direct path: `/resideo-schedules`. The normal climate popup remains
HA's standard thermostat control.

## Native schedule On/Off

Use the **Heating schedule** switch on the thermostat device page, or reviewed
**Turn schedule off/on** buttons in the editor. They call the app's dedicated
native schedule-status API, retaining the saved routine.

Inside the editor, use **Switch to Geofencing** above the On/Off controls for the
explicit mode-change form. The dropdown remains an alternative. Both open a draft; neither sends a command
until values are reviewed and Save is confirmed.

No PermanentHold, NoHold, temperature or HVAC-mode command is sent for this
operation. Manual holds, native schedule status and heating mode are separate.
Native On/Off does not validate or replace timed periods. A sparse routine or
an inactive `None` schedule type can be resumed through the status endpoint.
The weekday/weekend minimum remains a period-edit rule. After status readback,
the routine is fetched afresh. If that fetch fails, native On/Off success stays
confirmed while editing is blocked until a new load.

The switch reads the reported native `scheduleStatus`, never inferring it from
a hold. Missing status produces unknown. If verification is unconfirmed, it
keeps the observed state and exposes `last_command_verification`.

DHW retains its existing auto/on/off/boost controls. The heating-only schedule
status endpoint is not applied to the nested DHW zone.

## Read, edit, review and save

Load the actual cloud routine. No example household schedule is installed.
Heating rows use thermostat-local time and the device's display temperature
unit. DHW rows are On/Off transitions on the app's **10-minute grid**:
07:00, 07:10, 07:20, etc. A transition applies until the next one, including
across midnight. An empty day removes transitions; it does not mean Off all day.

Add/delete periods, copy days, then **Review & save**. Only **Save to Resideo**
sends a command. A partial update replaces the complete list of each supplied
day and merges untouched days from a fresh cloud response. Existing edited
days allow 0–6 periods. Heating must retain a populated weekday and weekend
day, following the maintainer's native-app observation. Empty Timed weeks are
readable for repair; no replacement temperatures are invented.

The requester confirmed heating/DHW action-based edits, row/day deletion and
whole-week restoration on 0.3.1, with verified readback and other days unchanged.
They did not test visual deletion or the popup flows. See
[the evidence matrix](TESTING_2026-10-27.md) and
[the deletion test](DELETION_TEST_PLAN.md) for that remaining coverage.

Dirty drafts block device switching. Discard/reload abandons the draft.
Revision checks prevent overwriting a change already visible in the fresh
pre-write GET. There is no traced atomic compare-and-swap; avoid simultaneous
app/HA editing during a save. Schedules load on demand, without a push
subscription or automatic schedule polling.

Heating validates reported `allowedTimeIncrements` when available. DHW uses
the traced 10-minute app grid. Invalid times are rejected locally, never rounded.

## Readback verification

After PUT, make up to five GET observations, with waits of 1, 2, 4 and 8 seconds
between retries. HTTP time is additional. **Only GET is retried.** Comparisons
normalize time seconds, day/period ordering, metadata and float precision.

A confirmed result has `verification_status: verified`. If still different:

- `status: readback_unconfirmed`, `write_accepted: true`;
- `verification_status: unconfirmed`, plus attempts;
- the last observed routine/status, if available;
- for period writes, `requested_days` and `mismatched_days`.

Accepted delivery is not proof that the cloud applied the intended values.
The editor shows a warning, keeps the draft and blocks another write until a
reload. Check the app first. An ignored change is not silently marked successful
or retried. A transport failure before delivery is known remains an error.

The tester's 07:05 DHW edit did not apply on 0.2.3. On 0.3.1 the 07:00 → 07:10
edit was applied and verified, while 07:05 was rejected before sending. The
tester reports the earlier immediate readback errors are gone. The week was
restored and compared to baseline. See [the report](TESTING_2026-10-27.md).

## Timed ↔ Geofence and backups

Export the loaded timed routine before changing to Geofence. Select the type,
use returned or owner-entered Home/Away temperatures, review and explicitly
confirm. Blank fields receive no guessed defaults. Returned sleep settings are editable with the shared create/edit/remove controls.
Phone registration and location permissions stay in the official app.

To return to Timed, use returned inactive periods if present, otherwise import
the exported backup or enter your own routine. Supply all seven day lists;
individual heating days can be empty while retaining both day groups. Review,
confirm, save, then compare app/readback and all other devices. Check the native
On/Off setting separately. Type changes do not explicitly send hold commands.

Export excludes unsaved changes and account/device IDs. Backups still reveal
household routines. Import validates kind, units and periods and changes only
the draft; it never imports an old revision.

Recognized no-schedule responses can open a blank first-time draft. Heating
uses all seven day lists and the day-group minimum; a new DHW routine needs
1–6 transitions per day. A GET error/404/unknown shape is not an empty routine.
First-time creation remains outside current live testing.

## Actions

All schedule actions return data. In Developer Tools → Actions → YAML mode or
scripts, keep `response_variable` aligned with `action`.

| Action | Target | Purpose |
| --- | --- | --- |
| `resideo_native.get_heating_schedule` | climate | Read periods, profile, native enabled status, unit and revision |
| `resideo_native.set_heating_schedule` | climate | Edit/create timed periods |
| `resideo_native.set_heating_schedule_enabled` | climate | Native schedule On/Off |
| `resideo_native.set_heating_schedule_mode` | climate | Confirm Timed/Geofence |
| `resideo_native.get_hot_water_schedule` | water_heater | Read DHW transitions |
| `resideo_native.set_hot_water_schedule` | water_heater | Edit/create DHW transitions |

```yaml
action: resideo_native.get_heating_schedule
target:
  entity_id: climate.replace_with_your_thermostat
response_variable: current_schedule
```

On/Off takes `enabled: true/false` and a fresh `expected_revision`.
Mode takes Timed/Geofence, `confirm_change: true`, a fresh revision, and either
all seven `days` lists or `geofence: {home_temperature: NUMBER, away_temperature: NUMBER}`.
Use owner-chosen temperatures. Heating rows are `{time: "07:15", temperature: 19.5}`;
DHW rows are `{time: "07:10", state: "On"}`. These are shapes, not defaults.

Times must be increasing and unique; optional seconds must be :00 and 24:00 is
unsupported. Revision hashes include native metadata and are not increasing
counters. Always fetch afresh before a write.

See [per-device actions](ACTION_TEST_PLAN.md), [On/Off test](SCHEDULE_CONTROLS_TEST_PLAN.md)
and [Sunday/DHW retest](READBACK_RETEST.md).

## Optional dashboard editor card

For an embedded editor, register this JavaScript module resource:

```text
/resideo_native/schedule-editor-0.3.1.js
```

```yaml
type: custom:resideo-schedule-card
entity: climate.replace_with_your_thermostat
```

The normal Schedule editor entity needs no manual resource entry.

## Protocol evidence and scope

Supplied Resideo Smart Home Android **6.21.1** APK:

| Operation | Method/path | Symbols |
| --- | --- | --- |
| Heating read | GET `api/v4/locations/{location}/devices/{parent}/Schedule` | `ef/c.h0`, `Be/b` |
| Timed/Geofence write | PUT `api/v3/locations/{location}/ThermostatSchedule` | `ef/c.A0`, `y9/p.g/f`, `Y9/a.b` |
| Native heating On/Off | PUT `api/v2/locations/{location}/Schedule/Status` | `base/h.putScheduleOnOffSettings` → `ef/c.y0`; `y9/u.w`, `U9/c` |
| DHW read/write | GET/PUT `api/v3/locations/{location}/devices/{parent}/dhw/schedule` | `Ce/c.Y/K0`, `F9/a.h` |

On/Off uses `DeviceIds: [one selected parent]` and `ScheduleStatus`.
The app's OFF/ON enum serializes the wire values Pause/Resume; those are
schedule-status values, not hold commands. Gson also serializes its unannotated
integer location field as `a`; this build preserves that request shape.
Read state is the root thermostat `scheduleStatus` in locations data.

DHW `O9/d.onClick` calls `wo/m.l4(10)` for both pickers. `l4` builds
selectable minute values with that increment. This is the basis for the DHW grid.

EMEA PUT periods exclude `periodType`/`isCancelled`, as established by earlier
live server errors and successful corrections. One selected parent is addressed.
Supported scope is heating-only legacy Jasper/EMEA and its reported DHW zone.
NA/cooling/partner schedules, phone setup and >6 periods are
outside this build. New On/Off and retry acceptance still need live testing.
See [VALIDATION.md](../VALIDATION.md).
