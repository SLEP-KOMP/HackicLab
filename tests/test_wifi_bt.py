"""База Wi-Fi/BT-адаптеров: что macOS поддерживает, а что нет."""
from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.knowledge import manual_hw, wifi_bt


class AdapterDbTests(unittest.TestCase):
    def test_supported_families(self):
        for name in (
            "Broadcom 802.11ac Network Adapter",
            "Broadcom BCM94360CD",
            "Intel(R) Wi-Fi 6 AX201 160MHz",
            "Intel(R) Wi-Fi 6E AX211 160MHz",
            "Killer(R) Wi-Fi 6 AX1650i 160MHz Wireless Network Adapter (201NGW)",
            "Atheros AR9285 Wireless Network Adapter",
            "Intel(R) Dual Band Wireless-AC 8265",
        ):
            self.assertFalse(wifi_bt.is_unsupported("", name), name)

    def test_unsupported_models(self):
        for name in (
            "MediaTek Wi-Fi 7 MT7925 Wireless LAN Card",
            "MediaTek MT7921",
            "Realtek RTL8852BE WiFi 6 802.11ax PCIe Adapter",
            "Realtek RTL8822CE",
            "Qualcomm Atheros QCA6174 802.11ac Wireless Network Adapter",
            "Intel(R) Wi-Fi 7 BE200 320MHz",
            "Killer Wi-Fi 6E 1675x",
            "Broadcom BCM43142",
        ):
            self.assertTrue(wifi_bt.is_unsupported("", name), name)

    def test_chipset_only_fallback(self):
        self.assertTrue(wifi_bt.is_unsupported("mediatek"))
        self.assertTrue(wifi_bt.is_unsupported("realtek"))
        self.assertTrue(wifi_bt.is_unsupported("qualcomm"))
        self.assertFalse(wifi_bt.is_unsupported("intel"))
        self.assertFalse(wifi_bt.is_unsupported("broadcom"))

    def test_support_details(self):
        info = wifi_bt.support("Intel(R) Wi-Fi 6 AX201 160MHz")
        self.assertTrue(info["supported"])
        self.assertIn("itlwm", info["kexts"])
        bad = wifi_bt.support("MediaTek Wi-Fi 7 MT7925")
        self.assertFalse(bad["supported"])
        self.assertTrue(bad["ru"])

    def test_manual_wifi_options_marked(self):
        values = {value for value, _ in manual_hw.WIFI_OPTIONS}
        self.assertTrue({"intel", "broadcom", "atheros"} <= values)
        self.assertTrue({"mediatek", "realtek", "qualcomm"} <= values)
        for value in ("mediatek", "realtek", "qualcomm"):
            self.assertIn(value, manual_hw.WIFI_NOTES)


if __name__ == "__main__":
    unittest.main()
