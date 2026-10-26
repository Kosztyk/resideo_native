# Resideo Native 0.1.8 — Jasper/T6R hot water

Adds the hot-water support requested in issue #2 for legacy Jasper thermostats
that return a nested `dhwZone`. This archive is based on the supplied 0.1.7
repository snapshot.

- Hot-water on/off state sensor and reported hold/boost/schedule attributes.
- Water-heater entity with follow schedule, always on, always off and boost.
- Timed boost action: 30, 60 or 90 minutes, plus a separate cancel action.
- Commands traced in the supplied Resideo Android 6.21.1 APK, using parent
  thermostat addressing and exact app JSON bodies.
- Shared polling, offline handling, discovery on later polls and no optimistic
  state updates.
- Existing thermostat climate behavior retained; diagnostic version corrected.
- Protocol and Home Assistant 2026.10.2 tests included in the source archive.

Replace the complete `/config/custom_components/resideo_native/` directory and
restart Home Assistant. The existing account configuration is retained.
Thermostats without `dhwZone` keep their existing climate entities.

The README contains installation and action examples. See
`docs/HOT_WATER_PROTOCOL.md` for the app routes, request bodies and symbol
references requested by the issue reporter.

The issue #2 requester confirmed hot-water readings and on/off/auto against
the Resideo app and physical Jasper/T6R on **Home Assistant 2026.10.4**.
On/off give PermanentHold; auto restores NoHold. HA reads changes back within
seconds. **Timed boost and cancellation still await hardware confirmation.**
No DHW temperature setpoint or schedule editor is added.
