# Resideo Native 0.3.1 — visual acceptance tests

Run only the cases applicable to the owner's devices. Local automated tests use
a synthetic HA API; this checklist records actual installed/cloud observations.

## Install and navigation

- [ ] Replace the complete integration folder, restart HA and refresh the browser.
- [ ] A visible **Schedule editor** entity opens that thermostat's page.
- [ ] A **Heating schedule** switch provides native On/Off.
- [ ] **Add scheduler to sidebar** is also a switch on this device page.
- [ ] **Switch to Geofencing** is a left/right switch; no Press entity remains.
- [ ] On opens Home/Away setup → review → Save, without leaving the current page.
- [ ] Off opens timed-week setup → review → Save.
- [ ] Cancel retains the observed cloud/switch state in both directions.
- [ ] Create/edit/remove overnight sleep works in the popup and full editor.
- [ ] Configure gear retains native HA options.
- [ ] The thermostat's **Visit device** link opens the same editor.
- [ ] Heading says **Editor 0.3.1**; no sidebar item appears by default.
- [ ] With multiple accounts, the integration link lists only that account's devices.
- [ ] **Integration settings** displays existing poll/hold values and sidebar Off.
- [ ] **Add scheduler to sidebar** is visible at the top and starts Off for a new account.
- [ ] Click it: **Resideo schedules** appears in the sidebar without reloading thermostat controls.
- [ ] Reopen the editor: the toggle still shows On.
- [ ] Click again: the shortcut disappears if no other account enables it.
- [ ] The editor entity still opens the page when the shortcut is Off.
- [ ] Poll/default-hold values and cloud routines remain unchanged.
- [ ] Editing a period disables the sidebar toggle until the draft is saved/discarded.

Saving integration options must not modify the Resideo routine or thermostat hold.

## Existing routines

For each entity, load the actual schedule and export a backup. Use
[the per-device read/change/check/restore plan](ACTION_TEST_PLAN.md), or repeat
its small changes visually.

| Entity from the requester | Baseline detail to preserve |
| --- | --- |
| `climate.upstaires` | Four periods; different weekday/weekend routine |
| `climate.downstaires` | Three weekday periods; four weekend periods |
| `water_heater.downstaires_hot_water` | Two On/Off intervals daily |

- [ ] Read matches the app; no prefilled routine appears.
- [ ] Edit one value. Typing retains focus and the draft blocks device switching.
- [ ] Review shows the intended change and sends nothing until Save.
- [ ] Save once; readback and official app agree.
- [ ] Other days/devices match the baseline.
- [ ] Restore in the app; a fresh HA load shows the restoration.

For period removal, use [the deletion test](DELETION_TEST_PLAN.md). Clearing an
individual heating day is allowed only with a weekday and weekend day remaining.
DHW retains its own validation; no heating Geofence/hold controls appear there.

## Native On/Off and schedule types

Follow [the focused controls test](SCHEDULE_CONTROLS_TEST_PLAN.md). It covers:

- [ ] Native schedule Off matches the app and retains periods.
- [ ] Native schedule On matches the app; no hold command is substituted.
- [ ] Timed backup exported before switching type.
- [ ] **Switch to Geofencing** is visible above the On/Off controls and opens Home/Away fields.
- [ ] A sparse/inactive routine can resume without creating replacement periods.
- [ ] Geofence Home/Away fields use actual returned or owner-entered values.
- [ ] Type changes require review and explicit confirmation.
- [ ] Other devices retain their types, routines and holds.
- [ ] Return to Timed using the backup if the cloud omits its inactive routine.
- [ ] Readback and app match after each step; original configuration is restored.

Keep phone registration/location permissions in the official app. Initial
geofence phone setup and first-time schedule creation are outside this test.

- [ ] Delayed readback retries GET; an unconfirmed result retains the draft and requires reload.
- [ ] DHW 07:05 is blocked before writing; 07:10 uses the app grid.

## Conflicts, backups and layout

- [ ] Change one period in the app after loading in HA. A subsequent stale HA save
      is rejected and the draft is retained.
- [ ] Reload before deciding to retry; use the current revision.
- [ ] Backup import changes only the draft; kind/unit mismatches are rejected.
- [ ] Desktop and phone layouts are usable without horizontal page overflow.
- [ ] The regular climate popup remains HA's standard thermostat control.

## Report

```text
Integration / editor: 0.3.1 / Editor 0.3.1
HA version / browser:
Model / firmware:
Schedule editor entity / Visit device:
Default sidebar hidden / optional toggle:
Account scoping:
Upstairs read-edit-check-restore:
Downstairs three-period day preserved:
DHW read-edit-check-restore:
Delete period / eligible empty day:
Weekday/weekend minimum guard:
Native schedule Off / On:
Timed -> Geofence -> Timed:
Other devices unchanged:
Conflict / backups / mobile:
First-time creation: Not tested
Exact sanitized errors:
```

Include relevant fresh GET responses and app screenshots after checking for
private household information. Never share passwords, tokens or login callback URLs.
