"""Тесты страницы валидации: плитки-метрики."""
from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401


class ValidateTilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest(f"PySide6 недоступен: {exc}") from None
        cls.app = QApplication.instance() or QApplication([])

    def test_tiles_show_errors_and_warnings(self):
        from hackiclab.ui.main_window import MainWindow

        window = MainWindow()
        try:
            window._set_val_tiles("err", 3, 5)
            self.assertEqual(window.val_tile_err.text(), "3")
            self.assertEqual(window.val_tile_warn.text(), "5")
            self.assertEqual(window.val_tile_state.property("tone"), "err")
            window._set_val_tiles("ok", 0, 0)
            self.assertEqual(window.val_tile_state.property("tone"), "ok")
        finally:
            window.close()
            window.deleteLater()

    def test_efi_root_for_folder(self):
        from pathlib import Path

        from hackiclab.ui.main_window import _efi_root_for

        self.assertEqual(_efi_root_for(r"C:\build\oc-lab"), Path(r"C:\build\oc-lab"))
        self.assertEqual(_efi_root_for(r"C:\build\oc-lab\EFI"), Path(r"C:\build\oc-lab"))
        self.assertEqual(_efi_root_for(r"C:\build\oc-lab\efi"), Path(r"C:\build\oc-lab"))

    def test_manual_build_makes_validation_see_config(self):
        from pathlib import Path
        from types import SimpleNamespace

        from hackiclab.ui.main_window import MainWindow

        window = MainWindow()
        try:
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                cfg = root / "EFI" / "OC" / "config.plist"
                cfg.parent.mkdir(parents=True)
                cfg.write_text("<plist/>", encoding="utf-8")
                window.profile = None
                window._build_done(SimpleNamespace(ok=True, root=root, errors=[], log=[], stats={}))
                self.assertEqual(window.last_build_dir, root)
                self.assertEqual(window._resolve_config(), cfg)
        finally:
            window.close()
            window.deleteLater()

