"""Карта дисков и загрузчиков (Windows-only, только чтение).

Показывает диски, разделы, ESP и найденные загрузчики (Windows, OpenCore,
Linux/GRUB, rEFInd), а также предупреждает о конфликтах: MBR там, где macOS
требует GPT, или несколько OpenCore на внутренних дисках.

Никаких операций записи в чужие ESP: модуль только читает и предупреждает.
Логика адаптирована из hackmate (dualboot.py, MIT).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_EFI_GUID = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"

_LINUX_DIRS = {
    "ubuntu", "fedora", "debian", "arch", "manjaro", "gentoo",
    "opensuse", "centos", "rhel", "bazzite", "nobara", "pop",
    "mint", "zorin", "elementary",
}


@dataclass
class PartitionInfo:
    device: str
    size: str
    fs_type: str
    label: str
    mount: str
    is_efi: bool
    access_paths: list = field(default_factory=list)


@dataclass
class DiskInfo:
    device: str
    model: str
    size: str
    transport: str
    is_gpt: bool
    partitions: list[PartitionInfo] = field(default_factory=list)


@dataclass
class BootloaderInfo:
    partition: str
    windows: bool = False
    linux_grub: bool = False
    linux_efi: bool = False
    opencore: bool = False
    refind: bool = False
    other: list[str] = field(default_factory=list)


def _powershell(script: str, timeout: int = 30) -> str:
    """Запускает PowerShell и возвращает stdout в UTF-8 (кириллица в метках)."""
    wrapper = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "$OutputEncoding = [System.Text.Encoding]::UTF8; "
        + script
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", wrapper],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout,
        )
        return (r.stdout or "").strip()
    except Exception:
        return ""


def _bytes_to_human(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024 or unit == "TB":
            return f"{b:.0f} {unit}"
        b //= 1024
    return f"{b} TB"


def scan_disks() -> list[DiskInfo]:
    """Список физических дисков с разделами (через Get-Disk/Get-Partition)."""
    script = r"""
$disks = Get-Disk | Sort-Object Number | ForEach-Object {
    $d = $_
    $parts = Get-Partition -DiskNumber $d.Number -ErrorAction SilentlyContinue |
             Sort-Object PartitionNumber | ForEach-Object {
        $p   = $_
        $vol = Get-Volume -Partition $p -ErrorAction SilentlyContinue
        [PSCustomObject]@{
            name   = "Disk$($d.Number)p$($p.PartitionNumber)"
            size   = $p.Size
            fs     = if ($vol) { $vol.FileSystemType } else { "" }
            label  = if ($vol) { $vol.FileSystemLabel } else { "" }
            mount  = if ($vol -and $vol.DriveLetter) { "$($vol.DriveLetter):" } else { "" }
            is_esp = ($p.GptType -eq "{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}")
            access = @($p.AccessPaths)
        }
    }
    [PSCustomObject]@{
        device     = "Disk$($d.Number)"
        model      = $d.FriendlyName
        size       = $d.Size
        transport  = $d.BusType
        is_gpt     = ($d.PartitionStyle -eq "GPT")
        partitions = @($parts)
    }
}
$disks | ConvertTo-Json -Depth 5
"""
    out = _powershell(script, timeout=40)
    if not out:
        return []
    try:
        data = json.loads(out)
    except Exception:
        return []
    if isinstance(data, dict):
        data = [data]

    disks: list[DiskInfo] = []
    for d in data:
        if not isinstance(d, dict):
            continue
        disk = DiskInfo(
            device=d.get("device") or "?",
            model=d.get("model") or "Unknown",
            size=_bytes_to_human(int(d.get("size") or 0)),
            transport=str(d.get("transport") or "?"),
            is_gpt=bool(d.get("is_gpt", True)),
        )
        for p in (d.get("partitions") or []):
            if not isinstance(p, dict):
                continue
            disk.partitions.append(PartitionInfo(
                device=p.get("name") or "?",
                size=_bytes_to_human(int(p.get("size") or 0)),
                fs_type=(p.get("fs") or "").lower(),
                label=p.get("label") or "",
                mount=p.get("mount") or "",
                is_efi=bool(p.get("is_esp")),
                access_paths=[a for a in (p.get("access") or []) if a],
            ))
        disks.append(disk)
    return disks


def _scan_efi_dir(root: Path, info: BootloaderInfo) -> bool:
    """Читает EFI раздела. False — если каталог недоступен/не читается."""
    efi = Path(root) / "EFI"
    try:
        if not efi.exists():
            return False
        entries = list(efi.iterdir())
    except Exception:
        return False

    for sub in entries:
        try:
            if not sub.is_dir():
                continue
            name = sub.name
            if name == "Microsoft" and (sub / "Boot" / "bootmgfw.efi").exists():
                info.windows = True
            elif name in _LINUX_DIRS:
                if (sub / "grubx64.efi").exists():
                    info.linux_grub = True
                else:
                    info.other.append(name)
            elif (name == "systemd" and (sub / "systemd-bootx64.efi").exists()) or name == "Linux":
                info.linux_efi = True
            elif name == "OC" and (sub / "OpenCore.efi").exists():
                info.opencore = True
            elif name == "refind" and (sub / "refind_x64.efi").exists():
                info.refind = True
            elif name not in ("BOOT", "tools", "Tools"):
                info.other.append(name)
        except Exception:
            continue
    return True


def _efi_root_paths(part: PartitionInfo) -> list[Path]:
    """Пути, где можно прочитать EFI раздела (буква или том без буквы)."""
    roots: list[Path] = []
    if part.mount:
        roots.append(Path(f"{part.mount.rstrip(':')}:\\"))
    for raw in part.access_paths:
        if raw.startswith("\\\\?\\Volume{"):
            try:
                roots.append(Path(raw.rstrip("\\") + "\\"))
            except Exception:
                continue
    return roots


def detect_bootloaders(part: PartitionInfo) -> Optional[BootloaderInfo]:
    """Загрузчики на EFI-разделе. None — если раздел не читается."""
    if not part.is_efi:
        return None
    roots = _efi_root_paths(part)
    if not roots:
        return None
    info = BootloaderInfo(partition=part.device)
    for root in roots:
        if _scan_efi_dir(root, info):
            return info
    return None


def scan_all_bootloaders(disks: list[DiskInfo]) -> dict[str, BootloaderInfo]:
    """Сканирует все EFI-разделы. Возвращает {device: BootloaderInfo}."""
    result: dict[str, BootloaderInfo] = {}
    for disk in disks:
        for part in disk.partitions:
            if not part.is_efi:
                continue
            info = detect_bootloaders(part)
            if info is not None:
                result[part.device] = info
    return result


def check_conflicts(disks: list[DiskInfo],
                    bootloaders: dict[str, BootloaderInfo]) -> list[dict]:
    """Предупреждения в виде {key, ...} для перевода в UI."""
    warnings: list[dict] = []

    part_transport = {p.device: d.transport.upper()
                      for d in disks for p in d.partitions}
    oc_internal = [dev for dev, b in bootloaders.items()
                   if b.opencore and part_transport.get(dev, "") != "USB"]
    if len(oc_internal) > 1:
        warnings.append({"key": "diskmap.warn_oc_dupe", "count": len(oc_internal)})

    for disk in disks:
        if not disk.is_gpt and disk.transport.upper() != "USB":
            warnings.append({"key": "diskmap.warn_mbr",
                             "device": disk.device, "model": disk.model})
    return warnings


def build_disk_tree(disks: list[DiskInfo],
                    bootloaders: Optional[dict] = None) -> str:
    """Текстовая карта дисков для интерфейса."""
    bootloaders = bootloaders or {}
    lines: list[str] = []
    for disk in disks:
        scheme = "GPT" if disk.is_gpt else "MBR"
        lines.append(f"{disk.device}  {disk.model}  {disk.size}  {scheme}  {disk.transport}")
        for i, part in enumerate(disk.partitions):
            connector = "└─" if i == len(disk.partitions) - 1 else "├─"
            tags: list[str] = []
            if part.is_efi:
                tags.append("EFI")
            info = bootloaders.get(part.device)
            if info:
                if info.windows:
                    tags.append("Windows")
                if info.linux_grub or info.linux_efi:
                    tags.append("Linux")
                if info.opencore:
                    tags.append("OpenCore")
                if info.refind:
                    tags.append("rEFInd")
                for unknown in info.other:
                    tags.append(unknown)
            label = part.label or part.fs_type.upper() or "?"
            tail = ("  " + " ".join(tags)) if tags else ""
            lines.append(f"  {connector} {part.device}  {part.size}  {label}{tail}")
    return "\n".join(lines) if lines else ""
