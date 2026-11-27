"""Reviewer regressions: metadata and honest hardware-validation wording."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/resideo_native"

class HACSWriteVerificationTests(unittest.TestCase):
    def test_versioned_frontend_assets_match_manifest(self):
        version = json.loads((COMP / "manifest.json").read_text())["version"]
        editor = (COMP / "www/schedule-editor.js").read_text()
        launcher = (COMP / "www/schedule-entity.js").read_text()
        self.assertIn(f'const EDITOR_VERSION = "{version}";', editor)
        self.assertIn(f'./schedule-editor-{version}.js', launcher)

    def test_stable_release_gate_and_versioned_notes(self):
        version = json.loads((COMP / "manifest.json").read_text())["version"]
        workflow = (ROOT / ".github/workflows/release.yml").read_text()
        self.assertIn(f'[[ "$VERSION" != "{version}" ]]', workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", workflow)
        self.assertIn("github.event.workflow_run.event == 'push'", workflow)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", workflow)
        self.assertIn('[[ "$CURRENT_SHA" != "$VALIDATED_SHA" ]]', workflow)
        self.assertTrue((ROOT / f"RELEASE_NOTES_{version}.md").is_file())
        for name in ("package.json", "package-lock.json"):
            self.assertEqual(json.loads((ROOT / name).read_text())["version"], version)

    def test_review_documentation_identifies_hardware_and_unknown_firmware(self):
        readme = (ROOT / "README.md").read_text()
        validation = (ROOT / "VALIDATION.md").read_text()
        self.assertIn("Jasper", readme)
        self.assertIn("Lyric T6 Pro", readme)
        self.assertIn("6.0.1.50", readme)
        self.assertIn("6.0.1.50", validation)
        self.assertIn("set_mode", validation)
        self.assertIn("set_temperature", validation)
        self.assertIn("set_hold", validation)
        self.assertIn("sw_version", validation)
        self.assertNotIn("Physical command acceptance remains to be verified on real devices.", readme)

if __name__ == "__main__":
    unittest.main()
