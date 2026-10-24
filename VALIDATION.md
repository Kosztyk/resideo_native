# Validation scope — Resideo Native v0.1.7

## Automated GitHub checks

The `.github/workflows/validate.yml` GitHub Actions workflow runs:

- HACS validation without ignored HACS checks;
- Home Assistant Hassfest integration validation;
- local packaging checks, Python compilation and metadata unit tests.

To run the bundled static checks:

```sh
python3 tools/check_repository.py
python3 -m unittest discover -s tests -v
python3 -m compileall -q custom_components
```

These packaging checks **do not test** real Resideo authentication,
thermostat command acceptance, temperature consistency or HA runtime behavior.

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

## Historical tests

An earlier README described 44 automated tests with Home Assistant 2026.10.2,
but the full test suite and referenced `requirements-test.txt`, `docs/` and
`tests/test_protocol.py` were not included in the published 0.1.5 repository.
The public checks added for this release cover packaging only.

## Safety

Never share Resideo passwords, OAuth codes, refresh tokens, or other account
credentials in bug reports or GitHub Actions logs. Sanitize diagnostics.
