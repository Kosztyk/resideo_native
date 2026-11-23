# Wireless room sensors and room priority

## Supported devices

Resideo Native supports paired Honeywell Home Smart Room Sensors on legacy-cloud
thermostats whose device type or model begins with `FlyCatcher`. This is the
thermostat family used for T9/T10 room controls in the Resideo app. Retail models,
firmware and backend support can vary. The [issue #9 field test](https://github.com/Kosztyk/resideo_native/issues/9)
covers one FlyCatcher installation and its paired sensors. The report did not
identify an exact retail thermostat SKU or firmware. Thermostats reported as
Jasper, including the tested T6/T6R, keep their existing controls.

Pair sensors and assign them to rooms in the official Resideo app or thermostat.
Home Assistant discovers sensors that the cloud reports for that account.

## Home Assistant entities

Each supported wireless accessory appears as a device linked to its thermostat.
Entities are added for fields that the cloud returns.

| Entity | Reported value |
| --- | --- |
| Temperature and humidity | Current readings reported for this accessory. |
| Motion and occupancy | Separate binary sensors for readings reported by this accessory. |
| Battery status and Battery low | Battery status text and a binary warning for recognized low-battery states. |
| Signal strength, Sensor status and Connected | RSSI in dBm, accessory status and binary connectivity for recognized states. |

Room-sensor entities are read-only. Readings and diagnostics follow account
polling. Since v0.3.5, existing measurement entities show **Unknown** when the
cloud omits that accessory's data and **Unavailable** when the accessory is
offline. Each accessory's diagnostic attributes use its reported priority
exclusions. [Issue #11](https://github.com/Kosztyk/resideo_native/issues/11)

## Room priority and holds

Open **Settings → Devices & services → Resideo Native → your thermostat**
and find **Room priority**.

| Option | Behavior |
| --- | --- |
| **Room** | Prioritize one room by name. |
| **Rooms** | Prioritize a combination of rooms. Combinations are listed when there are up to six rooms. |
| **All rooms** | Select every room currently reported by the thermostat in one request. |
| **Follow Me** | Use motion-based priority, labelled **Active Rooms** in the Resideo app. |
| **Whole House (set in Resideo app)** | Read-only display when the app reports its native Whole House mode. |

Manual room priority is a schedule override. **Follow Me** requests a temporary
hold when the schedule is running without a hold. An existing reported hold type
and, for a timed hold, its reported expiry are carried in the request. To
restore the current scheduled room selection, use **Follow schedule** on the
climate card. Edit room assignments for future schedule periods in the Resideo app.

## Troubleshooting

Check sensor pairing and room priority in the official app first. A room
priority command is sent once, followed by an immediate read and up to three
additional reads for cloud confirmation. If Follow Me remains unconfirmed,
Home Assistant logs a warning. A transient zero from the cloud is omitted
from the climate target while the thermostat reports it.

Include the integration version, thermostat model, Home Assistant version and
relevant log message in an issue report. Integration diagnostics show priority
mode, sensor counts and reported measurement coverage without room names or IDs.

## Field evidence

The [tester’s b6 report](https://github.com/Kosztyk/resideo_native/issues/9#issuecomment-6899349858)
confirmed Follow Me/Active Rooms and single, multiple and All rooms selections
in both directions while on a hold. The [subsequent report](https://github.com/Kosztyk/resideo_native/issues/9#issuecomment-6902627913)
identified the separate scheduled Follow Me transition and room-sensor registry
warning. The [b7 follow-up](https://github.com/Kosztyk/resideo_native/issues/9#issuecomment-6905093830)
reported no issues with that build. v0.3.4 was promoted from b7
with version metadata changes.

See also the [Resideo room priority API reference](https://developer.honeywellhome.com/lyric/apis).
