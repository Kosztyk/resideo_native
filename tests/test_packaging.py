"""Resideo Native packaging tests: no network, accounts, or HA runtime."""

import importlib.util
import json
import runpy
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/resideo_native"
spec = importlib.util.spec_from_file_location(
    "resideo_packaging", ROOT / "tools/check_repository.py"
)
assert spec and spec.loader
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class PackagingTests(unittest.TestCase):
    def test_repository_structure(self):
        self.assertEqual(checker.inspect_repository(ROOT), [])

    def test_release_and_manifest(self):
        data = json.loads((COMPONENT / "manifest.json").read_text())
        self.assertEqual(data["domain"], "resideo_native")
        self.assertEqual(data["version"], runpy.run_path(str(COMPONENT / "const.py"))["VERSION"])
        self.assertEqual(
            data["dependencies"],
            ["binary_sensor", "climate", "select", "sensor", "switch", "water_heater"],
        )

    def test_release_and_prerelease_version_formats(self):
        for version in ("0.3.4", "0.3.5b1", "0.3.5b12", "1.0.0a0", "1.0.0rc1"):
            with self.subTest(version=version):
                self.assertIsNotNone(checker.VERSION_PATTERN.fullmatch(version))
        for version in ("0.3", "v0.3.5b1", "0.3.5b", "0.3.5b-1", "0.3.5b1oops"):
            with self.subTest(version=version):
                self.assertIsNone(checker.VERSION_PATTERN.fullmatch(version))

    def test_hacs_metadata(self):
        data = json.loads((ROOT / "hacs.json").read_text())
        self.assertEqual(data["name"], "Resideo Native")
        self.assertTrue(data["render_readme"])


if __name__ == "__main__":
    unittest.main()
