"""Тесты SSDT-USB-Reset: поиск RHUB в DSDT и сборка DSL."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.builder.ssdt_factory import build_usb_reset, rhub_path

# Минимальный фрагмент декомпилированного DSDT: XHCI с корневым хабом.
DSDT = """
DefinitionBlock ("", "DSDT", 2, "ALASKA", "A M I", 0x01072009)
{
    Scope (_SB.PCI0)
    {
        Device (XHC1)
        {
            Name (_ADR, 0x00140000)
            Device (RHUB)
            {
                Name (_ADR, Zero)
                Device (HS01) { Name (_ADR, 0x01) }
            }
        }
    }
}
"""

FLAT = """
DefinitionBlock ("", "DSDT", 2, "TEST", "TEST", 0x00000001)
{
    Device (PCI0) { Device (XHC) { Device (RHUB) { Name (_ADR, Zero) } } }
}
"""


class RhubPathTests(unittest.TestCase):
    def test_full_path_is_built(self):
        self.assertEqual(rhub_path(DSDT), r"\_SB.PCI0.XHC1.RHUB")

    def test_flat_block_is_found(self):
        self.assertEqual(rhub_path(FLAT), r"\PCI0.XHC.RHUB")

    def test_missing_rhub_gives_empty_path(self):
        self.assertEqual(rhub_path("DefinitionBlock (\"\", \"DSDT\", 2, \"X\", \"Y\", 0) { }"), "")


class UsbResetTests(unittest.TestCase):
    def setUp(self):
        self.dsl = build_usb_reset(DSDT)

    def test_external_and_scope_point_to_rhub(self):
        self.assertIn(r"External (\_SB.PCI0.XHC1.RHUB, DeviceObj)", self.dsl)
        self.assertIn(r"Scope (\_SB.PCI0.XHC1.RHUB)", self.dsl)

    def test_sta_returns_zero(self):
        self.assertIn("Method (_STA, 0, NotSerialized)", self.dsl)
        self.assertIn("Return (Zero)", self.dsl)

    def test_table_is_ssdt(self):
        self.assertIn('"SSDT"', self.dsl)
        self.assertIn("UsbReset", self.dsl)

    def test_no_rhub_means_no_table(self):
        self.assertEqual(build_usb_reset("Scope (_SB) { }"), "")


class PipelineTests(unittest.TestCase):
    def _profile(self):
        from hackiclab.scanner.models import CPUInfo, HardwareProfile

        p = HardwareProfile(platform="desktop")
        p.cpu = CPUInfo(name="AMD Ryzen 5 3600", vendor="amd", generation=10)
        return p

    def test_reset_is_in_required_list(self):
        from hackiclab.knowledge.ssdt_logics import required_ssdts

        names = [s.name for s in required_ssdts(self._profile())]
        self.assertIn("SSDT-USB-Reset", names)

    def test_factory_without_dsdt_leaves_table_unbuilt(self):
        import tempfile
        from pathlib import Path

        from hackiclab.builder.ssdt_factory import SSDTFactory

        with tempfile.TemporaryDirectory() as tmp:
            results = SSDTFactory(self._profile()).generate_all(Path(tmp))
        reset = next(r for r in results if r["name"] == "SSDT-USB-Reset")
        self.assertEqual(reset["path"], "")

    def test_factory_uses_dsdt_when_given(self):
        import tempfile
        from pathlib import Path

        from hackiclab.builder import ssdt_factory

        with tempfile.TemporaryDirectory() as tmp:
            factory = ssdt_factory.SSDTFactory(self._profile(), dsdt_text=DSDT)
            self.assertIn("RHUB", ssdt_factory.build_usb_reset(factory.dsdt_text))
            self.assertEqual(len(factory.generate_all(Path(tmp))), 4)


if __name__ == "__main__":
    unittest.main()
