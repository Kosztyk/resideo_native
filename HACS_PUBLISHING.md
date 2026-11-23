# Resideo Native v0.3.5 publication

A push to `main` runs the repository packaging checks, Home Assistant tests,
editor and browser tests, HACS and Hassfest in
[Validate Resideo Native](https://github.com/Kosztyk/resideo_native/actions/workflows/validate.yml).

After all five jobs pass on the current `main` commit, the
[release workflow](https://github.com/Kosztyk/resideo_native/actions/workflows/release.yml)
publishes [v0.3.5](https://github.com/Kosztyk/resideo_native/releases/tag/v0.3.5)
as the latest stable release. The notes identify the validated
commit and run. Assets include the repository source ZIP, the manual Home
Assistant install ZIP and their SHA-256 checksums.

HACS reads the integration from the release tag. Users who have added this
repository as a HACS custom integration can download the update and restart Home
Assistant. Catalog inclusion is managed by HACS separately.
