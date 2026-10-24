# Changelog

## 0.1.7 — HACS physical-write verification documentation

- Document maintainer-confirmed real-device command acceptance on a physical
  Jasper thermostat for HVAC mode, target setpoint and hold/preset controls.
- Explicitly distinguish **Jasper** hardware evidence from unverified other
  devices and firmware builds; firmware version is not surfaced by HA.
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
