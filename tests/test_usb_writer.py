"""Тесты проверки цели записи на USB (без реального diskpart)."""

from __future__ import annotations

import time
import unittest
from typing import cast
from unittest import mock

import _bootstrap  # noqa: F401  (добавляет корень проекта в sys.path)

from hackiclab.builder import usb_writer as uw


class AssertTargetTests(unittest.TestCase):
    def test_rejects_system_disk(self):
        with mock.patch.object(uw, "_disk_info", return_value={"BusType": "USB", "IsSystem": True}):
            with self.assertRaises(RuntimeError):
                uw._assert_usb_target("F:", "3")

    def test_rejects_non_usb_bus(self):
        with mock.patch.object(uw, "_disk_info", return_value={"BusType": "NVMe", "IsSystem": False}):
            with self.assertRaises(RuntimeError):
                uw._assert_usb_target("F:", "3")

    def test_accepts_usb_disk(self):
        with mock.patch.object(uw, "_disk_info", return_value={"BusType": "USB", "IsSystem": False}), \
             mock.patch.object(uw, "_resolve_disk_number", return_value="3"):
            uw._assert_usb_target("F:", "3")

    def test_rejects_shifted_drive_letter(self):
        with mock.patch.object(uw, "_disk_info", return_value={"BusType": "USB", "IsSystem": False}), \
             mock.patch.object(uw, "_resolve_disk_number", return_value="5"):
            with self.assertRaises(RuntimeError):
                uw._assert_usb_target("F:", "3")

    def test_rejects_unreadable_disk(self):
        with mock.patch.object(uw, "_disk_info", return_value={}):
            with self.assertRaises(RuntimeError):
                uw._assert_usb_target("DISK3", "3")


class FormatUsbScriptTests(unittest.TestCase):
    def test_script_creates_gpt_and_efi_partition(self):
        scripts = []

        def fake_diskpart(text):
            scripts.append(text)
            return 0, ""

        def fake_powershell(script, timeout=15):
            if "Size / 1MB" in script:
                return "30528"
            if "Test-Path" in script:
                formatted = any("format fs=fat32" in s for s in scripts)
                return "true" if formatted else "false"
            return ""

        with mock.patch.object(uw, "is_admin", return_value=True), \
             mock.patch.object(uw, "_resolve_disk_number", return_value="3"), \
             mock.patch.object(uw, "_assert_usb_target") as guard, \
             mock.patch.object(uw, "_find_free_drive_letter", return_value="H:"), \
             mock.patch.object(uw, "_powershell", side_effect=fake_powershell), \
             mock.patch.object(uw, "_run_diskpart", side_effect=fake_diskpart), \
             mock.patch.object(time, "sleep", lambda *_: None):
            result = uw.format_usb("F:")

        self.assertEqual(result, "H:")
        guard.assert_called_once()
        create = next(s for s in scripts if "clean" in s)
        self.assertIn("convert gpt", create)
        self.assertIn("create partition efi", create)
        self.assertIn("select disk 3", create)
        self.assertTrue(any("format fs=fat32" in s for s in scripts))


    def test_removable_stick_uses_mbr_primary(self):
        """На съёмной флешке Windows не создаёт EFI-раздел — только MBR."""
        scripts = []

        def fake_diskpart(text):
            scripts.append(text)
            return 0, ""

        def fake_powershell(script, timeout=15):
            if "Size / 1MB" in script:
                return "29000"
            if "Test-Path" in script:
                return "true" if any("format fs=fat32" in s for s in scripts) else "false"
            return ""

        with mock.patch.object(uw, "is_admin", return_value=True), \
             mock.patch.object(uw, "_resolve_disk_number", return_value="3"), \
             mock.patch.object(uw, "_assert_usb_target"), \
             mock.patch.object(uw, "_is_removable", return_value=True), \
             mock.patch.object(uw, "_find_free_drive_letter", return_value="H:"), \
             mock.patch.object(uw, "_powershell", side_effect=fake_powershell), \
             mock.patch.object(uw, "_run_diskpart", side_effect=fake_diskpart), \
             mock.patch.object(time, "sleep", lambda *_: None):
            uw.format_usb("F:")

        create = next(s for s in scripts if "clean" in s)
        self.assertNotIn("convert gpt", create)
        self.assertNotIn("create partition efi", create)
        self.assertIn("create partition primary", create)
        self.assertIn("active", create)

    def test_fixed_disk_keeps_gpt_efi(self):
        scripts = []

        def fake_diskpart(text):
            scripts.append(text)
            return 0, ""

        def fake_powershell(script, timeout=15):
            if "Size / 1MB" in script:
                return "29000"
            if "Test-Path" in script:
                return "true" if any("format fs=fat32" in s for s in scripts) else "false"
            return ""

        with mock.patch.object(uw, "is_admin", return_value=True), \
             mock.patch.object(uw, "_resolve_disk_number", return_value="3"), \
             mock.patch.object(uw, "_assert_usb_target"), \
             mock.patch.object(uw, "_is_removable", return_value=False), \
             mock.patch.object(uw, "_find_free_drive_letter", return_value="H:"), \
             mock.patch.object(uw, "_powershell", side_effect=fake_powershell), \
             mock.patch.object(uw, "_run_diskpart", side_effect=fake_diskpart), \
             mock.patch.object(time, "sleep", lambda *_: None):
            uw.format_usb("F:")

        create = next(s for s in scripts if "clean" in s)
        self.assertIn("convert gpt", create)
        self.assertIn("create partition efi", create)

    def test_diskpart_failure_reports_reason(self):
        detail = ("Microsoft DiskPart version 10.0\n"
                  "Ошибка: эта операция не поддерживается на съёмных носителях.")
        self.assertIn("не поддерживается", uw._diskpart_reason(detail))


class ConfirmPhraseTests(unittest.TestCase):
    def test_phrase_uses_letter_or_disk_number(self):
        try:
            from hackiclab.ui.main_window import MainWindow
        except Exception as exc:  # PySide6 отсутствует — тест не применим
            self.skipTest(f"PySide6 недоступен: {exc}")
        self.assertEqual(MainWindow._confirm_phrase(cast(MainWindow, None), "f:"), "WRITE F:")
        self.assertEqual(MainWindow._confirm_phrase(cast(MainWindow, None), "DISK12"), "WRITE DISK 12")
        self.assertEqual(MainWindow._confirm_phrase(cast(MainWindow, None), "RAWDISK7"), "WRITE DISK 7")
        self.assertEqual(MainWindow._confirm_phrase(cast(MainWindow, None), "F:", "9"), "WRITE F:")


if __name__ == "__main__":
    unittest.main()


class BackupTests(unittest.TestCase):
    def test_list_backups_sorted_by_time(self):
        import os
        import tempfile
        import time
        from pathlib import Path

        from hackiclab.builder.usb_writer import list_backups

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "EFI-old"
            new = root / "EFI-new"
            old.mkdir()
            new.mkdir()
            os.utime(old, (time.time() - 100, time.time() - 100))
            names = [p.name for p in list_backups(root)]
        self.assertEqual(names, ["EFI-new", "EFI-old"])

    def test_restore_requires_existing_backup(self):
        import tempfile
        from pathlib import Path

        from hackiclab.builder.usb_writer import restore_backup

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                restore_backup(Path(tmp) / "missing", "Z")
