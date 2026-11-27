# Resideo Native v0.3.6 — production release

This release was built from v0.3.6b1 offline and subsequently published after successful GitHub validation. Issue #13 fan control is the same native mode-only Jasper POST that passed the beta reporter's hardware tests.

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

## Hosted validation and publication

The [v0.3.6 hosted validation run](https://github.com/Kosztyk/resideo_native/actions/runs/46078667779) passed all five jobs: packaging/Python checks (7 packaging and evidence tests), 305 Python/HA tests and 83 subtests (36 IPv6 loopback warnings), 37 JavaScript unit tests and Playwright browser tests, HACS (10/10 checks, with a missing-category warning), and Hassfest. The [v0.3.6 release](https://github.com/Kosztyk/resideo_native/releases/tag/v0.3.6) was published after validation.

## Install / rollback

Back up `/config/custom_components/resideo_native/`, replace the entire component folder with the installation ZIP's `resideo_native/` folder, then restart Home Assistant. Keep existing configuration entries. Restore the previous folder and restart for rollback. See [fan protocol and test plan](docs/FAN_CONTROL.md).
