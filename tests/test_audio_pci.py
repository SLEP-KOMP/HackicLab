"""layout-id по имени кодека и по PCI-ID (данные OpCore Simplify, BSD-3)."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.knowledge.audio_layouts import LAYOUTS, merged_layouts, recommended
from hackiclab.knowledge.audio_layouts_pci import PCI_LAYOUTS, layouts_for_pci


class PciLayoutTests(unittest.TestCase):
    def test_dataset_loaded(self):
        self.assertGreaterEqual(len(PCI_LAYOUTS), 100)
        for ids in PCI_LAYOUTS.values():
            self.assertIsInstance(ids, tuple)
            self.assertEqual(list(ids), sorted(ids))

    def test_lookup_by_pci_id(self):
        ids = layouts_for_pci("10EC-0892")
        self.assertTrue(ids)
        self.assertIn(11, ids)

    def test_lookup_accepts_colon_and_case(self):
        self.assertEqual(layouts_for_pci("10ec:0892"), layouts_for_pci("10EC-0892"))

    def test_unknown_codec_uses_pci(self):
        """Кодек не опознали, но PCI-ID известен — layout всё равно есть."""
        ids = merged_layouts("", "10EC-0892")
        self.assertTrue(ids)
        self.assertIn(11, ids)

    def test_merge_keeps_both_sources(self):
        codec_ids = set(LAYOUTS["ALC1220"])
        merged = set(merged_layouts("ALC1220", "10EC-0892"))
        self.assertTrue(codec_ids <= merged)
        self.assertTrue(set(layouts_for_pci("10EC-0892")) <= merged)

    def test_recommended_prefers_one(self):
        self.assertEqual(recommended("ALC1220", "10EC-0892"), 1)

    def test_recommended_without_data(self):
        self.assertEqual(recommended("", ""), 0)


if __name__ == "__main__":
    unittest.main()
