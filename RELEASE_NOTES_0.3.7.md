# Resideo Native v0.3.7 — maintenance release

This release corrects metadata, CI warnings and documentation after v0.3.6. The hardware-validated Jasper fan endpoint and payload, hold preservation logic, coordinator, authentication, schedules, room priority and hot water are unchanged.

- Add `climate.thermostats_heating` to the integration manifest and enforce it in packaging checks.
- Use Node.js 24 action releases: checkout v7.0.1, setup-python v7.1.0 and setup-node v7.1.0.
- Keep the existing test network restrictions; use IPv4 for the localhost HTTP test clients to avoid attempts to connect to blocked IPv6 loopback.
- Correct documentation for the published v0.3.6 release and synchronize version references.

## Validation baseline

The [v0.3.6 hosted validation run](https://github.com/Kosztyk/resideo_native/actions/runs/46078667779) passed all five jobs: packaging/Python checks (7 packaging and evidence tests), 305 Python/HA tests and 83 subtests (36 IPv6 loopback warnings), 37 JavaScript unit tests and Playwright browser tests, HACS (10/10 checks, with a missing-category warning), and Hassfest. The [v0.3.6 release](https://github.com/Kosztyk/resideo_native/releases/tag/v0.3.6) was published after validation.

Hardware evidence remains the issue #13 reporter's three Jasper thermostats running v0.3.6b1 on HA 2026.11.0. Optional fan-running telemetry was not available on those devices. See [fan control](docs/FAN_CONTROL.md).

The release workflow appends the exact successful v0.3.7 validation run and commit before publication. No new hardware testing is claimed.

## Installation

Update through HACS and restart Home Assistant. Manual installation assets and SHA-256 checksums are provided in the GitHub release. Retain existing configuration entries; restore the previous complete component folder for rollback.
