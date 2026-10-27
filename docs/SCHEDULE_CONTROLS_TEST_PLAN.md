# Resideo Native 0.3.1 — editor entity and schedule On/Off test

Install the complete folder, restart HA and refresh the browser.
First-time creation is outside this test.

## 1. Visible entities

Open **Settings → Devices & services → Resideo Native → a thermostat**.

- **Schedule editor**: sensor with calendar/edit icon and Open state.
  Clicking it must open that thermostat's page with **Editor 0.3.1**.
- **Heating schedule**: native On/Off switch, independent of manual holds.
- **Add scheduler to sidebar**: a switch beside Heating schedule, initially Off
  for an account with no saved preference. Toggle it On/Off; the sidebar shortcut
  should appear/disappear without reloading thermostat controls. Other thermostats
  on this account should show the same state; poll/default-hold values stay intact.
- **Switch to Geofencing**: a left/right switch. On opens the Home/Away popup;
  Off opens the timed-week popup. Each has a separate review/confirmation step.
  Cancel must not change the cloud or switch state. See the detailed
  [mode and sleep test plan](MODE_SWITCH_TEST_PLAN.md).
- Configure gear: native polling/default-hold/sidebar options.
- Sidebar: optional, off by default.

Test one thermostat at a time. The requester uses `climate.upstaires` and
`climate.downstaires`; the maintainer uses `climate.kosz_thermostat_2`.
Select switch/editor entities from the device page; their IDs depend on naming.

Native On/Off now accepts sparse/inactive routines without requiring replacement
periods. See [the focused resume retest](ON_AND_GEOFENCE_RETEST.md).

## 2. Read → Off → check → On → check

1. Load/export the current routine. Record the app's schedule On/Off setting,
   selected type, HVAC mode and manual hold.
2. Turn that thermostat's **Heating schedule** switch Off.
3. Check the native app's schedule setting and HA both show Off.
4. Re-read the week and compare it with the backup. Check other heating/DHW
   devices were unaffected.
5. Turn the same switch On. Check app/HA agree and all periods remain.
6. Restore the owner's intended final setting. Record any hold/mode effects
   actually observed. The integration itself sends no hold or HVAC-mode command.

Unknown means Resideo did not report a native status; it is not inferred Off.
An unconfirmed switch command keeps the observed state. Check app and reload
before retrying.

The editor's **Turn schedule off/on** buttons use the same operation, with review.

## 3. Equivalent action snippets

Read first, using the appropriate climate entity:

```yaml
action: resideo_native.get_heating_schedule
target:
  entity_id: climate.kosz_thermostat_2
response_variable: current_schedule
```

Turn native scheduling Off with that response's revision:

```yaml
action: resideo_native.set_heating_schedule_enabled
target:
  entity_id: climate.kosz_thermostat_2
data:
  enabled: false
  expected_revision: "PASTE_FRESH_REVISION"
response_variable: schedule_off_result
```

Read again, check the app, then turn it On with a new revision:

```yaml
action: resideo_native.set_heating_schedule_enabled
target:
  entity_id: climate.kosz_thermostat_2
data:
  enabled: true
  expected_revision: "PASTE_NEW_FRESH_REVISION"
response_variable: schedule_on_result
```

Keep `response_variable` aligned with `action`. The switch entity performs
the fresh revision read itself.

## 4. Timed ↔ Geofence

Export a timed backup. Phone geofencing must already be configured in the app.
Click **Switch to Geofencing** inside the editor, use owner-chosen Home/Away
values, review and explicitly confirm.
Compare app/readback and the other devices.

To return to Timed, import the backup if inactive periods were omitted by the
cloud. Review all seven lists, keeping a populated weekday and weekend day,
confirm, save and compare. Check the native On/Off setting separately.
Restore the intended type/profile/On-Off state after testing.

Skip this if no suitable geofence-configured device is available. Do not delete
a working routine to force first-time creation.

## Result

```text
Integration / editor: 0.3.1 / Editor 0.3.1
HA / browser / model / firmware:
Thermostat:
Editor entity visible and opens correct device:
Heating schedule switch visible:
Off: app and HA agree / periods preserved:
On: app and HA agree / periods preserved:
Other heating/DHW unchanged:
Observed hold / HVAC-mode effects:
Timed/Geofence: Passed / Failed / Not tested
Final intended configuration restored:
Exact sanitized error / verification status:
```

DHW retains its existing auto/on/off/boost controls. Use
[the Sunday/DHW retest](READBACK_RETEST.md) for the time-editing regression.
