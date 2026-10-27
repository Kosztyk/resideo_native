# 0.3.1 — Geofencing sleep payload retest

The 0.3.0 logs reported a generic validation failure. This build corrects the
sleep request to match the app's final serializer. No live write has been sent
as part of this investigation.

## Install and record

1. Replace the complete `/config/custom_components/resideo_native/` folder from
   this archive, restart Home Assistant and refresh the browser.
2. Confirm integration **0.3.1** and **Editor 0.3.1** in the popup/full page.
3. Record the current app mode, Home/Away/sleep values and native schedule status.
   Export your timed-week backup before changing schedule type.
4. Phone geofencing must already be configured in the official app.

## Repeat the failed case once

1. On `climate.kosz_thermostat_2`, open **Switch to Geofencing**. If already in
   Geofence, open **Schedule editor → Edit Geofencing settings** instead.
2. Enter your intended Home/Away values and create/edit the sleep setting.
   The reported case was Home **25°C**, Away **25°C**, sleep **23°C** from
   **22:00** to **09:00**. These are test inputs, not installed defaults.
3. **Save sleep settings** updates the draft only. Check the summary, then
   **Review & save**, confirm and **Save to Resideo** once.
4. A verified result should show Geofence and the requested sleep values after
   a fresh read. Refresh the official app and inspect its Sleep settings too.
5. If rejected or unconfirmed, retain the draft, check the app and reload before
   another attempt. Record the complete sanitized error and integration version.

## Edit and remove

- [ ] Change sleep using an allowed time increment or temperature, save the full
      profile and confirm a fresh HA read and the app match.
- [ ] Repeat through the other interface (popup or full editor).
- [ ] Remove sleep, review/save and confirm the app no longer shows it.
- [ ] Restore the intended profile. Check other zones and native schedule status.

Do not send raw account/device IDs, tokens or unredacted network captures.

```text
Integration / editor: 0.3.1 / Editor 0.3.1
Thermostat / firmware / HA:
Create sleep — save result / HA read / app:
Edit sleep — save result / HA read / app:
Remove sleep — save result / HA read / app:
Original intended profile restored:
Other zones / native schedule status unchanged:
Sanitized error, if any:
```
