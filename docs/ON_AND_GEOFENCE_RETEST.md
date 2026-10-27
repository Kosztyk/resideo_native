# Resideo Native 0.3.1 — native On/Off and Geofencing retest

Install the complete folder, restart HA and refresh the browser. Confirm Editor
0.3.1. The mode control is now a left/right switch; the old Press entity is gone.

| Control | Meaning |
| --- | --- |
| Heating schedule | Native schedule On/Off, independently of manual holds |
| Switch to Geofencing | On opens Geofence setup; Off opens timed setup |
| Add scheduler to sidebar | Optional saved account shortcut |
| Schedule editor | Full editor with the same sleep controls |

## Native schedule On/Off

1. Record app type, native enabled status, hold and current routine.
2. Turn Heating schedule Off and check HA/app agree.
3. Turn it On and check HA/app agree; re-read the routine and compare periods.
4. Restore the owner's intended state and record any effects.

Native status-only On/Off does not apply the timed weekday/weekend edit rule
or replace periods. Sparse/inactive responses are accepted through the traced
schedule-status API. Unknown native state must not be inferred from a hold.

## Mode and sleep

Follow the complete [mode-switch/sleep test plan](MODE_SWITCH_TEST_PLAN.md).
On and Off each open a setup popup, followed by review/confirmation and Save.
Cancel leaves the observed cloud mode unchanged. Sleep creation/editing/removal
is available both in the popup and full editor; phone registration/permissions
remain in the official app. Export the timed routine before changing type.

These new flows have local synthetic HA/browser coverage. Live acceptance of
the installed frontend and cloud sleep writes remains pending.
