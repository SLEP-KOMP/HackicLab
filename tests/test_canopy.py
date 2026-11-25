"""Тесты проверки Resources для графического меню OpenCanopy."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from hackiclab.builder import canopy


class ResourcesCheckTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _fill(self):
        (self.root / "Font").mkdir()
        for name in ("Font_1x.bin", "Font_1x.png", "Font_2x.bin"):
            (self.root / "Font" / name).write_bytes(b"x")
        theme = self.root / "Image" / "Acidanthera" / "GoldenGate"
        theme.mkdir(parents=True)
        (theme / "HardDrive.icns").write_bytes(b"x")
        (self.root / "Label").mkdir()
        (self.root / "Label" / "Apple.lbl").write_bytes(b"x")

    def test_audio_folder_is_kept(self):
        self.assertIn("Audio", canopy._KEEP)

    def test_empty_folder_reports_everything(self):
        missing = canopy.missing_parts(self.root)
        self.assertIn("Font/Font_1x.bin", missing)
        self.assertIn("Image/Acidanthera/GoldenGate", missing)
        self.assertIn("Label", missing)

    def test_complete_resources_are_clean(self):
        self._fill()
        self.assertEqual(canopy.missing_parts(self.root), [])

    def test_other_variant_is_checked(self):
        self._fill()
        missing = canopy.missing_parts(self.root, "Syrah")
        self.assertIn("Image/Acidanthera/Syrah", missing)

    def test_none_means_no_resources(self):
        self.assertEqual(canopy.missing_parts(None), ["Resources"])


if __name__ == "__main__":
    unittest.main()
