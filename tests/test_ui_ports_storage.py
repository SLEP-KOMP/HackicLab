"""Тесты UI: где живут карта портов, накопители и проверка флешки."""
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
            # USBToolBox-кекст и карта портов включаются в обеих сборках
            self.assertTrue(window.wiz_usb_chk.isChecked())
            self.assertTrue(window.opt_usb.isChecked())
            self.assertTrue(hasattr(window, "wiz_usb_map"))
            self.assertTrue(hasattr(window, "build_usb_map"))
            # на записи карты больше нет — только проверка флешки
            self.assertFalse(hasattr(window, "usb_map_chk"))
            self.assertTrue(hasattr(window, "usb_verify_btn"))
            # своя EFI: карта портов, диски и загрузчики
            self.assertTrue(hasattr(window, "ports_picker"))
            self.assertTrue(hasattr(window, "storage_warn"))
        finally:
            window.close()
            window.deleteLater()

    def test_panels_default_to_auto(self):
        from hackiclab.ui.main_window import MainWindow

        window = MainWindow()
        try:
            # обычный пользователь ничего не выбирает: режим «Автоматически»
            for panel in (window.wiz_usb_map, window.build_usb_map):
                self.assertTrue(panel.enabled())
                self.assertEqual(panel.mode(), "auto")
                self.assertIsNone(panel.ports())
                self.assertFalse(panel.picker.isVisibleTo(panel))
            # ручной режим показывает пикер портов
            window.wiz_usb_map.mode_combo.setCurrentIndex(1)
            self.assertEqual(window.wiz_usb_map.mode(), "manual")
            self.assertTrue(window.wiz_usb_map.picker.isVisibleTo(window.wiz_usb_map))
            self.assertEqual(window._wiz_state()["usb_mode"], "manual")
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

    def test_wizard_options_step_is_scrollable(self):
        from PySide6.QtWidgets import QScrollArea

        from hackiclab.ui.main_window import MainWindow

        window = MainWindow()
        try:
            pages = [window.wiz_stack.widget(i)
                     for i in range(window.wiz_stack.count())]
            self.assertTrue(any(isinstance(p, QScrollArea) for p in pages))
        finally:
            window.close()
            window.deleteLater()

    def test_storage_notes_render_on_usb_tab(self):
        from hackiclab.scanner.models import CPUInfo, HardwareProfile, StorageInfo
        from hackiclab.ui.main_window import MainWindow

        window = MainWindow()
        try:
            profile = HardwareProfile(platform="desktop")
            profile.cpu = CPUInfo(name="Intel Core i5", vendor="intel", generation=9)
            profile.storage = StorageInfo(controllers=["Samsung PM981"])
            window.profile = profile
            window._usb_refresh_storage_warn()
            self.assertIn("PM981", window.usb_storage_warn.text())
            window._refresh_storage_notes()
            self.assertIn("PM981", window.storage_warn.text())
        finally:
            window.close()
            window.deleteLater()

    def test_sip_secureboot_bootargs_are_automatic(self):
        """SIP, SecureBootModel и boot-args не выбираются руками:
        их считает сборщик по железу, macOS и набору патчей."""
        from hackiclab.ui.main_window import MainWindow

        window = MainWindow()
        try:
            for name in ("opt_sip", "build_sbm", "build_boot_args",
                         "wiz_bootargs"):
                self.assertFalse(hasattr(window, name), name)
        finally:
            window.close()
            window.deleteLater()

    def test_verify_requires_device(self):
        from hackiclab.ui.main_window import MainWindow

        window = MainWindow()
        try:
            window.usb_devices = []
            window.usb_combo.clear()
            window._usb_verify()
            self.assertTrue(window.usb_verify_status.text())
        finally:
            window.close()
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
