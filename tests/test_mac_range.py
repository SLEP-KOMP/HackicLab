"""Тесты диапазона macOS по железу (mac_range)."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.knowledge.mac_range import MacRange, index_of, mac_range
from hackiclab.scanner.models import CPUInfo, GPUInfo, HardwareProfile, NetInfo


def _profile(gen: int = 9, vendor: str = "intel"):
    p = HardwareProfile(platform="desktop")
    p.cpu = CPUInfo(name="Intel Core", vendor=vendor, generation=gen)
    return p


class MacRangeTests(unittest.TestCase):
    def test_amd_ceiling_is_tahoe_without_core2_label(self):
        p = _profile(0, "amd")
        p.dgpu = GPUInfo(name="RX 580", vendor="amd", device_id="6FDF")
        r = mac_range(p)
        self.assertEqual(r.highest, "Tahoe")
        self.assertEqual(r.recommended, "Tahoe")
        self.assertFalse(any("Core 2" in ru for ru, _ in r.reasons))

    def test_haswell_ceiling_monterey_and_preference_clamped(self):
        p = _profile(4)
        r = mac_range(p, "Sequoia")
        self.assertEqual(r.highest, "Monterey")
        self.assertEqual(r.recommended, "Monterey")
        self.assertTrue(any("выше потолка" in ru for ru, _ in r.reasons))

    def test_navi_and_i211_raise_minimum_to_monterey(self):
        p = _profile(9)
        p.net = NetInfo(eth_chipset="i211")
        p.dgpu = GPUInfo(vendor="amd", device_id="73E")
        r = mac_range(p, "Ventura")
        self.assertEqual(r.lowest, "Monterey")
        self.assertEqual(r.recommended, "Ventura")

    def test_preference_below_minimum_clamped_up(self):
        p = _profile(9)
        p.net = NetInfo(eth_chipset="i211")
        r = mac_range(p, "Big Sur")
        self.assertEqual(r.recommended, "Monterey")
        self.assertTrue(any("ниже минимума" in ru for ru, _ in r.reasons))

    def test_minimum_above_ceiling_returns_ceiling(self):
        p = _profile(2)
        p.dgpu = GPUInfo(vendor="amd", device_id="731")
        r = mac_range(p)
        self.assertEqual(r.highest, "High Sierra")
        self.assertEqual(r.recommended, "High Sierra")
        self.assertTrue(any("выше потолка" in ru for ru, _ in r.reasons))

    def test_golden_gate_never_recommended(self):
        p = _profile(9)
        r = mac_range(p, "macOS Golden Gate")
        self.assertEqual(r.recommended, "Sequoia")

    def test_unknown_preference_uses_ceiling(self):
        p = _profile(9)
        r = mac_range(p, "")
        self.assertEqual(r.recommended, r.highest)
        self.assertIsInstance(r, MacRange)

    def test_index_of_normalises_prefix(self):
        self.assertEqual(index_of("macOS Sequoia"), index_of("Sequoia"))
        self.assertEqual(index_of("чепуха"), -1)
        self.assertGreater(index_of("Tahoe"), index_of("Sonoma"))


if __name__ == "__main__":
    unittest.main()
