# Resideo Native 0.3.6

This offline v0.3.6 production candidate is not yet published through HACS. Back up and replace the complete `/config/custom_components/resideo_native/`
folder from the release ZIP. Restart Home Assistant and keep the existing account
configuration.

On a supported T9/T10-family (FlyCatcher) thermostat, find **Room priority** on
the thermostat’s device page. Look for paired room sensors under the integration’s
devices. Missing accessory readings may appear as **Unknown** until the sensor
reports them. See the [room sensor guide](docs/ROOM_SENSORS.md),
[release notes](RELEASE_NOTES_0.3.6.md) and [validation evidence](VALIDATION.md).

## Jasper fan control

Open the climate entity and check whether Fan mode is available. The reported
modes determine what appears; `diffuse` means Circulate. Check the current hold,
setpoints and system mode before and after a fan-only change. If the cloud
reports a boolean `fanRunning`, a separate Fan running binary sensor appears. The v0.3.6b1 tester confirmed fan control and Permanent Hold preservation on three Jasper thermostats; fan-running telemetry was not available on those devices. Follow the
[fan test plan](docs/FAN_CONTROL.md) and report unexpected changes. To roll back,
restore the v0.3.5 component folder and restart; account settings are unchanged.

## Schedule editor and hot water

Use the hour and minute dropdowns to set Timed heating, hot water and
Geofencing Sleep times. They replace the time control that crashed the
Home Assistant macOS app. [PR #10](https://github.com/Kosztyk/resideo_native/pull/10)

1. Replace the complete `/config/custom_components/resideo_native/` folder.
2. Fully restart Home Assistant and refresh the browser. Keep the account.
3. Open **Settings → Devices & services → Resideo Native → your thermostat**.
4. **Switch to Geofencing** is now a left/right switch beside **Heating schedule**.
   The old Press entity is removed automatically.
5. Turn it **On**: the Geofencing popup opens with Home/Away temperatures.
   Optionally use **Create Sleep Settings** to enter start, end and night temperature.
   Save sleep into the draft, then **Review & save**, confirm and **Save to Resideo**.
6. Turn it **Off**: the timed-week popup opens. Edit your periods or import a
   backup through the full editor if the cloud omits the inactive routine.
   **Review & save**, confirm and **Save to Resideo**.
7. **Cancel** closes either popup without changing the cloud or switch state.
8. The full **Schedule editor** has the same create/edit/remove sleep controls.
   Confirm **Editor 0.3.6** in the popup or full page.

The mode switch reflects confirmed cloud type; the separate Heating schedule
switch controls native schedule On/Off. Opening setup and saving sleep into a
draft send no cloud command. Export a timed backup before changing type.
Phone geofence registration/location permissions remain in the official app.

**Add scheduler to sidebar** remains Off by default and preserves existing
preferences. No household temperatures or periods are installed by this update.

For sleep settings, use [the focused sleep retest](docs/SLEEP_PAYLOAD_RETEST.md).
The [full switch/sleep test plan](docs/MODE_SWITCH_TEST_PLAN.md) is also included.
