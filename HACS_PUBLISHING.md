# Resideo Native publication

**v0.3.6 is an offline production candidate.** No repository update, tag or release has been performed. The version-specific release workflow is prepared for v0.3.6 only, and does not publish prereleases or other versions.

A future authorized push to `main` runs packaging checks, Home Assistant tests, editor and browser tests, HACS and Hassfest in [Validate Resideo Native](https://github.com/Kosztyk/resideo_native/actions/workflows/validate.yml).

After successful validation of a push to the current `main` commit, the [release workflow](https://github.com/Kosztyk/resideo_native/actions/workflows/release.yml) checks the validated SHA, exact manifest version and existing release, then publishes v0.3.6 as the latest stable release. The notes identify the validated commit and run. Assets include source and manual installation ZIPs with SHA-256 checksums. No hosted checks have run for this offline candidate.

HACS reads the integration from the release tag. Users with the repository added as a HACS custom integration can download the update and restart Home Assistant after publication. Catalog inclusion is managed by HACS separately.
