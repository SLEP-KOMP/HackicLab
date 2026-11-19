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
