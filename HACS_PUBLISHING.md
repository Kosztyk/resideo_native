# Resideo Native publication

The [v0.3.6 hosted validation run](https://github.com/Kosztyk/resideo_native/actions/runs/46078667779) passed all five jobs: packaging/Python checks (7 packaging and evidence tests), 305 Python/HA tests and 83 subtests (36 IPv6 loopback warnings), 37 JavaScript unit tests and Playwright browser tests, HACS (10/10 checks, with a missing-category warning), and Hassfest. The [v0.3.6 release](https://github.com/Kosztyk/resideo_native/releases/tag/v0.3.6) was published after validation.

The version-specific release workflow is authorized for v0.3.7 only. It does not publish prereleases or replace an existing release.

A push to `main` runs packaging checks, Home Assistant tests, editor and browser tests, HACS and Hassfest in [Validate Resideo Native](https://github.com/Kosztyk/resideo_native/actions/workflows/validate.yml).

After successful validation of a push to the current `main` commit, the [release workflow](https://github.com/Kosztyk/resideo_native/actions/workflows/release.yml) checks the validated SHA, exact manifest version and existing release, then publishes v0.3.7 as the latest stable release. The notes identify the validated commit and run. Assets include source and manual installation ZIPs with SHA-256 checksums.

HACS reads the integration from the release tag. Users with the repository added as a HACS custom integration can download the update and restart Home Assistant after publication. Catalog inclusion is managed by HACS separately.
