"""IRQ-конфликты HPET/RTC/TIMR по декомпилированному DSDT."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.builder.ssdt_factory import irq_conflict_devices

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


if __name__ == "__main__":
    unittest.main()
