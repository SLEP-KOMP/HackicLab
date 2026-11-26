"""Тесты проверки пересечений Kernel/Patch и выбора SecureBootModel."""

from __future__ import annotations

import plistlib
import unittest

import _bootstrap  # noqa: F401

from hackiclab.builder.config_gen import BuildOptions, generate_config_plist
from hackiclab.builder.patch_check import find_conflicts
from hackiclab.scanner.models import CPUInfo, HardwareProfile


def _patch(comment: str, lo: str, hi: str, enabled: bool = True) -> dict:
    return {"Comment": comment, "Identifier": "kernel", "MinKernel": lo,
            "MaxKernel": hi, "Enabled": enabled,
            "Find": b"\x01", "Replace": b"\x02"}


class PatchConflictTests(unittest.TestCase):
    def test_same_operation_overlapping_is_flagged(self):
        patches = [
            _patch("algrey | _mtrr_update_action | fix PAT | 10.13+", "17.0.0", "23.99.99"),
            _patch("Shaneee | _mtrr_update_action | Fix PAT | 10.13+",
                   "17.0.0", "23.99.99"),
        ]
        conflicts = find_conflicts(patches)
        self.assertEqual(len(conflicts), 1)
        self.assertIn("PAT", conflicts[0].describe())

    def test_same_operation_separate_ranges_is_fine(self):
        patches = [
            _patch("algrey | _cpuid_set_generic_info | allow leaf7 | 10.13+",
                   "17.0.0", "23.99.99"),
            _patch("algrey | _cpuid_set_generic_info | allow leaf7 | 15.0+",
                   "24.0.0", "25.99.99"),
        ]
        self.assertEqual(find_conflicts(patches), [])

    def test_different_operations_on_one_function_are_fine(self):
        patches = [
            _patch("algrey | _cpuid_set_generic_info | Remove wrmsr(0x8B) | 10.13+",
                   "17.0.0", "25.99.99"),
            _patch("algrey | _cpuid_set_generic_info | Set flag=1 | 10.13+",
                   "17.0.0", "25.99.99"),
        ]
        self.assertEqual(find_conflicts(patches), [])

    def test_disabled_patch_is_ignored(self):
        patches = [
            _patch("algrey | _mtrr_update_action | fix PAT | 10.13+", "17.0.0", "23.99.99"),
            _patch("Shaneee | _mtrr_update_action | Fix PAT | 10.13+",
                   "17.0.0", "23.99.99", enabled=False),
        ]
        self.assertEqual(find_conflicts(patches), [])


class SecureBootModelTests(unittest.TestCase):
    def _cfg(self, model: str) -> dict:
        profile = HardwareProfile(platform="desktop")
        profile.cpu = CPUInfo(name="AMD Ryzen 5 3600", vendor="amd", generation=10)
        return plistlib.loads(generate_config_plist(
            profile, BuildOptions(target_macos="Sequoia", secure_boot_model=model)))

    def test_default_model_is_applied(self):
        cfg = self._cfg("Default")
        self.assertEqual(cfg["Misc"]["Security"]["SecureBootModel"], "Default")

    def test_disabled_is_applied(self):
        cfg = self._cfg("Disabled")
        self.assertEqual(cfg["Misc"]["Security"]["SecureBootModel"], "Disabled")


if __name__ == "__main__":
    unittest.main()
