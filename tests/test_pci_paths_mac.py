"""Тесты UEFI-путей из IORegistry: разбор device-path и выбор узлов."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.scanner.pci_paths_mac import parse_nodes, pick, uefi_path_from_hex

# PciRoot(0x0)/Pci(0x8,0x1)/Pci(0x0,0x4) — так выглядит путь аудиоконтроллера.
AUDIO_HEX = (
    "02010C00D041030A00000000"
    "010106000108"
    "010106000400"
    "7FFF0400"
)

NODES = [
    {"IORegistryEntryName": "PCI0", "device-path": bytes.fromhex(
        "02010C00D041030A00000000" "7FFF0400")},
    {"IORegistryEntryName": "HDEF", "device-path": bytes.fromhex(AUDIO_HEX)},
    {"IORegistryEntryName": "GIGE", "device-path": bytes.fromhex(
        "02010C00D041030A00000000" "010106000003" "7FFF0400")},
    {"IORegistryEntryName": "DTGP"},  # без device-path
]


class HexPathTests(unittest.TestCase):
    def test_pci_root_and_two_bridges(self):
        self.assertEqual(uefi_path_from_hex(AUDIO_HEX),
                         "PciRoot(0x0)/Pci(0x8,0x1)/Pci(0x0,0x4)")

    def test_root_only(self):
        self.assertEqual(uefi_path_from_hex("02010C00D041030A000000007FFF0400"),
                         "PciRoot(0x0)")

    def test_garbage_gives_empty(self):
        self.assertEqual(uefi_path_from_hex("zz"), "")
        self.assertEqual(uefi_path_from_hex(""), "")

    def test_spaces_and_angle_brackets_are_tolerated(self):
        raw = "<" + AUDIO_HEX.lower() + ">"
        self.assertEqual(uefi_path_from_hex(raw),
                         "PciRoot(0x0)/Pci(0x8,0x1)/Pci(0x0,0x4)")


class NodeTests(unittest.TestCase):
    def test_nodes_map_names_to_paths(self):
        table = parse_nodes(NODES)
        self.assertEqual(table["HDEF"], "PciRoot(0x0)/Pci(0x8,0x1)/Pci(0x0,0x4)")
        self.assertEqual(table["GIGE"], "PciRoot(0x0)/Pci(0x3,0x0)")
        self.assertNotIn("DTGP", table)

    def test_pick_prefers_first_prefix(self):
        table = parse_nodes(NODES)
        self.assertEqual(pick(table, ("HDEF", "HDAS")),
                         "PciRoot(0x0)/Pci(0x8,0x1)/Pci(0x0,0x4)")
        self.assertEqual(pick(table, ("NOPE", "GIGE")), "PciRoot(0x0)/Pci(0x3,0x0)")

    def test_pick_without_match_is_empty(self):
        self.assertEqual(pick(parse_nodes(NODES), ("WIFI", "ARPT")), "")

    def test_broken_nodes_are_ignored(self):
        self.assertEqual(parse_nodes([{}, {"IORegistryEntryName": "X"}, "не словарь"]), {})


if __name__ == "__main__":
    unittest.main()
