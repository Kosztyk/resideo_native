## Wireless room sensors and priority for FlyCatcher

- Discover Honeywell Home Smart Room Sensors paired with compatible T9/T10-family thermostats on the legacy Resideo cloud. Temperature, humidity, motion, occupancy, battery, connectivity, signal and status entities appear as the cloud reports those fields.
- Select one room, multiple rooms, All rooms or Follow Me (Active Rooms in the Resideo app). The selector displays the cloud’s current priority and checks it after a write.
- Follow Me now requests a Temporary Hold from an active schedule. It preserves the reported type of an existing hold. Transient zero targets are suppressed and unconfirmed Follow Me writes produce a warning.
- Link room sensors to their thermostat using Home Assistant’s `via_device_id`. Use the native climate temperature properties on HA 2026.11 and keep the legacy climate properties on HA 2026.10.

The [FlyCatcher tester reported no issues on v0.3.4b7](https://github.com/Kosztyk/resideo_native/issues/9#issuecomment-6905093830). That test covers the reported installation. The [device guide](https://github.com/Kosztyk/resideo_native/blob/v0.3.4/docs/ROOM_SENSORS.md) describes model coverage and available entities.

## Upgrade

Requires Home Assistant 2026.10.0 or later. Update through HACS, or extract the Home Assistant install ZIP and replace `/config/custom_components/resideo_native/` with its full `resideo_native` folder. Restart Home Assistant. Your existing account configuration carries over. Refresh the browser and confirm **Editor 0.3.4** if you use the schedule editor.
