"""Тесты структурного аудита готовой EFI (efi_health)."""

from __future__ import annotations

import plistlib
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from hackiclab.analyzer.efi_health import audit
from hackiclab.analyzer.models import Severity


def _make_efi(root: Path, kexts: list[str]) -> Path:
    oc = root / "EFI" / "OC"
    kdir = oc / "Kexts"
    kdir.mkdir(parents=True, exist_ok=True)
    adds = []
    for name in kexts:
        (kdir / f"{name}.kext").mkdir()
        adds.append({"BundlePath": f"{name}.kext", "Enabled": True})
    (oc / "config.plist").write_bytes(plistlib.dumps(
        {"Kernel": {"Add": adds}, "ACPI": {"Add": []}}, fmt=plistlib.FMT_XML))
    return root


class KextConflictAuditTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def _codes(self, kexts: list[str]) -> list[str]:
        _make_efi(self.root, kexts)
        return [i.code for i in audit(self.root)]

    def test_nootrx_with_whatevergreen_is_error(self):
        issues = audit(_make_efi(self.root, ["Lilu", "NootRX", "WhateverGreen"]))
        conflict = [i for i in issues
                    if i.code == "kext_conflict_nootrx_whatevergreen"]
        self.assertTrue(conflict)
        self.assertEqual(conflict[0].severity, Severity.ERROR)
        self.assertEqual(conflict[0].kext, "WhateverGreen")

    def test_intel_wifi_pair_reported(self):
        codes = self._codes(["Lilu", "AirportItlwm", "itlwm"])
        self.assertIn("kext_conflict_airportitlwm_itlwm", codes)

    def test_smc_pair_reported_once(self):
        codes = self._codes(["Lilu", "VirtualSMC", "FakeSMC"])
        self.assertIn("smc_conflict", codes)
        self.assertNotIn("kext_conflict_virtualsmc_fakesmc", codes)

    def test_clean_set_has_no_conflicts(self):
        codes = self._codes(["Lilu", "VirtualSMC", "WhateverGreen"])
        self.assertFalse([c for c in codes if "conflict" in c])


if __name__ == "__main__":
    unittest.main()
