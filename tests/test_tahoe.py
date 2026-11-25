"""Тесты правил macOS 26 (Tahoe): звук, Intel Bluetooth, OTA, WhateverGreen."""

from __future__ import annotations

import plistlib
import unittest

import _bootstrap  # noqa: F401

from hackiclab.builder.config_gen import BuildOptions, generate_config_plist
from hackiclab.knowledge.compat import warnings_for
from hackiclab.knowledge.patches import plan
from hackiclab.scanner.models import AudioInfo, CPUInfo, GPUInfo, HardwareProfile, NetInfo

_NVRAM = "7C436110-AB2A-4BBB-A880-FE41995C9F82"


def _profile() -> HardwareProfile:
    p = HardwareProfile(platform="desktop")
    p.cpu = CPUInfo(name="Intel Core i5-9400", vendor="intel", generation=9)
    p.audio = AudioInfo(codec="ALC1220", layout_id=11)
    p.net = NetInfo(bt_chipset="intel")
    return p


def _boot_args(target: str, patches=None) -> str:
    cfg = plistlib.loads(generate_config_plist(
        _profile(), BuildOptions(target_macos=target, patches=patches)))
    return str(cfg["NVRAM"]["Add"][_NVRAM].get("boot-args") or "")


class TahoePatchPlanTests(unittest.TestCase):
    def test_tahoe_adds_audio_and_bluetooth_patches(self):
        ids = {p.id for p in plan(_profile(), "macOS Tahoe")}
        self.assertIn("audio_tahoe", ids)
        self.assertIn("bt_intel_26", ids)
        self.assertIn("ota_updates", ids)

    def test_sequoia_has_no_tahoe_patches(self):
        ids = {p.id for p in plan(_profile(), "macOS Sequoia")}
        self.assertNotIn("audio_tahoe", ids)
        self.assertNotIn("bt_intel_26", ids)
        self.assertNotIn("ota_updates", ids)

    def test_bluetooth_patch_needs_intel_bt(self):
        p = _profile()
        p.net = NetInfo(bt_chipset="broadcom")
        ids = {i.id for i in plan(p, "macOS Tahoe")}
        self.assertNotIn("bt_intel_26", ids)


class TahoeBootArgsTests(unittest.TestCase):
    def test_tahoe_skips_alcid_and_adds_ibtcompatbeta(self):
        args = _boot_args("macOS Tahoe")
        self.assertNotIn("alcid=", args)
        self.assertIn("-ibtcompatbeta", args)
        self.assertIn("revpatch=sbvmm", args)

    def test_sequoia_keeps_alcid(self):
        args = _boot_args("macOS Sequoia")
        self.assertIn("alcid=11", args)
        self.assertNotIn("-ibtcompatbeta", args)

    def test_disabled_patch_not_applied(self):
        args = _boot_args("macOS Tahoe", patches=set())
        self.assertNotIn("-ibtcompatbeta", args)
        self.assertNotIn("revpatch=sbvmm", args)


class TahoeWarningsTests(unittest.TestCase):
    def test_tahoe_warns_about_applehda_and_ota(self):
        ru = [r for r, _ in warnings_for(_profile(), "macOS Tahoe")]
        self.assertTrue(any("AppleHDA" in r for r in ru))
        self.assertTrue(any("revpatch" in r for r in ru))

    def test_tahoe_warns_about_whatevergreen_on_amd(self):
        p = _profile()
        p.dgpu = GPUInfo(name="RX 580", vendor="amd", device_id="67DF")
        ru = [r for r, _ in warnings_for(p, "macOS Tahoe")]
        self.assertTrue(any("WhateverGreen" in r for r in ru))

    def test_sequoia_has_no_tahoe_warnings(self):
        ru = [r for r, _ in warnings_for(_profile(), "macOS Sequoia")]
        self.assertFalse(any("AppleHDA" in r for r in ru))


if __name__ == "__main__":
    unittest.main()
