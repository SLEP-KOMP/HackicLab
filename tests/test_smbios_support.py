"""Тесты диапазонов macOS для SMBIOS-моделей и их учёта при выборе модели."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.knowledge.kexts import smbios_model_for
from hackiclab.knowledge.smbios_support import SUPPORT, pick, support, supports
from hackiclab.scanner.models import CPUInfo, HardwareProfile


def _profile(gen: int = 9, vendor: str = "intel", platform: str = "desktop"):
    p = HardwareProfile(platform=platform)
    p.cpu = CPUInfo(name="Intel Core", vendor=vendor, generation=gen)
    return p


class SmbiosSupportTests(unittest.TestCase):
    def test_known_model_range(self):
        self.assertEqual(support("MacPro7,1"), ("Catalina", "Tahoe"))
        self.assertIsNone(support("iMac99,9"))

    def test_supports_respects_both_bounds(self):
        self.assertTrue(supports("MacPro7,1", "Sequoia"))
        self.assertFalse(supports("MacPro7,1", "High Sierra"))
        self.assertFalse(supports("iMac19,1", "Tahoe"))

    def test_unknown_model_and_target_are_permissive(self):
        self.assertTrue(supports("iMac99,9", "Sequoia"))
        self.assertTrue(supports("MacPro7,1", ""))

    def test_imacpro_reaches_sequoia_but_not_tahoe(self):
        # iMac Pro (2017) поддерживается Apple до Sequoia; в Tahoe уже вычеркнут.
        self.assertEqual(support("iMacPro1,1"), ("High Sierra", "Sequoia"))
        self.assertTrue(supports("iMacPro1,1", "Sequoia"))
        self.assertFalse(supports("iMacPro1,1", "Tahoe"))

    def test_pick_returns_first_supported(self):
        ladder = ["iMac18,3", "iMac19,1", "iMac20,1", "MacPro7,1"]
        self.assertEqual(pick(ladder, "High Sierra"), "iMac18,3")
        self.assertEqual(pick(ladder, "Sequoia"), "iMac19,1")

    def test_all_table_entries_have_valid_order(self):
        from hackiclab.knowledge.smbios_support import index_of
        for model, (low, high) in SUPPORT.items():
            self.assertLessEqual(index_of(low), index_of(high), model)


class SmbiosSelectionTests(unittest.TestCase):
    def test_coffee_lake_on_high_sierra_gets_old_model(self):
        # iMac19,1 вышел в Mojave — на High Sierra он недопустим.
        model = smbios_model_for(_profile(9), "macOS High Sierra")
        self.assertEqual(model, "iMac18,3")

    def test_laptop_coffee_lake_on_ventura(self):
        model = smbios_model_for(_profile(8, platform="laptop"), "macOS Ventura")
        self.assertTrue(supports(model, "Ventura"))

    def test_laptop_on_high_sierra_gets_supported_model(self):
        model = smbios_model_for(_profile(6, platform="laptop"), "macOS High Sierra")
        self.assertTrue(supports(model, "High Sierra"))

    def test_default_behaviour_preserved_for_current_target(self):
        model = smbios_model_for(_profile(10), "macOS Sequoia")
        self.assertEqual(model, "iMac20,1")


if __name__ == "__main__":
    unittest.main()
