"""Тесты локального реестра железа и предложения конфигураций."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _bootstrap  # noqa: F401

from hackiclab.knowledge import registry
from hackiclab.scanner.models import CPUInfo, GPUInfo, HardwareProfile


def profile(cpu: str, vendor: str, gen: int, platform: str = "desktop",
            gpu: str = "3E92") -> HardwareProfile:
    p = HardwareProfile(platform=platform, board_vendor="ASUS", board_name="PRIME")
    p.cpu = CPUInfo(name=cpu, vendor=vendor, generation=gen)
    p.igpu = GPUInfo(name="Graphics", vendor="intel", device_id=gpu, is_integrated=True)
    return p


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        patch = mock.patch("hackiclab.knowledge.registry.app_home", return_value=self.home)
        patch.start()
        self.addCleanup(patch.stop)

    def test_register_creates_record(self):
        rec = registry.register(profile("Intel Core i5-9400", "intel", 9))
        self.assertEqual(rec["cpu"], "Intel Core i5-9400")
        self.assertEqual(rec["count"], 1)
        self.assertTrue(rec["fingerprint"])

    def test_same_hardware_increments_counter(self):
        p = profile("Intel Core i5-9400", "intel", 9)
        registry.register(p)
        rec = registry.register(p)
        self.assertEqual(rec["count"], 2)

    def test_fingerprint_has_no_personal_data(self):
        p = profile("Intel Core i5-9400", "intel", 9)
        fp = registry.fingerprint(p)
        self.assertEqual(len(fp), 16)
        self.assertNotIn("i5", fp)

    def test_known_hardware_matches_catalog(self):
        rec = registry.register(profile("Intel Core i5-9400", "intel", 9))
        self.assertTrue(rec["matched"])
        self.assertEqual(registry.unknown(), [])

    def test_unknown_hardware_is_listed(self):
        rec = registry.register(profile("Intel Pentium Gold G7400", "intel", 0))
        self.assertEqual(rec["matched"], "")
        self.assertEqual(len(registry.unknown()), 1)

    def test_find_returns_existing_record(self):
        p = profile("AMD Ryzen 5 3600", "amd", 10)
        registry.register(p)
        self.assertIsNotNone(registry.find(p))
        self.assertIsNone(registry.find(profile("Другой CPU", "intel", 11)))

    def test_export_writes_json(self):
        registry.register(profile("Intel Core i5-9400", "intel", 9))
        path = registry.export_json(self.home / "export.json")
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual(len(data), 1)

    def test_issue_url_is_prefilled_and_anonymized(self):
        rec = registry.register(profile("Intel Core i5-9400", "intel", 9))
        url = registry.issue_url(rec)
        self.assertIn("issues/new", url)
        self.assertIn("Intel", url)
        self.assertIn("labels=hardware-catalog", url)
        self.assertNotIn("Serial", url)

    def test_broken_registry_file_is_ignored(self):
        (self.home / "hardware_registry.json").write_text("{oops", encoding="utf-8")
        self.assertEqual(registry.load(), {})

    def test_catalog_matching_requires_close_generation(self):
        # 11-е поколение Intel в каталоге отсутствует — не считаем известным
        rec = registry.register(profile("Intel Core i7-1165G7", "intel", 11))
        self.assertEqual(rec["matched"], "")


if __name__ == "__main__":
    unittest.main()
