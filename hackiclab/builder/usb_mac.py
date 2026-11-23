"""Запись EFI на флешку на macOS: diskutil вместо diskpart.

Повторяет контракт Windows-версии (``usb_writer``), чтобы интерфейс не знал
о платформе: те же поля устройства, тот же результат записи. Форматирование —
``diskutil eraseDisk`` в FAT32 с таблицей MBR: такой раздел прошивка читает как
загрузочный, а на съёмных носителях MBR надёжнее GPT.
"""

from __future__ import annotations

import json
import os
import plistlib
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

VOLUME_LABEL = "HACKINTOSH"


@dataclass
class USBDevice:
    device: str          # /dev/disk4
    size: str = ""
    label: str = ""
    disk_number: str = ""
    model: str = ""
    letter: str = ""     # точка монтирования: /Volumes/HACKINTOSH
    raw: bool = False
    partition_style: str = ""


@dataclass
class USBWriteResult:
    ok: bool
    message: str = ""
    log: list = field(default_factory=list)
    mount_path: Optional[Path] = None
    backup_path: Optional[Path] = None


def _run(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    from ..proc import run

    return run(args, capture_output=True, text=True, timeout=timeout)


def is_admin() -> bool:
    """На macOS запись на диск требует root (diskutil eraseDisk)."""
    return hasattr(os, "geteuid") and os.geteuid() == 0


def parse_device_list(payload: bytes) -> list[dict]:
    """Разбирает ``diskutil list -plist external physical`` в список дисков."""
    data = plistlib.loads(payload)
    whole = data.get("WholeDisks") or []
    disks = []
    for name in whole:
        if not str(name).startswith("disk"):
            continue
        disks.append({"device": f"/dev/{name}", "disk_number": str(name).replace("disk", "")})
    return disks


def get_usb_devices() -> list[USBDevice]:
    """Внешние физические диски: имя, объём, метка тома, модель."""
    try:
        listed = _run(["diskutil", "list", "-plist", "external", "physical"], timeout=60)
    except Exception:
        return []
    if listed.returncode != 0:
        return []
    try:
        disks = parse_device_list(listed.stdout.encode("utf-8"))
    except Exception:
        return []

    devices: list[USBDevice] = []
    for disk in disks:
        info = _disk_info(disk["device"])
        devices.append(USBDevice(
            device=disk["device"],
            disk_number=disk["disk_number"],
            size=_human_size(info.get("Size", 0)),
            label=str(info.get("VolumeName") or ""),
            model=str(info.get("MediaName") or info.get("IORegistryEntryName") or ""),
            letter=str(info.get("MountPoint") or ""),
            raw=not bool(info.get("Content") or ""),
            partition_style="MBR" if str(info.get("Content") or "").startswith("FDisk")
            else ("GPT" if "GPT" in str(info.get("Content") or "") else ""),
        ))
    return devices


def _disk_info(device: str) -> dict:
    try:
        done = _run(["diskutil", "info", "-plist", device], timeout=60)
        if done.returncode != 0:
            return {}
        return plistlib.loads(done.stdout.encode("utf-8"))
    except Exception:
        return {}


def _human_size(size: int) -> str:
    if not size:
        return ""
    gigabytes = size / (1000 ** 3)
    return f"{gigabytes:.0f}GB" if gigabytes >= 1 else f"{size / (1000 ** 2):.0f}MB"


def format_usb(device: str, drive_letter: str = "") -> str:
    """Форматирует диск в FAT32/MBR и возвращает точку монтирования."""
    if not is_admin():
        raise RuntimeError(
            "Для форматирования флешки нужны права администратора: "
            "запустите HackicLab через sudo или подтвердите запрос системы."
        )
    if not str(device).startswith("/dev/disk"):
        raise RuntimeError(f"Неверное устройство: {device}")
    done = _run(["diskutil", "eraseDisk", "FAT32", VOLUME_LABEL, "MBR", str(device)],
                timeout=600)
    if done.returncode != 0:
        raise RuntimeError(f"diskutil: {done.stderr.strip() or done.stdout.strip()}")
    info = _disk_info(f"{device}s1")
    mount = info.get("MountPoint") or f"/Volumes/{VOLUME_LABEL}"
    return str(mount)


def _backup_root() -> Path:
    return Path.home() / "Library" / "Application Support" / "HackicLab" / "backups"


def backup_efi(efi_dir: Path, backup_root: Optional[Path] = None) -> Path:
    from datetime import datetime

    root = Path(backup_root) if backup_root else _backup_root()
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"EFI-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    shutil.copytree(efi_dir, target)
    return target


def copy_efi(source_efi: Path, mount_path: str, log=None,
             backup: bool = True, backup_root: Optional[Path] = None) -> Optional[Path]:
    """Копирует EFI на смонтированный том, сохраняя прежнюю EFI в резерв."""
    def _log(msg: str):
        if log:
            log(msg)

    source = Path(source_efi) / "EFI" if (Path(source_efi) / "EFI").is_dir() else Path(source_efi)
    root = Path(mount_path)
    if not root.is_dir():
        raise RuntimeError(f"Том не смонтирован: {mount_path}")
    target = root / "EFI"
    backup_path = None
    if target.exists():
        if backup:
            backup_path = backup_efi(target, backup_root)
            _log(f"Резервная копия старой EFI: {backup_path}")
        shutil.rmtree(target)
        _log(f"Удалена старая EFI на {root}")
    shutil.copytree(source, target)
    _log("EFI записана на флешку.")
    return backup_path


def write_efi_to_usb(source_efi: Path, device: str, skip_format: bool = False,
                     recovery_macos: str = "", log=None,
                     backup: bool = True,
                     backup_root: Optional[Path] = None,
                     drive_letter: str = "",
                     make_usb_map: bool = True) -> USBWriteResult:
    """Полный цикл на macOS: (опц.) форматирование, затем запись EFI."""
    res = USBWriteResult(ok=False, log=[])
    log_fn = log or res.log.append
    try:
        mount = ""
        if not skip_format:
            log_fn("Форматирую флешку (FAT32, MBR)…")
            mount = format_usb(device)
        else:
            mount = _disk_info(device).get("MountPoint") or ""
            if not mount:
                raise RuntimeError("Флешка не смонтирована — отформатируйте её или смонтируйте том")
        res.mount_path = Path(mount)
        res.backup_path = copy_efi(Path(source_efi), mount, log=log_fn,
                                   backup=backup, backup_root=backup_root)
        if recovery_macos:
            from .usb_writer import install_recovery_to
            log_fn(f"Скачиваю установщик macOS ({recovery_macos})…")
            message = install_recovery_to(Path(mount), recovery_macos, log=log_fn)
            log_fn(message)
            res.message = f"EFI записана на {mount} | {message}"
        else:
            res.message = f"EFI записана на {mount}"
        res.ok = True
    except Exception as exc:
        res.ok = False
        res.message = str(exc)
        log_fn(f"[err] {exc}")
    return res


def list_backups() -> list[Path]:
    root = _backup_root()
    if not root.is_dir():
        return []
    return sorted(root.glob("EFI-*"), reverse=True)


def _find_free_drive_letter() -> str:
    """На macOS букв дисков нет: интерфейсу нужен пустой ответ."""
    return ""


def disk_map_available() -> bool:
    return False


def json_report(devices: list[USBDevice]) -> str:
    return json.dumps([d.__dict__ for d in devices], ensure_ascii=False)
