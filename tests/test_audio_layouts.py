"""Тесты таблицы layout-id: только реально поддерживаемые AppleALC значения."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.knowledge.audio_layouts import LAYOUTS, layouts_for, recommended


class LayoutTableTests(unittest.TestCase):
    def test_table_covers_known_codecs(self):
        self.assertGreater(len(LAYOUTS), 80)
        for codec in ("ALC1220", "ALC295", "ALC257", "ALC897"):
            self.assertGreater(len(layouts_for(codec)), 0, codec)

    def test_every_entry_is_sorted_tuple_of_ints(self):
        for codec, ids in LAYOUTS.items():
            self.assertIsInstance(ids, tuple, codec)
            self.assertTrue(all(isinstance(i, int) and i > 0 for i in ids), codec)
            self.assertEqual(list(ids), sorted(ids), codec)

    def test_recommended_is_supported(self):
        for codec in ("ALC1220", "ALC295", "ALC257"):
            self.assertIn(recommended(codec), layouts_for(codec))

    def test_alc1220_has_no_layout_1(self):
        """Раньше таблица обещала ALC1220 layout 1, которого в кексте нет."""
        self.assertNotIn(1, layouts_for("ALC1220"))
        self.assertIn(69, layouts_for("ALC1220"))

    def test_unknown_codec_gives_zero(self):
        self.assertEqual(recommended("ALC9999"), 0)
        self.assertEqual(layouts_for(""), ())

    def test_lookup_is_case_insensitive(self):
        self.assertEqual(layouts_for("alc1220"), layouts_for("ALC1220"))


if __name__ == "__main__":
    unittest.main()
