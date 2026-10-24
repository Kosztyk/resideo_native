"""Reviewer regressions: metadata and honest hardware-validation wording."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/resideo_native"

class HACSWriteVerificationTests(unittest.TestCase):
    def test_release_version(self):
        m = json.loads((COMP / "manifest.json").read_text())
        self.assertEqual(m["version"], "0.1.7")

    def test_review_documentation_identifies_hardware_and_unknown_firmware(self):
        readme = (ROOT / "README.md").read_text()
        validation = (ROOT / "VALIDATION.md").read_text()
        self.assertIn("Jasper", readme)
        self.assertIn("set_mode", validation)
        self.assertIn("set_temperature", validation)
        self.assertIn("set_hold", validation)
        self.assertIn("sw_version", validation)
        self.assertNotIn("Physical command acceptance remains to be verified on real devices.", readme)

if __name__ == "__main__":
    unittest.main()
