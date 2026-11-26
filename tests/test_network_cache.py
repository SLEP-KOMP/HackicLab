"""Тесты сетевого кэша: подмена папки, проверка доступности, повторное использование."""

from __future__ import annotations

import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import _bootstrap  # noqa: F401

from hackiclab import uistate
from hackiclab.builder import cache_manager, downloader
from hackiclab.builder.cache_warmup import kext_entries
from hackiclab.knowledge.kexts import KextEntry


class CachePathTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self._env = os.environ.pop("HACKICLAB_CACHE", None)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        if self._env is not None:
            os.environ["HACKICLAB_CACHE"] = self._env

    def test_check_cache_path_accepts_writable_folder(self):
        ok, detail = cache_manager.check_cache_path(str(self.root / "cache"))
        self.assertTrue(ok, detail)
        self.assertTrue((self.root / "cache").is_dir())

    def test_check_cache_path_rejects_empty_and_missing_drive(self):
        self.assertFalse(cache_manager.check_cache_path("")[0])
        missing = "Q:\\definitely-not-a-drive\\cache"
        ok, _ = cache_manager.check_cache_path(missing)
        self.assertFalse(ok)

    def test_cache_dir_honours_setting(self):
        target = self.root / "netcache"
        with mock.patch.object(uistate, "get", return_value=str(target)):
            self.assertEqual(cache_manager.cache_dir(), target)
            self.assertTrue(cache_manager.is_network_cache())

    def test_cache_dir_falls_back_when_unreachable(self):
        with mock.patch.object(uistate, "get",
                               return_value="Q:\\definitely-not-a-drive\\cache"):
            path = cache_manager.cache_dir()
            self.assertFalse(cache_manager.is_network_cache())
        self.assertEqual(path, cache_manager.app_home() / "cache")

    def test_env_override_used_when_setting_empty(self):
        target = self.root / "envcache"
        os.environ["HACKICLAB_CACHE"] = str(target)
        with mock.patch.object(uistate, "get", return_value=""):
            self.assertEqual(cache_manager.cache_dir(), target)


class KextCacheReuseTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self._old = os.environ.get("HACKICLAB_CACHE")
        os.environ["HACKICLAB_CACHE"] = str(self.root / "cache")
        self.addCleanup(self._restore)

    def _restore(self):
        if self._old is None:
            os.environ.pop("HACKICLAB_CACHE", None)
        else:
            os.environ["HACKICLAB_CACHE"] = self._old

    def _entry(self) -> KextEntry:
        return KextEntry("Lilu", "acidanthera/Lilu", "Lilu-", "тест")

    def _cached_zip(self) -> Path:
        work = self.root / "cache" / "kexts" / "Lilu"
        work.mkdir(parents=True)
        zpath = work / "Lilu-1.6.7.zip"
        with zipfile.ZipFile(zpath, "w") as z:
            z.writestr("Lilu.kext/Contents/Info.plist", "<plist/>")
            z.writestr("Lilu.kext/Contents/pad.bin", b"0" * 2048)
        return zpath

    def test_cached_archive_is_not_downloaded_again(self):
        self._cached_zip()
        dest = self.root / "Kexts"
        dl = downloader.Downloader()
        with mock.patch.object(downloader.GitHubFetcher, "latest_tag",
                               return_value="1.6.7"), \
                mock.patch.object(downloader.Downloader, "kext_release_file",
                                  return_value="Lilu-1.6.7.zip"), \
                mock.patch.object(downloader, "download_bytes",
                                  side_effect=AssertionError("сеть не должна вызываться")):
            path = dl.download_kext(self._entry(), dest, "")
        self.assertIsNotNone(path)
        self.assertTrue((dest / "Lilu.kext").is_dir())
        self.assertTrue(any("из кэша" in line for line in dl.log))


class KextRegistryTests(unittest.TestCase):
    def test_registry_has_entries_and_no_internal(self):
        entries = kext_entries()
        self.assertGreater(len(entries), 10)
        self.assertTrue(all(not getattr(e, "internal", False) for _, e in entries))


if __name__ == "__main__":
    unittest.main()
