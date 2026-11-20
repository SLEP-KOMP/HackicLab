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


if __name__ == "__main__":
    unittest.main()


