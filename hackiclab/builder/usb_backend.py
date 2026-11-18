"""Платформенный бэкенд записи на USB: diskpart на Windows, diskutil на macOS.

Интерфейс импортирует функции отсюда и не думает о платформе.
"""

from __future__ import annotations

import sys

if sys.platform == "darwin":
    from .usb_mac import (
        USBDevice,
        USBWriteResult,
        _find_free_drive_letter,
        backup_efi,
        copy_efi,
        format_usb,
        get_usb_devices,
        is_admin,
        list_backups,
        relaunch_as_admin,
        write_efi_to_usb,
    )
else:
    from .usb_writer import (  # noqa: F401
        USBDevice,
        USBWriteResult,
        _find_free_drive_letter,
        backup_efi,
        copy_efi,
        format_usb,
        get_usb_devices,
        is_admin,
        list_backups,
        relaunch_as_admin,
        write_efi_to_usb,
    )

__all__ = [
    "USBDevice",
    "USBWriteResult",
    "backup_efi",
    "copy_efi",
    "format_usb",
    "get_usb_devices",
    "is_admin",
    "list_backups",
    "relaunch_as_admin",
    "write_efi_to_usb",
]
