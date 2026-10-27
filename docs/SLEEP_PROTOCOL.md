# Geofencing sleep protocol — Android 6.21.1

The supported scope is heating-only legacy Jasper/EMEA thermostats. Geofencing
still uses the phone registration/location permissions from the official app.

## App evidence

The final legacy request serialization, inspected in Android 6.21.1, is:

1. `Y9/a.b` builds the internal Home/Away PeriodSettings and optional flat
   `SleepModeSettings(startTime, endTime)`, with model-specific temperatures.
2. `ef/c.A0` sends the legacy v3 request. For `geoFenceSchedule` it calls
   `GeofenceScheduleSetting.a()` rather than serializing the internal model as-is.
3. That method converts sleep into `SleepModeSettingsV3`, copies its inherited
   period values and serializes it as `sleepMode`.
4. `SleepModeSettingsV3` constructs an array containing one `GeofenceTriggers`.
   Its fields serialize as `triggers`, then `days`, `startTime` and `endTime`.
5. `GeofenceTriggers` assigns `hd/g.values()` to days: Sunday, Monday, Tuesday,
   Wednesday, Thursday, Friday, Saturday. These enum values use their names.

Version 0.3.0 stopped at the internal builder and incorrectly sent flat sleep
times. Version 0.3.1 follows the final serializer, including the day array. The
separate Titan `sleepPeriod` serializer is not used by this legacy route.

The existing traced mode endpoint is:

```text
PUT api/v3/locations/{location}/ThermostatSchedule
```

The selected parent ID remains the only entry in deviceIDs. The body contains
scheduleType Geofence and geoFenceSchedule with homePeriod, awayPeriod and
optional sleepMode. For the maintainer's 25°C Home, 25°C Away and 23°C sleep from
22:00 to 09:00 example, the sleep part on a Fahrenheit-wire Jasper is:

```json
{
  "sleepMode": {
    "triggers": [{
      "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
      "startTime": "22:00:00",
      "endTime": "09:00:00"
    }],
    "heatSetPoint": 73.4,
    "coolSetPoint": 0
  }
}
```

This is the daily sleep setting used by the app. Values are examples, not an
installed routine. No additional route or hold command is introduced.

## Public action input

The existing `geofence` action object now accepts optional `sleep`:

```yaml
geofence:
  home_temperature: 20
  away_temperature: 16
  sleep:
    start_time: "22:00"
    end_time: "06:00"
    temperature: 16.5
```

These are examples, not defaults. Temperatures use the thermostat's display
unit and are converted through the existing device rules. Sleep start/end use
thermostat-local wall time and any reported device time increment. Overnight
periods are valid; equal start/end times are rejected. Missing fields, unknown
keys, booleans/non-finite temperatures and values outside limits stop before PUT.

Omit sleep to preserve returned native sleep settings. Use `sleep: null` to
remove them explicitly. Creating/editing sleep constructs the traced V3 trigger
shape for all seven days; it does not copy arbitrary GET fields into a new model.

Readback compares normalized sleep start/end, heat temperature and trigger day
coverage. Day ordering and HH:MM versus HH:MM:00 do not cause a mismatch. A
response missing days, covering only some of the requested days or containing
different times/temperatures cannot confirm a new write. Flat/unknown returned
sleep shapes remain readable/preserved where possible; an opaque preserved
shape requires exact readback equality unless explicitly replaced or removed.

The request revision and all existing mode constraints still apply. Verification
retries GET only, never the PUT. Tests cover exact synthetic bodies and readback;
physical/cloud acceptance of new sleep writes still requires owner testing.

## Report investigated on 27 October 2026

Read-only inspection of HA 2026.10.4 confirmed the installed version was 0.3.0.
Its logs contained two `set_heating_schedule_mode` HTTP 400 ValidationError
events at 21:04:58 and 21:05:30 (Europe/Bucharest). Both reported only the generic
validation message; neither identified an invalid field. The serializer
comparison establishes the payload defect. Its role in the live rejection
must be confirmed by testing the corrected build. No live PUT was sent while
investigating, and equal Home/Away temperatures were not assumed to be invalid.
