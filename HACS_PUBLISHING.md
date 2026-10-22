# Resideo Native — HACS publishing checklist

1. Verify all three checks in the HACS-readiness Pull Request: HACS, Hassfest,
   Packaging and Python.
2. Merge the PR into `main`.
3. Verify the **push** validation on the merged main commit succeeded.
4. The release workflow will publish `v0.1.6` only when the main branch
   check is successful and HEAD hasn't changed. If this does not happen,
   publish a full GitHub Release manually after a successful validation,
   targeting the validated commit. Use `RELEASE_NOTES_0.1.6.md`.
5. Verify the release and install through HACS > Custom repositories,
   category **Integration**, using
   `https://github.com/Kosztyk/resideo_native`.
6. In the `Kosztyk/default` fork of `hacs/default`, add
   `"Kosztyk/resideo_native"` alphabetically to the `integration` file.
7. Submit a PR to `hacs/default:master` using its official template.
   Tick all checkboxes and link the exact release, successful HACS job
   and successful Hassfest job. Do not request reviews or post unneeded comments.

Publishing rules: https://www.hacs.xyz/docs/publish/start/
