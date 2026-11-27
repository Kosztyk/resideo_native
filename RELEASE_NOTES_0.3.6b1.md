# Resideo Native v0.3.6b1 — offline beta

Built from the supplied v0.3.5 source archive (6698623444d54579281651469c493181fc12b9e3). No GitHub changes or publication. Addresses feature request #13 for Jasper (T5/T6).

## Added

- Standard Home Assistant climate fan mode service and state: Auto → `auto`, On → `on`, Circulate → `diffuse`.
- Capability-based Jasper-only writes through the native mobile API, with only the `mode` field in the POST body. Existing account auth, lock and bounded read-back verification are reused. No thermostat, setpoint, hold or schedule writes are made by the fan command.
- Optional Fan running binary sensor on thermostats reporting a valid boolean `fanRunning`; explicit fan demand flags are diagnostic only. Idle equipment with confirmed fan activity reports HVAC Fan while the HVAC system is enabled. Configured Off still reports Off.
- Sanitized diagnostics and EN/RO sensor translations. All previous v0.3.5 changes retained; only the editor version strings/import URL change.

## Local validation

- Repository packaging checker: PASS.
- Packaging and review-evidence unit tests: 6 passed.
- Python source/test compilation: PASS.
- Standalone HTTP protocol tests: 36 passed (including three new fan regressions).
- Standalone domestic hot water protocol tests: 13 passed.
- Protocol-only schedule, room accessory, creation, resume, validation and read-back tests: 109 passed using a temporary namespace import adapter to bypass the unavailable HA entrypoint; no HA behavior was mocked or claimed.
- JavaScript editor logic: 37 passed.
- Full Home Assistant runtime suite (including new HA fan tests), Playwright browser tests, hosted HACS and Hassfest: NOT RUN; required runtime/dependencies unavailable offline.
- Physical thermostat: not tested during the original offline build. **Subsequent hardware validation:** the issue #13 reporter confirmed fan modes, transitions, Permanent Hold, Heat and setpoint preservation on three Jasper thermostats with HA 2026.11.0, with 10–20 second confirmation and no warnings. No fan-running sensor appeared; cooling, temporary hold, following schedule and Off behavior were not explicitly tested. See [fan protocol and test plan](docs/FAN_CONTROL.md).

## Installation

Back up the installed component, replace `/config/custom_components/resideo_native/` with the supplied beta component folder and restart HA. Do not remove the config entry. This beta is not published in HACS; restore the v0.3.5 folder and restart to roll back. Other model families, FollowSchedule and fan speed writes remain unsupported.
