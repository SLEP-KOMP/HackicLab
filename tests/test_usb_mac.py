"""Тесты macOS-бэкенда записи: разбор diskutil и копирование EFI."""

from __future__ import annotations

import plistlib
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from hackiclab.builder.usb_mac import (
    _human_size,
    copy_efi,
    list_backups,
    parse_device_list,
)

LIST_PLIST = plistlib.dumps({
    "WholeDisks": ["disk4", "disk0"],
    "AllDisksAndPartitions": [
        {"DeviceIdentifier": "disk4", "Size": 32000000000},
        {"DeviceIdentifier": "disk0", "Size": 500000000000},
    ],
})


class ParseTests(unittest.TestCase):
    def test_only_whole_disks_are_taken(self):
        disks = parse_device_list(LIST_PLIST)
        self.assertEqual([d["device"] for d in disks], ["/dev/disk4", "/dev/disk0"])
        self.assertEqual(disks[0]["disk_number"], "4")

    def test_broken_plist_raises(self):
        with self.assertRaises(plistlib.InvalidFileException):
            parse_device_list(b"<not a plist>")

    def test_human_size(self):
        self.assertEqual(_human_size(32_000_000_000), "32GB")
        self.assertEqual(_human_size(512_000_000), "512MB")
        self.assertEqual(_human_size(0), "")


class CopyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / "build"
        (self.source / "EFI" / "OC").mkdir(parents=True)
        (self.source / "EFI" / "OC" / "config.plist").write_bytes(b"<plist/>")
        (self.source / "EFI" / "BOOT").mkdir()
        (self.source / "EFI" / "BOOT" / "BOOTx64.efi").write_bytes(b"boot")
        self.volume = self.root / "volume"
        self.volume.mkdir()

    def test_efi_is_copied(self):
        copy_efi(self.source, str(self.volume), backup=False)
        self.assertTrue((self.volume / "EFI" / "OC" / "config.plist").is_file())

    def test_old_efi_is_backed_up(self):
        old = self.volume / "EFI" / "OC"
        old.mkdir(parents=True)
        (old / "old.txt").write_text("old", encoding="utf-8")
        backup_root = self.root / "backups"
        made = copy_efi(self.source, str(self.volume), backup_root=backup_root)
        assert made is not None
        self.assertTrue((made / "OC" / "old.txt").is_file())
        self.assertFalse((self.volume / "EFI" / "OC" / "old.txt").exists())

    def test_missing_volume_is_reported(self):
        with self.assertRaises(RuntimeError):
            copy_efi(self.source, str(self.root / "nope"), backup=False)

    def test_backups_are_listed(self):
        path = self.root / "backups" / "EFI-20260101-000000"
        path.mkdir(parents=True)
        import hackiclab.builder.usb_mac as mac

        original = mac._backup_root
        mac._backup_root = lambda: self.root / "backups"
        try:
            self.assertEqual(len(list_backups()), 1)
        finally:
            mac._backup_root = original


if __name__ == "__main__":
    unittest.main()
