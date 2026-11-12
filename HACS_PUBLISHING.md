# Resideo Native v0.3.3 — GitHub release and HACS publication

This bundle prepares the next release; it does not itself publish a release.
Do not manually create a tag before the validated GitHub Actions workflow runs.

1. Use `bash publish_v0.3.3.sh` on macOS or Linux with Git and Python 3 to clone
   `Kosztyk/resideo_native`, apply the complete v0.3.3 integration, update the
   repository docs/metadata/tests and show a diff **without pushing**.
2. Run `bash publish_v0.3.3.sh --push` when ready. The script prompts for
   approval before committing/pushing. It does not require Homebrew or `gh`.
   GitHub authentication is handled by ordinary Git credential management.
3. A push to `main` triggers `.github/workflows/validate.yml`: packaging,
   Python/Home Assistant tests, JavaScript/browser tests, HACS and Hassfest.
4. After the validation run for **that exact current main commit** succeeds,
   `.github/workflows/release.yml` will create `v0.3.3` and attach the repository
   source ZIP and SHA-256 file. The workflow is explicitly gated to `0.3.3`,
   does not publish stale commits, and skips if the release already exists.
5. Verify all checks and the release on
   https://github.com/Kosztyk/resideo_native/actions and
   https://github.com/Kosztyk/resideo_native/releases.
6. HACS custom-repository users can update from the newly published tag and
   restart Home Assistant. This does not automatically add the integration to
   the default HACS catalog.

If `main` is protected or the account cannot push, Git displays the error; the
script does not force push, bypass protections, or create a release regardless
of validation. Push a reviewed branch/PR instead.

No personal access token should be placed in this archive or a shell script.
