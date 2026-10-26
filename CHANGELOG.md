# Changelog

## 0.1.8 — Jasper/T6R domestic hot water

- Discover nested `dhwZone` data and add a hot-water entity plus an on/off state sensor to the parent thermostat device.
- Add follow schedule, permanent on/off and 30/60/90-minute boost/cancel commands traced in Resideo Android 6.21.1.
- Use the parent thermostat ID for the mobile API DHW routes; keep all thermostat climate behavior and shared polling.
- Expose the reported hold, boost, vacation, geo-boost and schedule fields without inventing water temperatures or optimistic command results.
- Disable DHW writes for untraced models; reject missing or offline zones and unsupported durations before sending.
- Restore the earlier protocol/HA regression tests and add DHW protocol, service, discovery and lifecycle tests.
- Align the diagnostic version constant with the manifest.
- User confirms DHW readings and on/off/auto against the app and physical
  Jasper/T6R on HA 2026.10.4; boost and cancellation await hardware testing.

## 0.1.7 — HACS physical-write verification documentation

- Document maintainer-confirmed real-device command acceptance on a physical
  Lyric T6 Pro thermostat (internal model Jasper, owner-reported firmware 6.0.1.50) for HVAC mode, target setpoint and hold/preset controls.
- Explicitly distinguish **Jasper** hardware evidence from unverified other
  devices and firmware builds; firmware 6.0.1.50 is owner-reported and not surfaced by HA.
- Remove obsolete claims that **no** real thermostat command testing exists.
- Preserve existing climate/protocol code; no changes to motor, heating,
  login, setpoint, schedule or other runtime behavior.
- Refresh documentation and version metadata for HACS PR #12444.

## 0.1.6 — HACS publication readiness

- Add HACS and Home Assistant Hassfest validation workflows.
- Add static repository checks and Python packaging tests.
- Add a guarded GitHub release workflow that runs only after the main branch
  has passed validation.
- Correct the HACS display name and link the integration documentation and
  issue tracker to its repository.
- Canonicalize the MIT license file name and clarify README testing scope.
- Keep integration version metadata consistent with the release number.

**Thermostat control, authentication and Resideo network protocol behavior are unchanged.**

## 0.1.5

Previous published release. See the repository's GitHub Releases for its history.
