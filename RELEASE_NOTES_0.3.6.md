# Resideo Native v0.3.6 — offline production candidate

This candidate is built from v0.3.6b1. No GitHub access, repository change, tag, release or live thermostat command was made during this build. Issue #13 fan control is the same native mode-only Jasper POST that passed the beta reporter's hardware tests.

## Changes since v0.3.6b1

- Add fan-specific delayed/bounded read-back, superseding command, simultaneous thermostat and HVAC Off HA tests. Add local HTTP regressions for sanitized 400, non-replayed 500, 429 backoff, concurrent device commands, post-lock capability revalidation, and conservative model fallback.
- Recognize an exact Jasper `deviceModel` when `deviceType` is missing or an explicitly generic type (`thermostat`, `stat`, `unknown`, `lcc`, `tcc`). Reject known conflicting families, unfamiliar non-generic types and malformed model identifiers. Still require at least one recognized advertised mode.
- With configured HVAC Off, positive `fanRunning` reports Fan without changing HVAC mode. Missing/false telemetry retains Off and ignores stale equipment demand. When HVAC is enabled, heating/cooling retain precedence. Never infer running from configured fan mode or demand flags.
- Add reverse fan-mode lookup, typed sensor discovery and organized imports. The coordinator, authentication and fan write method are unchanged.
- Synchronize version metadata to 0.3.6 and prepare the exact-version release gate with existing validated-main and successful-CI checks. No auto-publication occurs in this offline build.

## Hardware validation (reported for v0.3.6b1)

On three Jasper heat/cool thermostats (Home Assistant 2026.11.0, US account), the reporter confirmed `auto`, `on`, `diffuse` discovery and initial state, successful fan changes within 10–20 seconds, no warnings, and preservation of Permanent Hold, Heat and setpoints. A raised setpoint and a temperature change while the fan was On were also preserved. No fan-running binary sensor appeared and HVAC action never reported Fan during Circulate. This suggests usable `fanRunning` telemetry was absent; diagnostics were not supplied. This is not a blocker for fan mode control.

The new generic-model fallback and Off-mode activity behavior have not been hardware-tested. Cooling operation, Temporary Hold, following schedule and external app/wall updates after setup were not explicitly tested. Other model families, FollowSchedule and speed writes remain unsupported.

## Offline validation

- 42 local HTTP protocol tests passed (six new tests).
- 13 local domestic hot-water protocol tests passed.
- 109 protocol-only schedule and room tests passed using a temporary namespace import adapter to bypass the unavailable Home Assistant entrypoint.
- 37 JavaScript editor logic tests passed.
- 7 packaging/review-evidence tests passed, including the exact stable-version release gate.
- Python compilation, repository packaging checker and ZIP integrity passed.
- Full Home Assistant runtime suite (including five new HA tests and the expanded HVAC action matrix), Ruff, Playwright browser tests and hosted HACS/Hassfest not executed: the pinned dependencies/runtime are unavailable offline. The source is prepared for these checks, not certified as passing them.

## Install / rollback

Back up `/config/custom_components/resideo_native/`, replace the entire component folder with the installation ZIP's `resideo_native/` folder, then restart Home Assistant. Keep existing configuration entries. Restore the previous folder and restart for rollback. See [fan protocol and test plan](docs/FAN_CONTROL.md).
