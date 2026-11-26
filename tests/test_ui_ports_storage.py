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
            # USBToolBox-кекст включается в обеих сборках
            self.assertTrue(window.wiz_usb_chk.isChecked())
            self.assertTrue(window.opt_usb.isChecked())
            # карта портов при записи и проверка флешки
            self.assertTrue(window.usb_map_chk.isChecked())
            self.assertTrue(hasattr(window, "usb_verify_btn"))
            # диагностика портов и накопителей — отдельная вкладка
            self.assertTrue(hasattr(window, "ports_picker"))
            self.assertTrue(hasattr(window, "storage_warn"))
        finally:
            window.close()
            window.deleteLater()

    def test_pickers_removed_from_build_and_wizard(self):
        from hackiclab.ui.main_window import MainWindow

        window = MainWindow()
        try:
            # дубли убраны: карта выбирается только на записи/диагностике
            self.assertFalse(hasattr(window, "build_usb_picker"))
            self.assertFalse(hasattr(window, "build_storage"))
            self.assertFalse(hasattr(window, "wiz_usb_picker"))
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

    def test_boot_args_field_adds_presets_once(self):
        from hackiclab.ui.main_window import MainWindow

        window = MainWindow()
        try:
            window.build_boot_args.setText("")
            window._add_boot_arg("npci=0x2000")
            window._add_boot_arg("npci=0x2000")
            window._add_boot_arg("unfairgva=1")
            text = window.build_boot_args.text().split()
            self.assertEqual(text.count("npci=0x2000"), 1)
            self.assertIn("unfairgva=1", text)
            # тот же выбор есть в мастере
            self.assertTrue(hasattr(window, "wiz_bootargs"))
        finally:
            window.close()
            window.deleteLater()

    def test_secure_boot_model_choice_exists(self):
        from hackiclab.ui.main_window import MainWindow

        window = MainWindow()
        try:
            options = [window.build_sbm.itemData(i)
                       for i in range(window.build_sbm.count())]
            self.assertIn("Disabled", options)
            self.assertIn("Default", options)
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
