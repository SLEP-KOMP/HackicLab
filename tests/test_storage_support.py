"""Тесты предупреждений по накопителям (Anti-Hackintosh Buyers Guide)."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.knowledge.compat import warnings_for
from hackiclab.knowledge.storage_support import storage_notes, warnings
from hackiclab.scanner.models import CPUInfo, HardwareProfile, StorageInfo


def _profile(controllers=None, **storage) -> HardwareProfile:
    p = HardwareProfile(platform="desktop")
    p.cpu = CPUInfo(name="Intel Core i5-9400", vendor="intel", generation=9)
    p.storage = StorageInfo(controllers=list(controllers or []), **storage)
    return p


class StorageSupportTests(unittest.TestCase):
    def test_samsung_oem_nvme_is_blocker(self):
        notes = storage_notes(StorageInfo(controllers=["Samsung SSD 970 PM981 512GB"]))
        self.assertEqual([n.severity for n in notes], ["blocker"])

    def test_intel_600p_is_warning(self):
        notes = storage_notes(StorageInfo(controllers=["Intel SSD 660p 1TB"]))
        self.assertEqual([n.severity for n in notes], ["warning"])

    def test_asm1061_is_blocker(self):
        notes = storage_notes(StorageInfo(controllers=["ASMedia ASM1062 SATA Controller"]))
        self.assertEqual([n.severity for n in notes], ["blocker"])

    def test_good_drive_has_no_notes(self):
        self.assertEqual([], storage_notes(StorageInfo(controllers=["Samsung SSD 970 EVO 1TB"])))

    def test_empty_controllers_are_silent(self):
        self.assertEqual([], storage_notes(StorageInfo()))

    def test_warnings_follow_language(self):
        st = StorageInfo(controllers=["PM991"])
        self.assertTrue(warnings(st, "ru")[0].startswith("Samsung"))
        self.assertIn("will not boot", warnings(st, "en")[0])

    def test_compat_surfaces_storage_warning(self):
        ru = [r for r, _ in warnings_for(_profile(["Samsung PM981"]), "Sequoia")]
        self.assertTrue(any("PM981" in r for r in ru))

    def test_clean_storage_adds_no_compat_warning(self):
        ru = [r for r, _ in warnings_for(_profile(["Samsung SSD 970 EVO 1TB"]), "Sequoia")]
        self.assertFalse(any("PM981" in r for r in ru))


if __name__ == "__main__":
    unittest.main()
