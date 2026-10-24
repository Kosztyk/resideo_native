# Resideo Native — HACS publishing checklist

1. Verify all three checks in the HACS-readiness Pull Request: HACS, Hassfest,
   Packaging and Python.
2. Merge the PR into `main`.
3. Verify the **push** validation on the merged main commit succeeded.
4. The release workflow will publish `v0.1.7` only when the main branch
   check is successful and HEAD hasn't changed. If this does not happen,
   publish a full GitHub Release manually after a successful validation,
   targeting the validated commit. Use `RELEASE_NOTES_0.1.7.md`.
5. Verify the release and install through HACS > Custom repositories,
   category **Integration**, using
   `https://github.com/Kosztyk/resideo_native`.
6. Continue the **existing** HACS review PR #12444; do not open a duplicate.
7. Update its release/HACS/Hassfest links after v0.1.7 is published,
   document maintainer-reported Jasper physical write testing, and submit
   for re-review as requested by the HACS maintainer.

Publishing rules: https://www.hacs.xyz/docs/publish/start/
