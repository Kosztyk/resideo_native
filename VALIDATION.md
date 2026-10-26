# Validation scope — Resideo Native v0.1.8

## Local automated validation — 26 October 2026

The complete included suite passed on **Home Assistant 2026.10.2** with
**Python 3.14.8**: **102 tests passed**, including **44 new DHW tests** and
55 successful subtests across the suite. Repository packaging checks and
Python compilation also passed.

DHW coverage includes nested discovery on the second of two thermostats,
reported state/hold fields, exact mobile API paths and JSON, parent-device
addressing, all three boost durations, cancel versus permanent off, invalid
input rejection, offline/missing zones, failed/timed-out writes, readback,
standard and custom HA actions, dynamic discovery, unload/reload, read-only
handling for untraced models and diagnostics redaction.

The original login, cookies, token renewal, thermostat temperature conversion,
climate actions, setup, options and reauthentication regression tests are also
included and pass. HTTP protocol tests contact only a local simulated server;
no live account or thermostat is used by these tests.

To reproduce with Python 3.14:

```sh
python3.14 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-test.txt
python -m pytest -q
python tools/check_repository.py
python -m compileall -q custom_components
```

The GitHub validation workflow runs packaging, the pinned runtime suite,
HACS and Hassfest. Publication is gated on successful main-branch validation.
See the repository Actions page for the current run results.

## Jasper/T6R hot-water hardware verification (user report)

The issue #2 requester reports installing **0.1.8 over 0.1.7**, restarting
**Home Assistant 2026.10.4**, and testing on **Jasper/T6R**. The integration
loaded without log errors. Both hot-water entities appeared, and state and
hold/boost/schedule attributes matched the raw `dhwZone` data.

| Command | User-confirmed result in Resideo app and physical thermostat |
| --- | --- |
| `on` | Hot water On, `PermanentHold`; always on |
| `off` | Hot water Off, `PermanentHold`; permanently off |
| `auto` | `NoHold`; schedule mode restored |

Home Assistant read each change back within a few seconds. This is the
requester's first-hand hardware report, supplied by the maintainer; it is
separate from automated tests. Firmware was not supplied. **Timed boost
(30/60/90 minutes) and boost cancellation remain unverified on hardware.**

## Hardware write verification (maintainer statement)

The maintainer has confirmed physical operation of a real **Honeywell Home Lyric T6 Pro** thermostat (internal model **Jasper**, owner-reported firmware **6.0.1.50**) with the **Resideo Native** Home Assistant integration,
using all three supported write pathways:

| Home Assistant action | Protocol client path | Reported real-device result |
| --- | --- | --- |
| Change HVAC mode | `set_mode` | Thermostat responds to mode changes |
| Change target temperature | `set_temperature` | Thermostat accepts setpoint changes |
| Choose follow schedule / temporary / permanent hold | `set_hold` | Thermostat responds to hold/preset commands |

**Hardware identification:** The Home Assistant device registry identifies
manufacturer **Resideo / Honeywell Home**, internal model **Jasper**, platform
`resideo_native`. Its `sw_version` property is null; firmware is therefore
**not populated by Home Assistant**. The owner directly reports the physical Lyric T6 Pro firmware as **6.0.1.50**; this version was not independently recovered from the integration. This is the owner's
first-hand confirmation, not an independently logged test run or firmware
matrix. Original reports and documentation do not justify extending the
verification claim to every T6/T6R device, every firmware version, cooling
capabilities not exercised, or every cloud account. Live command demonstrations
may be supplied separately for HACS review.

These real-device checks are distinct from Python/HACS/Hassfest CI and should
not be interpreted as coverage of physical hardware by automated tests.

## Recovered historical suite

The uploaded 0.1.7 repository snapshot contained packaging tests only. The
missing 0.1.5 protocol and HA regression sources were recovered from the prior
archive supplied in this project and included in this local build, with their
version expectation updated to 0.1.8. They run against the new source together
with the DHW tests; historical pass counts are not used as evidence for this
build. The current result is the fresh local run described above.

## Safety

Never share Resideo passwords, OAuth codes, refresh tokens, or other account
credentials in bug reports or GitHub Actions logs. Sanitize diagnostics.
