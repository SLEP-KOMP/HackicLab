"""Тесты каталога конфигураций: целостность данных и фильтры."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.knowledge import configs as cfg


class CatalogIntegrityTests(unittest.TestCase):
    def test_catalog_is_not_empty(self):
        self.assertGreaterEqual(len(cfg.all_configs()), 10)

    def test_keys_are_unique(self):
        keys = [c.key for c in cfg.all_configs()]
        self.assertEqual(len(keys), len(set(keys)))

    def test_every_category_is_covered(self):
        for cat in cfg.CATEGORIES:
            self.assertTrue(cfg.by_category(cat), f"пустая категория: {cat}")

    def test_statuses_and_texts_are_valid(self):
        for c in cfg.all_configs():
            self.assertIn(c.status, cfg.STATUSES, c.key)
            self.assertTrue(c.title and c.title_en, c.key)
            self.assertTrue(c.cpu and c.gpu and c.macos, c.key)
            self.assertTrue(c.note and c.note_en, c.key)

    def test_source_keys_exist(self):
        from hackiclab.knowledge.sources import SOURCES
        for c in cfg.all_configs():
            for key in c.sources:
                self.assertIn(key, SOURCES, f"{c.key}: неизвестный источник {key}")

    def test_links_are_https(self):
        for c in cfg.all_configs():
            if c.url:
                self.assertTrue(c.url.startswith("https://"), c.key)


class CatalogFilterTests(unittest.TestCase):
    def test_search_matches_vendor_and_model(self):
        found = cfg.search_configs("thinkpad")
        self.assertTrue(found)
        self.assertTrue(all("thinkpad" in cfg._haystack(c) for c in found))

    def test_search_is_case_insensitive(self):
        self.assertEqual(
            [c.key for c in cfg.search_configs("RYZEN")],
            [c.key for c in cfg.search_configs("ryzen")],
        )

    def test_search_finds_kext(self):
        self.assertTrue(cfg.search_configs("VirtualSMC"))

    def test_category_filter(self):
        laptops = cfg.search_configs("", cfg.CAT_LAPTOP)
        self.assertTrue(laptops)
        self.assertTrue(all(c.category == cfg.CAT_LAPTOP for c in laptops))

    def test_empty_query_returns_everything(self):
        self.assertEqual(len(cfg.search_configs()), len(cfg.all_configs()))

    def test_unknown_query_returns_nothing(self):
        self.assertEqual(cfg.search_configs("нет-такого-железа-123"), [])


class SimilarConfigTests(unittest.TestCase):
    def _profile(self, platform: str, codename: str):
        from hackiclab.scanner.models import CPUInfo, HardwareProfile

        p = HardwareProfile(platform=platform)
        p.cpu = CPUInfo(name="Intel Core i5", vendor="intel", codename=codename)
        return p

    def test_laptop_profile_gets_laptop_entries(self):
        found = cfg.similar_configs(self._profile("laptop", "Kaby Lake-R"), limit=2)
        self.assertTrue(found)
        self.assertEqual(found[0].category, cfg.CAT_LAPTOP)

    def test_desktop_profile_gets_desktop_entries(self):
        found = cfg.similar_configs(self._profile("desktop", "Ryzen 5"), limit=3)
        self.assertTrue(found)
        self.assertIn(found[0].category, (cfg.CAT_DESKTOP_AMD, cfg.CAT_DESKTOP_INTEL))

    def test_none_profile_returns_empty(self):
        self.assertEqual(cfg.similar_configs(None), [])


if __name__ == "__main__":
    unittest.main()
