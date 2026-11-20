"""IRQ-конфликты HPET/RTC/TIMR по декомпилированному DSDT."""

from __future__ import annotations

import plistlib
import unittest

import _bootstrap  # noqa: F401

from hackiclab.builder.config_gen import BuildOptions, generate_config_plist
from hackiclab.builder.ssdt_factory import build_hpet_fix, irq_conflict_devices
from hackiclab.scanner.models import CPUInfo, HardwareProfile

DSDT_WITH_CONFLICTS = '''
DefinitionBlock ("", "DSDT", 2, "ALASKA", "A M I", 0x01072009)
{
    Scope (\\_SB)
    {
        Device (HPET)
        {
            Name (_HID, EisaId ("PNP0103"))
            Name (_CRS, ResourceTemplate ()
            {
                IRQNoFlags () {0}
                Memory32Fixed (ReadWrite, 0xFED00000, 0x00000400)
            })
        }
        Device (RTC)
        {
            Name (_HID, EisaId ("PNP0B00"))
            Name (_CRS, ResourceTemplate ()
            {
                IO (Decode16, 0x0070, 0x0070, 0x01, 0x08)
                IRQNoFlags () {8}
            })
        }
        Device (TIMR)
        {
            Name (_CRS, ResourceTemplate ()
            {
                IRQNoFlags () {0}
            })
        }
        Device (LPCB)
        {
            Name (_ADR, 0x001F0000)
        }
    }
}
'''

DSDT_CLEAN = '''
DefinitionBlock ("", "DSDT", 2, "ALASKA", "A M I", 0x01072009)
{
    Scope (\\_SB)
    {
        Device (HPET)
        {
            Name (_HID, EisaId ("PNP0103"))
            Name (_CRS, ResourceTemplate ()
            {
                Memory32Fixed (ReadWrite, 0xFED00000, 0x00000400)
            })
        }
    }
}
'''


class IrqConflictTests(unittest.TestCase):
    def test_finds_conflicting_devices(self):
        self.assertEqual(irq_conflict_devices(DSDT_WITH_CONFLICTS),
                         ["HPET", "RTC", "TIMR"])

    def test_clean_dsdt_has_no_conflicts(self):
        self.assertEqual(irq_conflict_devices(DSDT_CLEAN), [])

    def test_empty_text_is_safe(self):
        self.assertEqual(irq_conflict_devices(""), [])

    def test_irq_outside_device_is_ignored(self):
        text = "Scope (\\_SB) { IRQNoFlags () {0} }"
        self.assertEqual(irq_conflict_devices(text), [])


class HpetFixTests(unittest.TestCase):
    def _fix(self):
        return build_hpet_fix(DSDT_WITH_CONFLICTS)

    def test_generates_dsl_and_patches(self):
        dsl, patches = self._fix()
        self.assertIn('DefinitionBlock ("", "SSDT"', dsl)
        self.assertEqual([p["Base"] for p in patches],
                         ["\\_SB.HPET", "\\_SB.RTC", "\\_SB.TIMR"])
        for p in patches:
            self.assertEqual(p["Find"], b"_CRS")
            self.assertEqual(p["Replace"], b"XCRS")
            self.assertEqual(p["TableSignature"], b"DSDT")
            self.assertTrue(p["Enabled"])

    def test_irq_removed_but_addresses_kept(self):
        dsl, _ = self._fix()
        self.assertNotIn("IRQNoFlags", dsl)
        self.assertIn("Memory32Fixed (ReadWrite, 0xFED00000, 0x00000400)", dsl)
        self.assertIn("IO (Decode16, 0x0070, 0x0070, 0x01, 0x08)", dsl)

    def test_scope_targets_original_device(self):
        dsl, _ = self._fix()
        self.assertIn("External (\\_SB.HPET, DeviceObj)", dsl)
        self.assertIn("Scope (\\_SB.HPET)", dsl)
        self.assertIn("Method (_CRS, 0, NotSerialized)", dsl)

    def test_clean_dsdt_produces_nothing(self):
        self.assertEqual(build_hpet_fix(DSDT_CLEAN), ("", []))
        self.assertEqual(build_hpet_fix(""), ("", []))

    def test_device_without_resources_is_skipped(self):
        text = ('Scope (\\_SB) { Device (HPET) { Name (_CRS, Buffer (0) {}) '
                'IRQNoFlags () {0} } }')
        self.assertEqual(build_hpet_fix(text), ("", []))

    def test_extra_patches_reach_config(self):
        _, patches = self._fix()
        p = HardwareProfile(platform="desktop")
        p.cpu = CPUInfo(name="Intel Core i7-8700", vendor="intel", generation=8)
        cfg = plistlib.loads(generate_config_plist(
            p, BuildOptions(extra_acpi_patches=patches)))
        found = [x for x in cfg["ACPI"]["Patch"] if x["Find"] == b"_CRS"]
        self.assertEqual(len(found), 3)

    def test_config_without_patches_untouched(self):
        p = HardwareProfile(platform="desktop")
        p.cpu = CPUInfo(name="Intel Core i7-8700", vendor="intel", generation=8)
        cfg = plistlib.loads(generate_config_plist(p, BuildOptions()))
        self.assertEqual(cfg["ACPI"]["Patch"], [])


if __name__ == "__main__":
    unittest.main()
