"""Тесты кэша AMD_Vanilla: свежесть, офлайн-фолбэк, срок актуальности."""

from __future__ import annotations

import os
import plistlib
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import _bootstrap  # noqa: F401

from hackiclab.builder import amd_patches as ap


def patches_plist(count: int = 2) -> bytes:
    """Плист правдоподобного размера (> 1 КБ, как настоящий patches.plist)."""
    payload = {
        "Kernel": {"Patch": [{"Comment": f"patch {i}", "Enabled": True} for i in range(count)]},
        "Padding": "x" * 2000,
    }
    return plistlib.dumps(payload)


class AmdPatchesCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _run(self, download):
        with mock.patch("hackiclab.builder.cache_manager.cache_dir",
                        return_value=self.cache_dir), \
             mock.patch("hackiclab.builder.fetcher.download_bytes", side_effect=download):
            return ap.fetch_amd_patches()

    def test_downloads_and_caches(self):
        patches = self._run(lambda *a, **k: patches_plist(3))
        self.assertEqual(len(patches), 3)
        self.assertTrue((self.cache_dir / "amd_patches.plist").exists())

    def test_uses_fresh_cache_without_network(self):
        self._run(lambda *a, **k: patches_plist(2))
        calls = []

        def offline(*a, **k):
            calls.append(1)
            raise OSError("no network")

        patches = self._run(offline)
        self.assertEqual(len(patches), 2)
        self.assertEqual(calls, [], "свежий кэш не должен требовать сети")

    def test_stale_cache_is_refreshed(self):
        self._run(lambda *a, **k: patches_plist(1))
        cache = self.cache_dir / "amd_patches.plist"
        old = time.time() - (ap.CACHE_TTL_DAYS + 2) * 86400
        os.utime(cache, (old, old))

        patches = self._run(lambda *a, **k: patches_plist(4))
        self.assertEqual(len(patches), 4)

    def test_offline_without_cache_returns_empty(self):
        def offline(*a, **k):
            raise OSError("no network")

        self.assertEqual(self._run(offline), [])


if __name__ == "__main__":
    unittest.main()
