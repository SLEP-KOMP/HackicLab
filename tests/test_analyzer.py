"""Тесты анализа готовой EFI: отсутствующие и «лишние» кексты."""

from __future__ import annotations

import plistlib
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from hackiclab.analyzer.engine import Analyzer
from hackiclab.analyzer.models import Severity
from hackiclab.scanner.models import CPUInfo, HardwareProfile, NetInfo


def _profile() -> HardwareProfile:
    p = HardwareProfile(platform="desktop")
    p.cpu = CPUInfo(name="Intel Core i7-8700", vendor="intel", generation=8)
    p.net = NetInfo(eth_chipset="i211", eth_name="Intel I211 Gigabit")
    return p


def _make_efi(root: Path, kexts: list[str]) -> Path:
    oc = root / "EFI" / "OC"
    kdir = oc / "Kexts"
    kdir.mkdir(parents=True, exist_ok=True)
    for name in kexts:
        (kdir / name).mkdir()
    (oc / "config.plist").write_bytes(plistlib.dumps(
        {"Kernel": {"Add": []}, "ACPI": {"Add": []}}, fmt=plistlib.FMT_XML))
    (oc / "OpenCore.efi").write_bytes(b"x")
    boot = root / "EFI" / "BOOT"
    boot.mkdir(parents=True, exist_ok=True)
    (boot / "BOOTx64.efi").write_bytes(b"x")
    return root


class AnalyzerKextTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def _issues(self, kexts: list[str]):
        _make_efi(self.root, kexts)
        return Analyzer(_profile()).analyze_folder(self.root)

    def test_missing_kext_is_warning(self):
        issues = self._issues(["Lilu.kext", "AppleIGB.kext"])
        missing = [i for i in issues if i.code == "kext_missing"]
        self.assertTrue(any(i.title.endswith("VirtualSMC") for i in missing))
        self.assertEqual(missing[0].severity, Severity.WARNING)

    def test_appleigb_present_silences_network_advice(self):
        with_igb = [i.code for i in self._issues(["Lilu.kext", "AppleIGB.kext"])]
        self.assertNotIn("eth_i211_appleigb", with_igb)

        self.root = self.root / "second"
        without = [i.code for i in self._issues(["Lilu.kext"])]
        self.assertIn("eth_i211_appleigb", without)

    def test_internal_kext_not_reported_as_extra(self):
        """SMCSuperIO приезжает в архиве VirtualSMC — он не «лишний»."""
        issues = self._issues(["Lilu.kext", "AppleIGB.kext", "VirtualSMC.kext",
                               "SMCSuperIO.kext"])
        extra = [i for i in issues if i.code == "kext_extra"]
        self.assertFalse([i for i in extra if i.title.endswith("SMCSuperIO")])

    def test_target_macos_selects_ethernet_driver(self):
        """I211: до Monterey — AppleIntelI210Ethernet, с Monterey — AppleIGB."""
        _make_efi(self.root, ["Lilu.kext"])
        def names(macos: str) -> list[str]:
            return [i.kext for i in Analyzer(_profile(), macos)
                    .analyze_folder(self.root) if i.code == "kext_missing"]
        self.assertIn("AppleIGB", names("Ventura"))
        self.assertNotIn("AppleIGB", names("Big Sur"))
        self.assertIn("AppleIntelI210Ethernet", names("Big Sur"))

    def test_broadcom_native_requires_oclp_set(self):
        """Нативный Broadcom на Sonoma+ без набора OCLP не поднимется."""
        p = _profile()
        p.net = NetInfo(eth_chipset="i211", eth_name="Intel I211",
                        wifi_chipset="broadcom", bt_native_apple=True)
        _make_efi(self.root, ["Lilu.kext"])
        missing = [i.kext for i in Analyzer(p, "Sonoma").analyze_folder(self.root)
                   if i.code == "kext_missing"]
        self.assertIn("AMFIPass", missing)
        self.assertIn("IOSkywalkFamily", missing)


class AnalyzerKextConflictTests(unittest.TestCase):
    """Кексты, которые нельзя держать в одном EFI (ловим и чужие сборки)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def _codes(self, kexts: list[str]) -> list[str]:
        _make_efi(self.root, kexts)
        return [i.code for i in Analyzer(_profile()).analyze_folder(self.root)]

    def test_nootrx_and_whatevergreen_conflict(self):
        codes = self._codes(["Lilu.kext", "NootRX.kext", "WhateverGreen.kext"])
        self.assertIn("kext_conflict_nootrx_whatevergreen", codes)

    def test_intel_wifi_drivers_conflict(self):
        codes = self._codes(["Lilu.kext", "AirportItlwm.kext", "itlwm.kext"])
        self.assertIn("kext_conflict_airportitlwm_itlwm", codes)

    def test_smc_providers_conflict(self):
        codes = self._codes(["Lilu.kext", "VirtualSMC.kext", "FakeSMC.kext"])
        self.assertIn("kext_conflict_virtualsmc_fakesmc", codes)

    def test_single_kext_is_not_conflict(self):
        codes = self._codes(["Lilu.kext", "NootRX.kext", "AirportItlwm.kext",
                             "VirtualSMC.kext"])
        self.assertFalse([c for c in codes if c.startswith("kext_conflict_")])

    def test_conflict_is_error_severity(self):
        _make_efi(self.root, ["Lilu.kext", "NootRX.kext", "WhateverGreen.kext"])
        issues = [i for i in Analyzer(_profile()).analyze_folder(self.root)
                  if i.code == "kext_conflict_nootrx_whatevergreen"]
        self.assertEqual(issues[0].severity, Severity.ERROR)
        self.assertEqual(issues[0].kext, "WhateverGreen")


if __name__ == "__main__":
    unittest.main()



