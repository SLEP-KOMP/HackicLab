"""Тесты проверки обновлений: сравнение версий, разбор релиза, загрузка."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _bootstrap  # noqa: F401

from hackiclab import updater


def release(version: str, asset: bool = True, size: int = 1234) -> dict:
    assets = []
    if asset:
        assets = [{
            "name": "HackicLab.exe",
            "browser_download_url": f"https://example.com/{version}/HackicLab.exe",
            "size": size,
        }]
    return {
        "tag_name": f"v{version}",
        "html_url": f"https://github.com/SLEP-KOMP/HackicLab/releases/tag/v{version}",
        "body": "Что нового",
        "assets": assets,
    }


class VersionTests(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(updater.parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(updater.parse_version("1.0.1-beta"), (1, 0, 1))
        self.assertEqual(updater.parse_version("2"), (2,))
        self.assertEqual(updater.parse_version(""), (0,))

    def test_is_newer(self):
        self.assertTrue(updater.is_newer("1.0.2", "1.0.1"))
        self.assertTrue(updater.is_newer("1.1.0", "1.0.9"))
        self.assertTrue(updater.is_newer("2.0", "1.9.9"))
        self.assertFalse(updater.is_newer("1.0.1", "1.0.1"))
        self.assertFalse(updater.is_newer("1.0.0", "1.0.1"))

    def test_is_newer_handles_short_tags(self):
        self.assertFalse(updater.is_newer("1.0", "1.0.0"))
        self.assertTrue(updater.is_newer("1.0.0.1", "1.0.0"))


class ParseReleaseTests(unittest.TestCase):
    def test_newer_release_with_asset(self):
        info = updater.parse_release(release("9.9.9"))
        self.assertIsNotNone(info)
        self.assertEqual(info.version, "9.9.9")
        self.assertTrue(info.has_asset)
        self.assertEqual(info.asset_size, 1234)

    def test_same_version_is_ignored(self):
        self.assertIsNone(updater.parse_release(release(updater.__version__)))

    def test_release_without_asset(self):
        info = updater.parse_release(release("9.9.9", asset=False))
        self.assertIsNotNone(info)
        self.assertFalse(info.has_asset)

    def test_release_without_tag(self):
        self.assertIsNone(updater.parse_release({"assets": []}))

    def test_check_for_update_uses_github_json(self):
        payload = json.dumps(release("9.9.9")).encode("utf-8")
        with mock.patch.object(updater, "download_bytes", return_value=payload) as dl:
            info = updater.check_for_update()
        self.assertEqual(info.version, "9.9.9")
        called_url = dl.call_args[0][0]
        self.assertIn("api.github.com", called_url)
        self.assertIn("SLEP-KOMP/HackicLab", called_url)

    def test_http_error_propagates(self):
        with mock.patch.object(updater, "download_bytes", side_effect=RuntimeError("403")):
            with self.assertRaises(RuntimeError):
                updater.check_for_update()


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = mock.patch.dict("os.environ", {"LOCALAPPDATA": self.tmp.name})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_download_writes_file(self):
        info = updater.UpdateInfo(
            version="9.9.9", tag="v9.9.9", notes="", page_url="",
            asset_url="https://example.com/HackicLab.exe", asset_size=None,
        )
        data = b"MZ" + b"0" * 2048
        with mock.patch.object(updater, "download_bytes", return_value=data):
            path = updater.download_update(info)
        self.assertTrue(path.exists())
        self.assertEqual(path.read_bytes(), data)
        self.assertIn("9.9.9", path.name)

    def test_size_mismatch_raises(self):
        info = updater.UpdateInfo(
            version="9.9.9", tag="v9.9.9", notes="", page_url="",
            asset_url="https://example.com/HackicLab.exe", asset_size=100000,
        )
        with mock.patch.object(updater, "download_bytes", return_value=b"x" * 10):
            with self.assertRaises(RuntimeError):
                updater.download_update(info)

    def test_missing_asset_raises(self):
        info = updater.UpdateInfo(version="1", tag="v1", notes="", page_url="", asset_url="")
        with self.assertRaises(RuntimeError):
            updater.download_update(info)


class HelperScriptTests(unittest.TestCase):
    def test_script_waits_and_replaces(self):
        text = updater.helper_script(Path(r"C:\app\HackicLab.exe"),
                                     Path(r"C:\tmp\new.exe"), 4242)
        self.assertIn("PID eq 4242", text)
        self.assertIn(r'copy /y "C:\tmp\new.exe" "C:\app\HackicLab.exe"', text)
        self.assertIn("start", text)

    def test_can_self_update_only_for_frozen(self):
        with mock.patch.object(updater.sys, "frozen", False, create=True):
            self.assertFalse(updater.can_self_update())
        with mock.patch.object(updater.sys, "frozen", True, create=True):
            self.assertTrue(updater.can_self_update())


if __name__ == "__main__":
    unittest.main()
