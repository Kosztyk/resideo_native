# Validation scope — Resideo Native v0.1.6

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

## Historical tests

An earlier README described 44 automated tests with Home Assistant 2026.10.2,
but the full test suite and referenced `requirements-test.txt`, `docs/` and
`tests/test_protocol.py` were not included in the published 0.1.5 repository.
The public checks added for this release cover packaging only.

## Safety

Never share Resideo passwords, OAuth codes, refresh tokens, or other account
credentials in bug reports or GitHub Actions logs. Sanitize diagnostics.
