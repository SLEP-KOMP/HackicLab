"""Тесты проверки обновлений: сравнение версий, разбор релиза, загрузка."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _bootstrap  # noqa: F401

from hackiclab import updater


def release(version: str, asset: bool = True, size: int = 1234,
            digest: str = "") -> dict:
    assets = []
    if asset:
        assets = [{
            "name": "HackicLab.exe",
            "browser_download_url": f"https://example.com/{version}/HackicLab.exe",
            "size": size,
            "digest": digest,
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
        assert info is not None
        self.assertEqual(info.version, "9.9.9")
        self.assertTrue(info.has_asset)
        self.assertEqual(info.asset_size, 1234)

    def test_same_version_is_ignored(self):
        self.assertIsNone(updater.parse_release(release(updater.__version__)))

    def test_same_version_new_digest_is_a_rebuild(self):
        info = updater.parse_release(
            release(updater.__version__, digest="sha256:new"), current_digest="sha256:old")
        self.assertIsNotNone(info)
        assert info is not None
        self.assertTrue(info.is_rebuild)
        self.assertEqual(info.asset_digest, "sha256:new")

    def test_same_digest_is_not_an_update(self):
        info = updater.parse_release(
            release(updater.__version__, digest="sha256:same"),
            current_digest="sha256:same")
        self.assertIsNone(info)

    def test_rebuild_needs_known_local_digest(self):
        payload = release(updater.__version__, digest="sha256:new")
        self.assertIsNone(updater.parse_release(payload, current_digest=""))

    def test_release_without_asset(self):
        info = updater.parse_release(release("9.9.9", asset=False))
        self.assertIsNotNone(info)
        assert info is not None
        self.assertFalse(info.has_asset)

    def test_release_without_tag(self):
        self.assertIsNone(updater.parse_release({"assets": []}))

    def test_check_for_update_uses_github_json(self):
        payload = json.dumps(release("9.9.9")).encode("utf-8")
        with mock.patch.object(updater, "download_bytes", return_value=payload) as dl:
            info = updater.check_for_update()
        assert info is not None
        self.assertEqual(info.version, "9.9.9")
        called_url = dl.call_args[0][0]
        self.assertIn("api.github.com", called_url)
        self.assertIn("SLEP-KOMP/HackicLab", called_url)

    def test_current_binary_digest_empty_for_source_runs(self):
        with mock.patch.object(updater.sys, "frozen", False, create=True):
            self.assertEqual(updater.current_binary_digest(), "")

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


class ApplyUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.target = self.dir / "HackicLab.exe"
        self.new = self.dir / "new.exe"
        self.target.write_bytes(b"OLD")
        self.new.write_bytes(b"NEWBYTES")

    def test_replaces_running_binary_and_keeps_backup(self):
        with mock.patch.object(updater.sys, "executable", str(self.target)), \
                mock.patch.object(updater, "can_self_update", return_value=True):
            self.assertTrue(updater.apply_update(self.new))
        self.assertEqual(self.target.read_bytes(), b"NEWBYTES")
        self.assertEqual((self.dir / "HackicLab.exe.old").read_bytes(), b"OLD")

    def test_restores_binary_when_copy_fails(self):
        with mock.patch.object(updater.sys, "executable", str(self.target)), \
                mock.patch.object(updater, "can_self_update", return_value=True), \
                mock.patch.object(updater.shutil, "copy2", side_effect=OSError("locked")):
            self.assertFalse(updater.apply_update(self.new))
        self.assertEqual(self.target.read_bytes(), b"OLD")

    def test_apply_requires_frozen_build(self):
        with mock.patch.object(updater, "can_self_update", return_value=False):
            self.assertFalse(updater.apply_update(self.new))
        self.assertEqual(self.target.read_bytes(), b"OLD")

    def test_missing_source_is_rejected(self):
        with mock.patch.object(updater.sys, "executable", str(self.target)), \
                mock.patch.object(updater, "can_self_update", return_value=True):
            self.assertFalse(updater.apply_update(self.dir / "absent.exe"))

    def test_cleanup_removes_old_copy(self):
        old = self.dir / "HackicLab.exe.old"
        old.write_bytes(b"OLD")
        with mock.patch.object(updater.sys, "frozen", True, create=True), \
                mock.patch.object(updater.sys, "executable", str(self.target)):
            updater.cleanup_old_binaries()
        self.assertFalse(old.exists())

    def test_cleanup_is_noop_for_source_runs(self):
        old = self.dir / "HackicLab.exe.old"
        old.write_bytes(b"OLD")
        with mock.patch.object(updater.sys, "frozen", False, create=True), \
                mock.patch.object(updater.sys, "executable", str(self.target)):
            updater.cleanup_old_binaries()
        self.assertTrue(old.exists())

    def test_relaunch_starts_binary(self):
        with mock.patch.object(updater.sys, "executable", str(self.target)), \
                mock.patch.object(updater.subprocess, "Popen") as popen:
            self.assertTrue(updater.relaunch_self())
        self.assertEqual(popen.call_args[0][0], [str(self.target)])

    def test_can_self_update_only_for_frozen(self):
        with mock.patch.object(updater.sys, "frozen", False, create=True):
            self.assertFalse(updater.can_self_update())
        with mock.patch.object(updater.sys, "frozen", True, create=True):
            self.assertTrue(updater.can_self_update())


if __name__ == "__main__":
    unittest.main()
