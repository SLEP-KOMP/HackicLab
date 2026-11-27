"""Тесты модели поддержки сборки и потолков macOS."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.knowledge import configs as cfg
from hackiclab.knowledge import support
from hackiclab.knowledge.oc_platforms import MAX_MACOS_BY_GEN, max_macos_for
from hackiclab.scanner.models import CPUInfo, HardwareProfile


class CeilingTests(unittest.TestCase):
    def _profile(self, vendor: str, generation: int, name: str = "") -> HardwareProfile:
        p = HardwareProfile(platform="desktop")
        p.cpu = CPUInfo(name=name, vendor=vendor, generation=generation)
        return p

    def test_intel_ceiling_matches_apple_support(self):
        self.assertEqual(max_macos_for(self._profile("intel", 7)), "Ventura")
        self.assertEqual(max_macos_for(self._profile("intel", 9)), "Sequoia")
        self.assertEqual(max_macos_for(self._profile("intel", 10)), "Tahoe")
        self.assertEqual(max_macos_for(self._profile("intel", 6)), "Monterey")

    def test_amd_uses_its_own_ceiling(self):
        self.assertEqual(max_macos_for(self._profile("amd", 12)), "Tahoe")

    def test_skylake_x_is_not_limited_by_consumer_skylake(self):
        profile = self._profile("intel", 6, "Intel Core i9-7900X (Skylake-X)")
        self.assertEqual(max_macos_for(profile), "Sequoia")

    def test_all_generations_have_ceiling(self):
        for generation in range(0, 16):
            self.assertIn(generation, MAX_MACOS_BY_GEN)


class SupportReportTests(unittest.TestCase):
    def test_catalog_configs_are_supported(self):
        reports = {c.key: support.support_report(c) for c in cfg.all_configs()}
        unsupported = [k for k, r in reports.items() if r.level == support.LEVEL_NONE]
        # единственная запись без macOS — IdeaPad 3, это осознанное «не рекомендуется»
        self.assertEqual(unsupported, ["laptop_ideapad_3"])

    def test_reports_have_checks(self):
        report = support.support_report(cfg.all_configs()[0])
        keys = [key for key, _ in report.checks]
        self.assertIn("support.platform", keys)
        self.assertIn("support.plist", keys)
        self.assertTrue(report.details == () or report.details)

    def test_unsupported_config_has_no_build(self):
        idea = next(c for c in cfg.all_configs() if c.key == "laptop_ideapad_3")
        report = support.support_report(idea)
        self.assertEqual(report.level, support.LEVEL_NONE)
        self.assertFalse(report.ok)

    def test_every_config_has_structured_fields(self):
        for c in cfg.all_configs():
            self.assertIn(c.platform, ("desktop", "laptop", "mini", "workstation"), c.key)
            self.assertIn(c.vendor, ("intel", "amd"), c.key)
            self.assertTrue(c.generation >= 0, c.key)

    def test_kexts_in_catalog_exist_in_database(self):
        for c in cfg.all_configs():
            self.assertEqual(support._kexts_missing(c), [], c.key)

    def test_ssdts_in_catalog_exist(self):
        for c in cfg.all_configs():
            self.assertEqual(support._ssdts_missing(c), [], c.key)


if __name__ == "__main__":
    unittest.main()

class ModernIntelCeilingTests(unittest.TestCase):
    """11–15 поколения Intel доживают до Sequoia: Tahoe уже без Intel."""

    def test_modern_intel_reaches_sequoia(self):
        from hackiclab.knowledge.oc_platforms import max_macos_for
        from hackiclab.scanner.models import CPUInfo, HardwareProfile

        for generation in (11, 12, 13, 14, 15):
            profile = HardwareProfile(platform="desktop")
            profile.cpu = CPUInfo(name=f"Intel Core {generation}000", vendor="intel",
                                  generation=generation)
            self.assertEqual(max_macos_for(profile), "Sequoia", generation)
