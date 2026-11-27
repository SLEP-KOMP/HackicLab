"""Материнская плата: Windows под OpenCore отдаёт подменённый SMBIOS."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.scanner.models import HardwareProfile
from hackiclab.scanner.windows_scanner import is_spoofed_smbios
from hackiclab.ui.hwview import hardware_rows


class SpoofDetectionTests(unittest.TestCase):
    def test_acidanthera_board_is_spoofed(self):
        self.assertTrue(is_spoofed_smbios("Acidanthera", "Mac-27AD2F918AE68F61"))

    def test_real_gigabyte_board_is_not_spoofed(self):
        self.assertFalse(is_spoofed_smbios("GIGABYTE", "X470 AORUS ULTRA GAMING"))
        self.assertFalse(is_spoofed_smbios("ASUSTeK COMPUTER INC.",
                                           "ROG MAXIMUS Z790 HERO"))

    def test_spoofing_is_case_insensitive(self):
        self.assertTrue(is_spoofed_smbios("acidanthera", "mac-27ad2f918ae68f61"))

    def test_empty_values_are_not_spoofed(self):
        self.assertFalse(is_spoofed_smbios("", ""))


class BoardRowTests(unittest.TestCase):
    def _row(self, profile):
        rows = hardware_rows(profile)
        return next((r for r in rows if r["key"] == "hw.board"), None)

    def test_spoofed_board_is_not_shown_as_hardware(self):
        profile = HardwareProfile(board_vendor="Acidanthera",
                                  board_name="Mac-27AD2F918AE68F61",
                                  board_spoofed=True)
        row = self._row(profile)
        self.assertIsNotNone(row)
        self.assertNotIn("Mac-", row["value"])
        self.assertNotIn("Acidanthera", row["value"])
        self.assertTrue(row["note"])

    def test_real_board_is_shown(self):
        profile = HardwareProfile(board_vendor="GIGABYTE",
                                  board_name="X470 AORUS ULTRA GAMING")
        row = self._row(profile)
        self.assertEqual(row["value"], "GIGABYTE X470 AORUS ULTRA GAMING")
        self.assertEqual(row["note"], "")


if __name__ == "__main__":
    unittest.main()
