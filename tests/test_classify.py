"""Тесты чистой классификации чипсетов Ethernet."""

from __future__ import annotations

import unittest

from hackiclab.scanner.classify import eth_chipset_from_name


class EthChipsetTests(unittest.TestCase):
    def test_intel_i211_is_not_generic_intel(self):
        self.assertEqual(
            eth_chipset_from_name("Intel(R) I211 Gigabit Network Connection"), "i211")

    def test_intel_families(self):
        self.assertEqual(eth_chipset_from_name("Intel(R) Ethernet Connection I219-V"), "i219")
        self.assertEqual(eth_chipset_from_name("Intel(R) I210 Gigabit Network Connection"), "i210")
        self.assertEqual(eth_chipset_from_name("Intel(R) Ethernet Controller I225-V"), "i225")
        self.assertEqual(eth_chipset_from_name("Intel(R) Ethernet Controller I226-V"), "i226")
        self.assertEqual(eth_chipset_from_name("Intel(R) I350 Gigabit Network Connection"), "i350")

    def test_realtek_families(self):
        self.assertEqual(eth_chipset_from_name("Realtek Gaming 2.5GbE Family Controller"), "rtl8125")
        self.assertEqual(eth_chipset_from_name("Realtek PCIe GbE Family Controller"), "rtl8111")
        self.assertEqual(eth_chipset_from_name("Realtek Ethernet Controller"), "realtek")

    def test_unknown_and_generic(self):
        self.assertEqual(eth_chipset_from_name("Intel(R) Ethernet Connection"), "intel")
        self.assertEqual(eth_chipset_from_name(""), "")
        self.assertEqual(eth_chipset_from_name("Some USB NIC"), "")


if __name__ == "__main__":
    unittest.main()
