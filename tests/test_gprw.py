"""SSDT-GPRW: сон и пробуждение ноутбука (патч _PRW → XPRW)."""

from __future__ import annotations

import plistlib
import unittest

import _bootstrap  # noqa: F401

from hackiclab.builder.config_gen import BuildOptions, generate_config_plist
from hackiclab.builder.ssdt_factory import render_template
from hackiclab.knowledge.ssdt_logics import required_ssdts
from hackiclab.scanner.models import CPUInfo, HardwareProfile


def _laptop() -> HardwareProfile:
    p = HardwareProfile(platform="laptop")
    p.cpu = CPUInfo(name="Intel Core i5-8250U", vendor="intel", generation=8)
    return p


class GprwTests(unittest.TestCase):
    def test_template_compiles_to_dsl(self):
        dsl = render_template("SSDT-GPRW")
        self.assertIn("Method (GPRW, 2", dsl)
        self.assertIn("0x6D", dsl)
        self.assertNotIn("{{", dsl)

    def test_laptop_profile_gets_gprw(self):
        names = [s.name for s in required_ssdts(_laptop())]
        self.assertIn("SSDT-GPRW", names)

    def test_acpi_patch_renames_prw(self):
        cfg = plistlib.loads(generate_config_plist(_laptop(), BuildOptions()))
        patches = cfg["ACPI"]["Patch"]
        rename = [p for p in patches if p.get("Find") == b"_PRW"]
        self.assertEqual(len(rename), 1)
        self.assertEqual(rename[0]["Replace"], b"XPRW")
        self.assertEqual(rename[0]["TableSignature"], b"DSDT")
        self.assertTrue(rename[0]["Enabled"])

    def test_desktop_keeps_acpi_patches_empty(self):
        p = HardwareProfile(platform="desktop")
        p.cpu = CPUInfo(name="Intel Core i7-8700", vendor="intel", generation=8)
        cfg = plistlib.loads(generate_config_plist(p, BuildOptions()))
        self.assertEqual(cfg["ACPI"]["Patch"], [])


if __name__ == "__main__":
    unittest.main()

