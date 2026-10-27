# Resideo Native 0.3.1 — schedules and visual controls

This release includes heating/DHW schedule actions and editing, visible native
schedule controls, optional sidebar access and reviewed Geofencing/sleep setup.
Heating/DHW action and real Off results are hardware-confirmed for the reported
T6H700RW4011 setup; see [the evidence matrix](docs/TESTING_2026-10-27.md).

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
   Confirm **Editor 0.3.1** in the popup or full page.

The mode switch reflects confirmed cloud type; the separate Heating schedule
switch controls native schedule On/Off. Opening setup and saving sleep into a
draft send no cloud command. Export a timed backup before changing type.
Phone geofence registration/location permissions remain in the official app.

**Add scheduler to sidebar** remains Off by default and preserves existing
preferences. No household temperatures or periods are installed by this update.

Start with [the focused sleep retest](docs/SLEEP_PAYLOAD_RETEST.md).
The [full switch/sleep test plan](docs/MODE_SWITCH_TEST_PLAN.md) is also included.
See [release notes](RELEASE_NOTES_0.3.1.md) and [validation](VALIDATION.md).
For HACS updates, download the release and restart HA. Manual installation uses
the complete integration folder. Account configuration is retained.
