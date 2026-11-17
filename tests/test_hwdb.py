"""Тесты базы реальных отчётов hackmate-hwdb: разбор логов и матчинг."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.knowledge import hwdb
from hackiclab.scanner.models import AudioInfo, CPUInfo, GPUInfo, HardwareProfile, NetInfo

SAMPLE = """device: ThinkPad T480
feature: full
submitted by: someone
date: 2026-07-15

--- hardware ---
cpu: Intel(R) Core(TM) i5-8350U CPU @ 1.70GHz
cpu_generation: 8
cpu_codename: Kaby Lake-R
platform: laptop

igpu: Intel UHD Graphics 620
dgpu: none

audio_codec: ALC257
ethernet_chipset: Intel I219-V
wifi_chipset: intel

touchpad_type: i2c
nvme: yes
thunderbolt: yes

--- result ---
hackmate_version: v2.0.0
macos_version: macOS Sonoma (14)
worked: build completed
issues: none
notes: wifi works after itlwm
"""


def laptop_profile():
    profile = HardwareProfile(platform="laptop")
    profile.cpu = CPUInfo(name="Intel Core i5-1135G7", vendor="intel", generation=11,
                          codename="Tiger Lake")
    profile.igpu = GPUInfo(name="Intel Iris Xe Graphics", vendor="intel", is_integrated=True)
    profile.audio = AudioInfo(codec="")
    profile.net = NetInfo(eth_chipset="i219", wifi_chipset="intel")
    return profile


def amd_profile():
    profile = HardwareProfile(platform="desktop")
    profile.cpu = CPUInfo(name="AMD Ryzen 7 7800X3D", vendor="amd", generation=12,
                          codename="Zen 4")
    return profile


class ParseTests(unittest.TestCase):
    def test_fields_are_parsed(self):
        report = hwdb.parse_log(SAMPLE, "full-build-logs/intel-gen8/thinkpad-t480.log")
        assert report is not None
        self.assertEqual(report.device, "ThinkPad T480")
        self.assertEqual(report.feature, "full")
        self.assertEqual(report.vendor, "intel")
        self.assertEqual(report.generation, 8)
        self.assertEqual(report.codename, "Kaby Lake-R")
        self.assertEqual(report.platform, "laptop")
        self.assertTrue(report.nvme)
        self.assertTrue(report.thunderbolt)
        self.assertTrue(report.succeeded)
        self.assertFalse(report.failed)
        self.assertEqual(report.macos, "macOS Sonoma (14)")

    def test_multiline_issues_are_joined(self):
        text = SAMPLE.replace("issues: none", "issues: diskpart failed:\nno media in the device")
        report = hwdb.parse_log(text)
        assert report is not None
        self.assertIn("no media in the device", report.issues)

    def test_empty_template_is_skipped(self):
        text = (
            "device: <vendor + model, e.g. ThinkPad T480>\n"
            "cpu: <full cpu name>\n"
            "worked: <yes / no / partial>\n"
        )
        self.assertIsNone(hwdb.parse_log(text))

    def test_feature_falls_back_to_directory(self):
        report = hwdb.parse_log(SAMPLE.replace("feature: full", "feature: x"),
                                "repair-efi-logs/intel-gen8/thinkpad.log")
        assert report is not None
        self.assertEqual(report.feature, "repair")

    def test_failed_report_is_not_success(self):
        report = hwdb.parse_log(SAMPLE.replace("worked: build completed",
                                               "worked: build failed"))
        assert report is not None
        self.assertTrue(report.failed)
        self.assertFalse(report.succeeded)


class BundledDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reports = hwdb.load_all()

    def test_snapshot_is_present(self):
        self.assertGreaterEqual(len(self.reports), 60)
        self.assertEqual(hwdb.count(), len(self.reports))

    def test_all_features_and_vendors_covered(self):
        self.assertEqual({report.feature for report in self.reports},
                         {"full", "formatted", "repair", "no_usb", "dual_boot", "health"})
        self.assertEqual({report.vendor for report in self.reports}, {"amd", "intel"})

    def test_every_report_has_device_and_result(self):
        for report in self.reports:
            self.assertTrue(report.device or report.cpu, report.path)
            self.assertTrue(report.worked, report.path)
            self.assertNotIn("<", report.device, report.path)

    def test_attribution_files_exist(self):
        root = hwdb._dir()
        for name in ("ATTRIBUTION.md", "README.upstream.md", "TEMPLATE.log"):
            self.assertTrue((root / name).is_file(), name)


class MatchTests(unittest.TestCase):
    def test_laptop_matches_same_generation(self):
        found = hwdb.match(laptop_profile())
        self.assertTrue(found)
        for report, score in found:
            self.assertGreaterEqual(score, 4)
            self.assertEqual(report.platform, "laptop")
            self.assertEqual(report.vendor, "intel")

    def test_results_are_sorted_by_score(self):
        scores = [score for _report, score in hwdb.match(laptop_profile(), limit=10)]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_amd_zen_matching_uses_codename(self):
        found = hwdb.match(amd_profile())
        self.assertTrue(found)
        for report, _score in found:
            self.assertEqual(report.vendor, "amd")
            self.assertIn("zen 4", {report.codename.lower(), "zen 4"})

    def test_foreign_platform_is_rejected(self):
        profile = amd_profile()
        profile.platform = "laptop"
        for report, _score in hwdb.match(profile, limit=10):
            self.assertEqual(report.platform, "laptop")

    def test_no_profile_returns_nothing(self):
        self.assertEqual(hwdb.match(None), [])
        self.assertEqual(hwdb.summary(None)["similar"], 0)

    def test_summary_counts_add_up(self):
        data = hwdb.summary(laptop_profile())
        self.assertEqual(data["total"], hwdb.count())
        self.assertEqual(data["ok"] + data["failed"] + data["partial"], data["similar"])
        self.assertEqual(len(data["reports"]), data["similar"])


class BuildReportTests(unittest.TestCase):
    def test_report_has_template_sections(self):
        from hackiclab.builder.config_gen import BuildOptions
        from hackiclab.scanner.models import AudioInfo, CPUInfo, GPUInfo, HardwareProfile, NetInfo

        profile = HardwareProfile(platform="desktop", board_vendor="ASUS", board_name="B450")
        profile.cpu = CPUInfo(name="AMD Ryzen 5 3600", vendor="amd", generation=10,
                              codename="Zen 2")
        profile.dgpu = GPUInfo(name="Radeon RX 580", vendor="amd")
        profile.audio = AudioInfo(name="Realtek", codec="ALC1220")
        profile.net = NetInfo(eth_chipset="i211", wifi_chipset="intel")

        class Result:
            ok = True
            errors: list = []

        text = hwdb.build_report(profile, BuildOptions(target_macos="Sonoma"), Result())
        self.assertIn("--- hardware ---", text)
        self.assertIn("--- result ---", text)
        self.assertIn("cpu: AMD Ryzen 5 3600", text)
        self.assertIn("worked: build completed", text)
        self.assertIn("macos_version: Sonoma", text)

    def test_failed_report_lists_errors(self):
        class Result:
            ok = False
            errors = ["ocvalidate: Missing key"]

        from hackiclab.scanner.models import CPUInfo, HardwareProfile

        profile = HardwareProfile(platform="desktop")
        profile.cpu = CPUInfo(name="Intel Core i5-9400", vendor="intel", generation=9)
        text = hwdb.build_report(profile, None, Result())
        self.assertIn("worked: build failed", text)
        self.assertIn("Missing key", text)
