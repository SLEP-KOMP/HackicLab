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


class UnknownConnectorTests(unittest.TestCase):
    """Порт без подключённого устройства не должен выдаваться за USB 2.0."""

    def test_empty_port_has_no_type(self):
        from hackiclab.builder.usb_map import _guess_port_type

        self.assertIsNone(_guess_port_type({"status": "NoDeviceConnected"}))

    def test_connected_superspeed_is_usb3(self):
        from hackiclab.builder.usb_map import _guess_port_type

        self.assertEqual(_guess_port_type({
            "status": "DeviceConnected", "class": "SuperSpeed",
            "type_c": False, "user_connectable": True}), 3)

    def test_connected_highspeed_is_usb2(self):
        from hackiclab.builder.usb_map import _guess_port_type

        self.assertEqual(_guess_port_type({
            "status": "DeviceConnected", "class": "HighSpeed",
            "type_c": False, "user_connectable": True}), 0)

    def _unknown_plist(self):
        from hackiclab.builder.usb_map import build_map_plist

        return build_map_plist([{
            "identifiers": {"bdf": [2, 0, 0]},
            "ports": [{"index": 1, "type": None, "guessed": None,
                       "status": "NoDeviceConnected", "class": "Unknown",
                       "type_c": False, "user_connectable": True}],
        }], limit=None)

    def test_map_omits_connector_when_unknown(self):
        from hackiclab.builder.usb_map import port_rows

        rows = port_rows(self._unknown_plist())
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["type_known"])

    def test_known_connector_keeps_flag(self):
        from hackiclab.builder.usb_map import port_rows

        plist = build_map_plist([_controller(20, 2)], limit=None)
        self.assertTrue(all(row["type_known"] for row in port_rows(plist)))

    def test_picker_shows_unknown_type_and_hint(self):
        from hackiclab.ui.usb_picker import UsbPortPicker

        picker = UsbPortPicker()
        picker.set_plist(self._unknown_plist())
        self.assertIn("не определён", picker.tree.topLevelItem(0).child(0).text(1))
        self.assertIn("3.0", picker.hint.text())


class SpeedClassTests(unittest.TestCase):
    """Скорость берём из ConnectionInfo.Speed, а не только из флагов протоколов."""

    def test_super_speed_by_speed_field(self):
        from hackiclab.builder.usb_map import _port_speed_class

        self.assertEqual(_port_speed_class({"ConnectionInfo": {"Speed": 3}}), "SuperSpeed")

    def test_high_speed_by_speed_field(self):
        from hackiclab.builder.usb_map import _port_speed_class

        self.assertEqual(_port_speed_class({"ConnectionInfo": {"Speed": 2}}), "HighSpeed")

    def test_falls_back_to_protocol_flags(self):
        from hackiclab.builder.usb_map import _port_speed_class

        port = {"ConnectionInfoV2": {"SupportedUsbProtocols": {"Usb300": 1}}}
        self.assertEqual(_port_speed_class(port), "SuperSpeed")

    def test_unknown_without_data(self):
        from hackiclab.builder.usb_map import _port_speed_class

        self.assertEqual(_port_speed_class({}), "Unknown")


if __name__ == "__main__":
    unittest.main()
