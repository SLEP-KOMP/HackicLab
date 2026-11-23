"""Тесты сборки UEFI-путей из дерева PnP."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.scanner.pci_paths import compose_path, paths, table

# Настоящее дерево этой машины: Ethernet за мостом 43C7 → 43C6 → 1483.
ROWS = [
    {"id": "PCI\\VEN_1022&DEV_1483", "addr": 0x10003, "parent": r"ACPI\PNP0A08\0"},
    {"id": "PCI\\VEN_1022&DEV_43C6", "addr": 0x00002, "parent": "PCI\\VEN_1022&DEV_1483"},
    {"id": "PCI\\VEN_1022&DEV_43C7", "addr": 0x30000, "parent": "PCI\\VEN_1022&DEV_43C6"},
    {"id": "PCI\\VEN_8086&DEV_1539", "addr": 0x00000, "parent": "PCI\\VEN_1022&DEV_43C7"},
]


class ComposePathTests(unittest.TestCase):
    def setUp(self):
        self.lookup = table(ROWS)

    def test_deep_chain_is_built_from_root(self):
        path = compose_path("PCI\\VEN_8086&DEV_1539", self.lookup)
        self.assertEqual(
            path,
            "PciRoot(0x0)/Pci(0x1,0x3)/Pci(0x0,0x2)/Pci(0x3,0x0)/Pci(0x0,0x0)",
        )

    def test_device_and_function_are_encoded(self):
        path = compose_path("PCI\\VEN_1022&DEV_1483", self.lookup)
        self.assertEqual(path, "PciRoot(0x0)/Pci(0x1,0x3)")
        self.assertIn("Pci(0x1,0x3)", path)

    def test_unknown_device_gives_empty_path(self):
        self.assertEqual(compose_path("PCI\\VEN_FFFF&DEV_FFFF", self.lookup), "")

    def test_broken_chain_gives_empty_path(self):
        lone = table([{"id": "PCI\\VEN_1234&DEV_5678", "addr": 0, "parent": "ACPI\\PNP0A08\\0"}])
        self.assertEqual(compose_path("PCI\\VEN_1234&DEV_5678", lone), "")

    def test_paths_builds_map_for_every_device(self):
        built = paths(ROWS)
        self.assertEqual(len(built), 4)
        self.assertTrue(built["pci\\ven_8086&dev_1539"].startswith("PciRoot(0x0)"))


if __name__ == "__main__":
    unittest.main()
