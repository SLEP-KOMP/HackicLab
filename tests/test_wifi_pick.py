"""Выбор Wi-Fi-адаптера: поддерживаемый важнее первого в списке Windows."""
from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.scanner.windows_scanner import pick_wifi, wifi_chipset_of
from hackiclab.scanner.models import HardwareProfile, NetInfo
from hackiclab.ui.hwview import hardware_rows


class PickWifiTests(unittest.TestCase):
    def test_supported_wins_over_first_enabled(self):
        names = ["MediaTek Wi-Fi 7 MT7925 Wireless LAN Card",
                 "Broadcom 802.11ac Network Adapter"]
        self.assertEqual("Broadcom 802.11ac Network Adapter", pick_wifi(names))

    def test_only_unsupported_enabled_returns_it(self):
        names = ["MediaTek Wi-Fi 7 MT7925 Wireless LAN Card"]
        self.assertEqual(names[0], pick_wifi(names))

    def test_empty_list(self):
        self.assertEqual("", pick_wifi([]))

    def test_chipset_detection(self):
        self.assertEqual("mediatek", wifi_chipset_of("MediaTek MT7925"))
        self.assertEqual("broadcom", wifi_chipset_of("Broadcom BCM94360"))
        self.assertEqual("intel", wifi_chipset_of("Intel Wi-Fi 6 AX210"))
        self.assertEqual("", wifi_chipset_of("Unknown adapter"))


class WifiNoteTests(unittest.TestCase):
    def _rows(self, net: NetInfo) -> dict:
        profile = HardwareProfile()
        profile.net = net
        return {row["key"]: row for row in hardware_rows(profile, "Sequoia")}

    def test_no_inactive_note_when_supported_adapter_active(self):
        net = NetInfo(wifi_name="Broadcom 802.11ac Network Adapter",
                      wifi_chipset="broadcom",
                      ignored_wifi=["MediaTek Wi-Fi 7 MT7925 Wireless LAN Card"])
        note = self._rows(net)["hw.wifi"]["note"]
        self.assertNotIn("неактивен", note)
        self.assertNotIn("MediaTek", note)

    def test_hint_to_enable_supported_adapter(self):
        net = NetInfo(wifi_name="MediaTek Wi-Fi 7 MT7925 Wireless LAN Card",
                      wifi_chipset="mediatek",
                      ignored_wifi=["Broadcom 802.11ac Network Adapter"])
        note = self._rows(net)["hw.wifi"]["note"]
        self.assertIn("нет драйвера macOS", note)
        self.assertIn("Broadcom", note)


if __name__ == "__main__":
    unittest.main()
