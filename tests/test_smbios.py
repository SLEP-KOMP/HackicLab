"""Тесты генерации SMBIOS: формат серийника, согласованность года и недели."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.builder.smbios_gen import (
    _BASE34,
    _WEEK_FIRST,
    _WEEK_SECOND,
    _YEAR_HALVES,
    PLANT_PREFIXES,
    SMBIOSData,
    generate_smbios,
)

FIRST_HALF = {first for first, _ in _YEAR_HALVES.values()}
SECOND_HALF = {second for _, second in _YEAR_HALVES.values()}


class SerialFormatTests(unittest.TestCase):
    def setUp(self):
        self.data = generate_smbios("MacPro7,1")

    def test_length_and_alphabet(self):
        self.assertEqual(len(self.data.serial), 12)
        for char in self.data.serial:
            self.assertIn(char, _BASE34)
        self.assertNotIn("I", self.data.serial)
        self.assertNotIn("O", self.data.serial)

    def test_year_and_week_agree(self):
        year_char, week_char = self.data.serial[3], self.data.serial[4]
        if year_char in FIRST_HALF:
            self.assertIn(week_char, _WEEK_FIRST)
        else:
            self.assertIn(year_char, SECOND_HALF)
            self.assertIn(week_char, _WEEK_SECOND)

    def test_dates_stay_in_supported_years(self):
        self.assertIn(self.data.serial[3], FIRST_HALF | SECOND_HALF)

    def test_mlb_length_and_plant(self):
        self.assertEqual(len(self.data.mlb), 17)
        self.assertTrue(any(self.data.mlb.startswith(p) for p in PLANT_PREFIXES["MacPro"]))

    def test_rom_is_unicast_mac(self):
        self.assertEqual(len(self.data.rom), 12)
        first = int(self.data.rom[:2], 16)
        self.assertEqual(first % 2, 0)

    def test_uuid_is_upper_case(self):
        self.assertEqual(self.data.system_uuid, self.data.system_uuid.upper())

    def test_serials_differ_between_runs(self):
        other: SMBIOSData = generate_smbios("MacPro7,1")
        self.assertNotEqual(self.data.serial, other.serial)


if __name__ == "__main__":
    unittest.main()
