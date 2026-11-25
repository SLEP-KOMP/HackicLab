"""Тесты каталога тем OpenCanopy и карточек выбора."""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from hackiclab.knowledge import themes

_PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 24 + b"IEND" + b"\x00" * 4


def _icns(png: bytes = _PNG) -> bytes:
    chunk = struct.pack(">4sI", b"ic07", 8 + len(png)) + png
    return b"icns" + struct.pack(">I", 8 + len(chunk)) + chunk


class ThemeCatalogTests(unittest.TestCase):
    def test_variants_have_full_ids(self):
        ids = themes.variant_ids()
        self.assertIn("Acidanthera\\GoldenGate", ids)
        self.assertEqual(len(ids), 3)

    def test_picker_variant_accepts_short_and_full(self):
        self.assertEqual(themes.picker_variant("GoldenGate"),
                         "Acidanthera\\GoldenGate")
        self.assertEqual(themes.picker_variant("Acidanthera\\GoldenGate"),
                         "Acidanthera\\GoldenGate")

    def test_labels_are_localised(self):
        self.assertIn("GoldenGate", themes.variant_label("GoldenGate", "ru"))
        self.assertIn("dark", themes.variant_label("GoldenGate", "en"))

    def test_extract_png_from_icns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "HardDrive.icns"
            path.write_bytes(_icns())
            self.assertEqual(themes.extract_png(path), _PNG)

    def test_extract_png_returns_none_for_garbage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.icns"
            path.write_bytes(b"not an icns")
            self.assertIsNone(themes.extract_png(path))

    def test_available_reports_existing_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "Image" / "Acidanthera" / "Syrah"
            folder.mkdir(parents=True)
            (folder / "HardDrive.icns").write_bytes(_icns())
            self.assertEqual(themes.available(Path(tmp)), ["Acidanthera\\Syrah"])

    def test_preview_pngs_uses_theme_icons(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "Image" / "Acidanthera" / "Syrah"
            folder.mkdir(parents=True)
            (folder / "HardDrive.icns").write_bytes(_icns())
            pngs = themes.preview_pngs(Path(tmp), "Syrah")
            self.assertEqual(pngs, [_PNG])


class ThemeCardsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest(f"PySide6 недоступен: {exc}") from None
        cls.app = QApplication.instance() or QApplication([])

    def _cards(self):
        from hackiclab.ui.theme_cards import ThemeCards

        return ThemeCards()

    def test_empty_by_default(self):
        self.assertEqual(self._cards().selection(), set())

    def test_set_selection_marks_variant(self):
        cards = self._cards()
        cards.set_selection({"Acidanthera\\GoldenGate"})
        self.assertEqual(cards.selection(), {"Acidanthera\\GoldenGate"})

    def test_select_all_checks_every_variant(self):
        cards = self._cards()
        cards.select_all()
        self.assertEqual(cards.selection(), set(themes.variant_ids()))


class ThemeConfigTests(unittest.TestCase):
    """PickerVariant попадает в config.plist из выбранной темы."""

    def _boot(self, options):
        import plistlib

        from hackiclab.builder.config_gen import BuildOptions, generate_config_plist
        from hackiclab.scanner.models import CPUInfo, HardwareProfile

        profile = HardwareProfile(platform="desktop")
        profile.cpu = CPUInfo(name="Intel Core i5", vendor="intel", generation=9)
        cfg = plistlib.loads(generate_config_plist(profile, options))
        return cfg["Misc"]["Boot"]

    def test_custom_variant_is_written(self):
        from hackiclab.builder.config_gen import BuildOptions

        boot = self._boot(BuildOptions(gui_picker=True,
                                       picker_variant="Acidanthera\\Syrah"))
        self.assertEqual(boot["PickerVariant"], "Acidanthera\\Syrah")
        self.assertEqual(boot["PickerMode"], "External")

    def test_default_variant_when_not_selected(self):
        from hackiclab.builder.config_gen import BuildOptions

        boot = self._boot(BuildOptions(gui_picker=True))
        self.assertEqual(boot["PickerVariant"], "Acidanthera\\GoldenGate")


if __name__ == "__main__":
    unittest.main()
