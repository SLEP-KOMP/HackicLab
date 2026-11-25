"""Тесты OCLP-патча: NVRAM OCLP-Settings = -allow_amfi."""

from __future__ import annotations

import plistlib
import unittest

import _bootstrap  # noqa: F401

from hackiclab.builder.config_gen import BuildOptions, generate_config_plist
from hackiclab.knowledge.patches import plan
from hackiclab.scanner.models import CPUInfo, HardwareProfile, NetInfo

_NVRAM = "7C436110-AB2A-4BBB-A880-FE41995C9F82"


def _broadcom_profile() -> HardwareProfile:
    p = HardwareProfile(platform="desktop")
    p.cpu = CPUInfo(name="Intel Core i5-9400", vendor="intel", generation=9)
    p.net = NetInfo(wifi_chipset="broadcom")
    return p


class OclpAmfiPlanTests(unittest.TestCase):
    def test_broadcom_on_sonoma_offers_oclp_flag(self):
        ids = {p.id for p in plan(_broadcom_profile(), "macOS Sonoma")}
        self.assertIn("wifi_broadcom_root", ids)
        self.assertIn("oclp_amfi", ids)

    def test_no_system_patches_no_oclp_flag(self):
        p = HardwareProfile(platform="desktop")
        p.cpu = CPUInfo(name="Intel Core i5-9400", vendor="intel", generation=9)
        self.assertNotIn("oclp_amfi", {i.id for i in plan(p, "macOS Sonoma")})

    def test_oclp_flag_not_offered_before_sonoma(self):
        ids = {p.id for p in plan(_broadcom_profile(), "macOS Ventura")}
        self.assertNotIn("oclp_amfi", ids)


class OclpAmfiConfigTests(unittest.TestCase):
    def _nvram(self, target: str, patches):
        cfg = plistlib.loads(generate_config_plist(
            _broadcom_profile(), BuildOptions(target_macos=target, patches=patches)))
        return cfg["NVRAM"]["Add"][_NVRAM]

    def test_flag_written_when_selected(self):
        nv = self._nvram("macOS Sonoma", {"oclp_amfi"})
        self.assertEqual(nv.get("OCLP-Settings"), "-allow_amfi")

    def test_flag_absent_when_not_selected(self):
        nv = self._nvram("macOS Sonoma", set())
        self.assertNotIn("OCLP-Settings", nv)

    def test_flag_absent_before_sonoma(self):
        nv = self._nvram("macOS Ventura", {"oclp_amfi"})
        self.assertNotIn("OCLP-Settings", nv)


class OclpAutoTargetTests(unittest.TestCase):
    """Пустая цель («Авто») не должна отключать версионные патчи."""

    def test_plan_with_empty_target_keeps_broadcom(self):
        ids = {p.id for p in plan(_broadcom_profile(), "")}
        self.assertIn("wifi_broadcom_efi", ids)
        self.assertIn("wifi_broadcom_root", ids)
        self.assertIn("oclp_amfi", ids)

    def test_config_with_empty_target_blocks_ioskywalk(self):
        cfg = plistlib.loads(generate_config_plist(
            _broadcom_profile(), BuildOptions(target_macos="", patches=None)))
        blocks = [b.get("Identifier") for b in (cfg["Kernel"].get("Block") or [])]
        self.assertIn("com.apple.iokit.IOSkywalkFamily", blocks)


if __name__ == "__main__":
    unittest.main()
