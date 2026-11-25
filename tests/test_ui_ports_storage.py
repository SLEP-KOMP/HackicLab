"""Тесты UI: USB-карта в сборках и блок накопителей на вкладке «USB и накопители»."""
from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401


class PortsStorageUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest(f"PySide6 недоступен: {exc}") from None
        cls.app = QApplication.instance() or QApplication([])

    def test_widgets_exist(self):
        from hackiclab.ui.main_window import MainWindow

        window = MainWindow()
        try:
            # USB-карта доступна и в автосборке, и в ручной
            self.assertTrue(window.wiz_usb_chk.isChecked())
            self.assertTrue(window.opt_usb.isChecked())
            # накопители: подпись в сборке и карточка на отдельной вкладке
            self.assertTrue(hasattr(window, "build_storage"))
            self.assertTrue(hasattr(window, "storage_warn"))
        finally:
            window.close()
            window.deleteLater()

    def test_wizard_usb_toggle_writes_state(self):
        from hackiclab.ui.main_window import MainWindow

        window = MainWindow()
        try:
            window.wiz_usb_chk.setChecked(False)
            self.assertFalse(window._wiz_state()["usb_toolbox"])
            window.wiz_usb_chk.setChecked(True)
            self.assertTrue(window._wiz_state()["usb_toolbox"])
        finally:
            window.close()
            window.deleteLater()

    def test_storage_notes_render_for_profile(self):
        from hackiclab.scanner.models import CPUInfo, HardwareProfile, StorageInfo
        from hackiclab.ui.main_window import MainWindow

        window = MainWindow()
        try:
            profile = HardwareProfile(platform="desktop")
            profile.cpu = CPUInfo(name="Intel Core i5", vendor="intel", generation=9)
            profile.storage = StorageInfo(controllers=["Samsung PM981"])
            window._refresh_build_storage(profile)
            self.assertIn("PM981", window.build_storage.text())
            window.profile = profile
            window._refresh_storage_notes()
            self.assertIn("PM981", window.storage_warn.text())
        finally:
            window.close()
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
