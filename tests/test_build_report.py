"""Тесты отчёта о сборке: разделы, железо, итог и ошибки."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.knowledge.build_report import build_report


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

        text = build_report(profile, BuildOptions(target_macos="Sonoma"), Result())
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
        text = build_report(profile, None, Result())
        self.assertIn("worked: build failed", text)
        self.assertIn("Missing key", text)

    def test_note_states_what_report_confirms(self):
        from hackiclab.scanner.models import HardwareProfile

        class Result:
            ok = True
            errors: list = []

        text = build_report(HardwareProfile(), None, Result())
        self.assertIn("not that macOS booted", text)
