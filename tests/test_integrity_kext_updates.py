"""Тесты манифеста целостности EFI и проверки обновлений кекстов."""

from __future__ import annotations

import plistlib
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from hackiclab.builder.integrity_manifest import (
    MANIFEST_NAME,
    read_manifest,
    sha256_file,
    verify_manifest,
    write_manifest,
)
from hackiclab.builder.kext_updates import (
    check_updates,
    installed_versions,
    normalize_version,
)


class IntegrityManifestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "OC").mkdir()
        (self.root / "OC" / "config.plist").write_text("<plist/>", encoding="utf-8")
        (self.root / "BOOT").mkdir()
        (self.root / "BOOT" / "BOOTx64.efi").write_bytes(b"MZ")

    def test_write_and_verify_ok(self):
        manifest = write_manifest(self.root)
        self.assertIsNotNone(manifest)
        self.assertTrue(manifest.name == MANIFEST_NAME)
        report = verify_manifest(self.root)
        assert report is not None
        self.assertTrue(report.ok)
        self.assertEqual(report.checked, 2)
        self.assertEqual(report.drift, 0)
        self.assertEqual(report.added, [])

    def test_changed_file_is_reported(self):
        write_manifest(self.root)
        (self.root / "OC" / "config.plist").write_text("<plist>changed</plist>",
                                                      encoding="utf-8")
        report = verify_manifest(self.root)
        assert report is not None
        self.assertFalse(report.ok)
        self.assertIn("OC/config.plist", report.changed)

    def test_missing_file_is_reported(self):
        write_manifest(self.root)
        (self.root / "BOOT" / "BOOTx64.efi").unlink()
        report = verify_manifest(self.root)
        assert report is not None
        self.assertFalse(report.ok)
        self.assertIn("BOOT/BOOTx64.efi", report.missing)

    def test_added_file_does_not_break_integrity(self):
        write_manifest(self.root)
        (self.root / "OC" / "extra.txt").write_text("x", encoding="utf-8")
        report = verify_manifest(self.root)
        assert report is not None
        self.assertTrue(report.ok)
        self.assertIn("OC/extra.txt", report.added)

    def test_no_manifest_returns_none(self):
        self.assertIsNone(verify_manifest(self.root))
        self.assertIsNone(read_manifest(self.root))

    def test_empty_folder_has_no_manifest(self):
        empty = self.root / "empty"
        empty.mkdir()
        self.assertIsNone(write_manifest(empty))

    def test_sha256_matches_hashlib(self):
        import hashlib
        path = self.root / "OC" / "config.plist"
        self.assertEqual(sha256_file(path),
                         hashlib.sha256(path.read_bytes()).hexdigest())


class KextUpdatesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.kexts = Path(self._tmp.name) / "Kexts"
        self.kexts.mkdir()

    def _kext(self, name: str, version: str):
        info = self.kexts / f"{name}.kext" / "Contents"
        info.mkdir(parents=True)
        (info / "Info.plist").write_bytes(plistlib.dumps(
            {"CFBundleShortVersionString": version}))

    def test_normalize_version_strips_prefix(self):
        self.assertEqual(normalize_version("RestrictEvents-1.1.5",
                                           "RestrictEvents-"), "1.1.5")
        self.assertEqual(normalize_version("v1.2.0"), "1.2.0")
        self.assertEqual(normalize_version("release"), "")

    def test_installed_versions_read_info_plist(self):
        self._kext("Lilu", "1.6.7")
        self._kext("NotInDb", "9.9")
        versions = installed_versions(self.kexts)
        self.assertEqual(versions.get("Lilu"), "1.6.7")
        self.assertNotIn("NotInDb", versions)

    def test_check_updates_marks_newer_release(self):
        self._kext("Lilu", "1.6.7")
        self._kext("AppleALC", "1.9.0")
        states = check_updates(
            self.kexts, fetch_latest=lambda repo: "1.6.9")
        by_name = {s.name: s for s in states}
        self.assertEqual(by_name["Lilu"].status, "update")
        self.assertEqual(by_name["Lilu"].latest, "1.6.9")

    def test_check_updates_marks_current(self):
        self._kext("Lilu", "1.6.7")
        states = check_updates(
            self.kexts, fetch_latest=lambda repo: "Lilu-1.6.7")
        by_name = {s.name: s for s in states}
        self.assertEqual(by_name["Lilu"].status, "ok")
        self.assertFalse(by_name["Lilu"].has_update)

    def test_unknown_when_network_fails(self):
        self._kext("Lilu", "1.6.7")
        states = check_updates(self.kexts, fetch_latest=lambda repo: "")
        by_name = {s.name: s for s in states}
        self.assertEqual(by_name["Lilu"].status, "unknown")


if __name__ == "__main__":
    unittest.main()
