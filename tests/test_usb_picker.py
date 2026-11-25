"""Тесты интерактивного выбора USB-портов (UsbPortPicker) и опции сборки."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.builder.config_gen import BuildOptions
from hackiclab.builder.usb_map import MAX_PORTS_PER_CONTROLLER, build_map_plist, count_ports


def _controller(name: int, count: int) -> dict:
    return {
        "identifiers": {"bdf": [0, name, 0]},
        "ports": [{"index": i, "type": 3, "class": "SuperSpeed", "guessed": 3}
                  for i in range(1, count + 1)],
    }


class BuildOptionsUsbTests(unittest.TestCase):
    def test_usb_ports_defaults_to_auto(self):
        self.assertIsNone(BuildOptions().usb_ports)

    def test_usb_ports_keeps_selection(self):
        sel = {("0-20-0", "HS01")}
        self.assertEqual(BuildOptions(usb_ports=sel).usb_ports, sel)


class PickerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest(f"PySide6 недоступен: {exc}") from None
        cls.app = QApplication.instance() or QApplication([])

    def _picker(self):
        from hackiclab.ui.usb_picker import UsbPortPicker

        picker = UsbPortPicker()
        plist = build_map_plist([_controller(20, 20)], limit=None)
        assert plist is not None
        picker.set_plist(plist)
        return picker

    def test_default_checks_fifteen_ports(self):
        picker = self._picker()
        self.assertEqual(len(picker.selection()), MAX_PORTS_PER_CONTROLLER)

    def test_summary_reports_count(self):
        picker = self._picker()
        self.assertIn("15", picker.summary.text())

    def test_filtered_map_matches_selection(self):
        picker = self._picker()
        filtered = picker.filtered()
        assert filtered is not None
        self.assertEqual(count_ports(filtered),
                         {"0-20-0": MAX_PORTS_PER_CONTROLLER})

    def test_unchecking_port_shrinks_map(self):
        from PySide6.QtCore import Qt

        picker = self._picker()
        group = picker.tree.topLevelItem(0)
        group.child(0).setCheckState(0, Qt.CheckState.Unchecked)
        self.assertEqual(len(picker.selection()), MAX_PORTS_PER_CONTROLLER - 1)
        filtered = picker.filtered()
        assert filtered is not None
        self.assertEqual(count_ports(filtered),
                         {"0-20-0": MAX_PORTS_PER_CONTROLLER - 1})

    def test_over_limit_is_flagged(self):
        from PySide6.QtCore import Qt

        picker = self._picker()
        group = picker.tree.topLevelItem(0)
        group.child(MAX_PORTS_PER_CONTROLLER).setCheckState(0, Qt.CheckState.Checked)
        self.assertIn("macOS", picker.summary.text())
        self.assertEqual(picker.summary.property("tone"), "err")

    def test_restore_selection_from_state(self):
        picker = self._picker()
        keep = {("0-20-0", "SS01")}
        picker.set_plist(picker.plist(), selected=keep)
        self.assertEqual(picker.selection(), keep)


if __name__ == "__main__":
    unittest.main()
