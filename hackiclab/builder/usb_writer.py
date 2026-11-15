"""Запись собранной EFI на USB-флешку (подход из hackmate, адаптирован для Windows).

Этапы:
  1) форматуем флешку как GPT + ESP (FAT32) через diskpart;
  2) раскладываем готовую папку EFI на целевую флешку;
  3) монтируем диск (Windows монтирует сам), отдаём путь.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class USBDevice:
    device: str          # "E:" или "RAWDISK<n>"
    size: str            # "15GB"
    label: str
    disk_number: str = ""


@dataclass
class USBWriteResult:
    ok: bool
    error: str = ""
    target_letter: str = ""
    backup_path: str = ""
    log: list = field(default_factory=list)


def _powershell(script: str, timeout: int = 15) -> str:
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=timeout,
        )
        return (r.stdout or "").strip()
    except Exception:
        return ""


def get_usb_devices() -> list[USBDevice]:
    """Список USB-накопителей (device, size, label). RAWDISK<n> — без разметки."""
    devices: list[USBDevice] = []

    out_disk = _powershell(
        "Get-Disk | Where-Object {$_.BusType -eq 'USB'} | "
        "Select-Object Number, FriendlyName, Size | ConvertTo-Json",
        timeout=20,
    )
    if not out_disk:
        return devices

    import json
    try:
        disks = json.loads(out_disk)
    except Exception:
        return devices
    if isinstance(disks, dict):
        disks = [disks]

    # порядок важн: номер диска => (размер, имя)
    usb: dict[str, dict] = {}
    for d in disks:
        num = str(d.get("Number") or "").strip()
        if num:
            usb[num] = {
                "size": d.get("Size") or 0,
                "friendly": str(d.get("FriendlyName") or "").strip(),
            }

    if not usb:
        return devices

    out_part = _powershell(
        "Get-Partition | Where-Object {$_.DriveLetter} | Select-Object DiskNumber, DriveLetter",
        timeout=20,
    )
    parts: list = []
    if out_part:
        try:
            import json as _j
            parts = _j.loads(out_part)
            if isinstance(parts, dict):
                parts = [parts]
        except Exception:
            parts = []

    out_vol = _powershell(
        "Get-Volume | Where-Object {$_.DriveLetter} | "
        "Select-Object DriveLetter, FileSystemLabel, Size",
        timeout=20,
    )
    vol_map: dict = {}
    if out_vol:
        try:
            import json as _j
            vols = _j.loads(out_vol)
            if isinstance(vols, dict):
                vols = [vols]
            for v in vols:
                letter = str(v.get("DriveLetter") or "").strip().upper()
                if letter:
                    vol_map[letter] = {
                        "label": str(v.get("FileSystemLabel") or "").strip(),
                        "size": v.get("Size") or 0,
                    }
        except Exception:
            pass

    seen = set()
    disks_with_letter = set()
    for p in parts:
        disk_num = str(p.get("DiskNumber") or "").strip()
        letter = str(p.get("DriveLetter") or "").strip().upper()
        if disk_num in usb and letter and letter not in seen:
            seen.add(letter)
            disks_with_letter.add(disk_num)
            meta = vol_map.get(letter, {})
            label = meta.get("label") or usb[disk_num]["friendly"] or ""
            size_b = meta.get("size") or usb[disk_num]["size"] or 0
            size_gb = f"{int(size_b) // 1024 // 1024 // 1024}GB" if size_b else "?"
            devices.append(USBDevice(f"{letter}:", size_gb, label, disk_num))

    # флешки без разметки
    for disk_num, meta in usb.items():
        if disk_num not in disks_with_letter:
            size_gb = f"{int(meta['size']) // 1024 // 1024 // 1024}GB" if meta.get("size") else "?"
            label = "(raw / не разметана)" if not meta.get("friendly") else meta["friendly"]
            devices.append(USBDevice(f"RAWDISK{disk_num}", size_gb, label, disk_num))
    return devices


def resolve_drive_letter(device: str, disk_number: str = "") -> str:
    """Реальная буква выбранного накопителя: "F:" либо "" (буквы нет)."""
    dev = (device or "").strip().upper()
    if len(dev) == 2 and dev.endswith(":"):
        used = _powershell(
            "[System.IO.DriveInfo]::GetDrives() | ForEach-Object { $_.Name.Substring(0,1).ToUpper() }"
        )
        return dev if dev[0] in set(used.split()) else ""

    num = str(disk_number or "").strip()
    if not num and dev.startswith("RAWDISK"):
        num = dev[7:]
    if not num:
        return ""

    letter = _read_disk_letter(num)
    if letter:
        return letter
    # последняя попытка: назначить букву разделу и перечитать
    _powershell(
        f"Get-Partition -DiskNumber {num} | Where-Object {{ -not $_.DriveLetter }} | "
        f"Add-PartitionAccessPath -AssignDriveLetter -ErrorAction SilentlyContinue",
        timeout=20,
    )
    return _read_disk_letter(num)


def _read_disk_letter(disk_number: str) -> str:
    out = _powershell(
        f"Get-Partition -DiskNumber {disk_number} | Where-Object {{ $_.DriveLetter }} | "
        f"Select-Object -First 1 -ExpandProperty DriveLetter",
        timeout=20,
    )
    letter = (out or "").strip().upper()
    return f"{letter[0]}:" if letter and letter[0].isalpha() else ""


def _find_free_drive_letter() -> str:
    used_raw = _powershell(
        "[System.IO.DriveInfo]::GetDrives() | ForEach-Object { $_.Name.Substring(0,1).ToUpper() }"
    )
    used = set(used_raw.split())
    for letter in "ZYXWVUTSRQPONMLKJIHGFED":
        if letter not in used:
            return f"{letter}:"
    raise RuntimeError("Нет свободной буквы диска — освободите одну и повторите.")


def _resolve_disk_number(device: str) -> str:
    letter = device.rstrip(":\\").upper()
    if letter.startswith("RAWDISK"):
        return letter[7:]
    num = _powershell(
        f"(Get-Partition -DriveLetter {letter} | Get-Disk).Number"
    )
    if num.isdigit():
        return num
    num = _powershell(
        f"(Get-Volume -DriveLetter {letter} -ErrorAction SilentlyContinue | "
        f"Get-Partition -ErrorAction SilentlyContinue | Get-Disk).Number"
    )
    if num.isdigit():
        return num
    # единственная USB → берём её
    usb = _powershell("(Get-Disk | Where-Object {$_.BusType -eq 'USB'}).Number")
    nums = usb.split()
    if len(nums) == 1 and nums[0].isdigit():
        return nums[0]
    raise RuntimeError(
        f"Не удалось определить номер диска для {device}: флешка может быть RAW "
        f"(без файловой системы). Откройте Управление дисками, отформатируйте в FAT32 "
        f"и попробуйте режим «Уже отформатирована»."
    )


def _run_diskpart(script_text: str) -> tuple[int, str]:
    p = Path(tempfile.mktemp(suffix=".txt"))
    p.write_text(script_text, encoding="utf-8")
    try:
        r = subprocess.run(
            ["diskpart", "/s", str(p)],
            capture_output=True, timeout=120,
        )
        out = (r.stdout.decode("oem", errors="replace") +
               r.stderr.decode("oem", errors="replace"))
        return r.returncode, out.strip()[-500:]
    finally:
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass


def format_usb(device: str, drive_letter: str = "") -> str:
    """Форматирует USB как FAT32 + GPT + ESP, возвращает букву диска.

    Опция drive_letter — занять конкретную букву (если задана); иначе найдёт свободную.
    """
    import time as _time
    letter = device.rstrip(":\\").upper()
    disk_num = _resolve_disk_number(letter)

    if not drive_letter:
        drive_letter = _find_free_drive_letter()
    target = drive_letter.rstrip(":\\").upper()

    # проверим, что буква не занята
    busy = _powershell(f"Test-Path {target}:\\").lower()
    if busy == "true":
        raise RuntimeError(
            f"Буква {target}: уже занята другим накопителем. Освободите её и повторите."
        )

    # размер раздела: 4 ГБ хватает для EFI, но не больше, чем диск
    size_mb_raw = _powershell(f"[math]::Floor((Get-Disk -Number {disk_num}).Size / 1MB)")
    partition_mb = 4096
    if size_mb_raw.isdigit():
        partition_mb = min(4096, max(1, int(size_mb_raw) - 8))

    create_script = (
        f"select disk {disk_num}\n"
        "clean\n"
        f"create partition primary size={partition_mb}\n"
        "exit\n"
    )
    format_script = (
        f"select disk {disk_num}\n"
        "select partition 1\n"
        "format fs=fat32 quick label=HACKINTOSH\n"
        f"assign letter={target}\n"
        "exit\n"
    )

    last_detail = ""
    for attempt in range(3):
        code, detail = _run_diskpart(create_script)
        if code != 0:
            last_detail = detail
            _time.sleep(3)
            continue
        _time.sleep(2)
        code, detail = _run_diskpart(format_script)
        if code == 0:
            last_detail = ""
            break
        last_detail = detail
        _time.sleep(3)

    if not last_detail == "":
        raise RuntimeError(f"diskpart не смог отформатировать флешку:\n{last_detail}")

    mounted = _powershell(f"Test-Path {target}:\\").lower()
    if mounted != "true":
        raise RuntimeError(
            f"Флешка отформатирована, но {target}: не появилась. "
            f"Переподключите флешку и используйте «Уже отформатирована»."
        )
    return f"{target}:"


def _backup_root() -> Path:
    """Каталог резервных копий EFI (в профиле пользователя)."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "HackicLab" / "backups"


def backup_efi(efi_dir: Path, backup_root: Optional[Path] = None) -> Path:
    """Копирует существующую EFI в резервную папку и возвращает путь копии.

    Вызывается перед перезаписью EFI на флешке: старая структура сохраняется
    целиком, чтобы неудачный ремонт можно было откатить.
    """
    import shutil
    from datetime import datetime

    src = Path(efi_dir)
    if not src.is_dir():
        raise RuntimeError(f"Резервировать нечего: {src} — не папка")

    root = Path(backup_root) if backup_root else _backup_root()
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = root / f"{src.name}-{stamp}"
    suffix = 1
    while dst.exists():
        dst = root / f"{src.name}-{stamp}-{suffix}"
        suffix += 1
    shutil.copytree(str(src), str(dst))
    return dst


def copy_efi(source_efi: Path, target_letter: str, log=None,
             backup: bool = True, backup_root: Optional[Path] = None) -> Optional[Path]:
    """Копирует содержимое собранной папки (EFI/) на флешку.

    Если на флешке уже есть EFI, она сначала копируется в резервную папку
    (``backup=True``), и только после успешного бэкапа удаляется. При ошибке
    бэкапа старая EFI остаётся нетронутой.
    """
    def _log(msg):
        if log:
            log(msg)

    src_efi = Path(source_efi)
    if not src_efi.exists():
        raise RuntimeError(f"Папка EFI не найдена: {src_efi}")

    letter = target_letter.rstrip(":\\")

    # EFI/ на флешку (корень флешки = буква) — как у hackmate: EFI папка в корень
    dst_root = Path(f"{letter}:\\")
    if not dst_root.exists():
        raise RuntimeError(f"Флешка {letter}: недоступна.")

    # источник может быть сама папка EFI или её родитель
    candidate = src_efi
    if (src_efi / "EFI").exists():
        candidate = src_efi / "EFI"
    elif (src_efi / "OC").exists():
        candidate = src_efi
    else:
        # если в целевой папке лежит EFI/OC — возьмём всё
        candidate = src_efi

    if (candidate / "EFI").exists():
        src_efi_core = candidate / "EFI"
    elif (candidate / "OC").exists():
        src_efi_core = candidate
    else:
        raise RuntimeError(
            "В указанной папке не найдена структура EFI (EFI/OC). Выберите папку "
            "со собранной EFI (обычно содержит подпапку OC)."
        )

    # удаляем старый EFI на флешке
    old = Path(f"{letter}:\\EFI")
    backup_path: Optional[Path] = None
    if old.exists():
        import shutil
        if backup:
            backup_path = backup_efi(old, backup_root)
            _log(f"Резервная копия старой EFI: {backup_path}")
        else:
            _log("Старая EFI будет удалена без резервной копии")
        shutil.rmtree(str(old))
        _log(f"Удалена старая EFI на {letter}:\\EFI")

    # копируем всё содержимое EFI
    import shutil
    for item in src_efi_core.iterdir():
        dst = Path(f"{letter}:\\") / item.name
        if item.is_dir():
            shutil.copytree(str(item), str(dst), dirs_exist_ok=True)
        else:
            shutil.copy2(str(item), str(dst))
        _log(f"  {item.name} → {letter}:\\")

    _log("EFI записана на флешку.")
    return backup_path


def write_efi_to_usb(source_efi: Path, device: str, skip_format: bool = False,
                     recovery_macos: str = "", log=None,
                     backup: bool = True,
                     backup_root: Optional[Path] = None) -> USBWriteResult:
    """Полный цикл: (опц.) форматирование + запись EFI + возврат буквы.

    Если задан recovery_macos (напр. "macOS Sonoma") — дополнительно скачивает
    macOS recovery и раскладывает com.apple.recovery.boot (полноценный установщик).
    Перед перезаписью существующей EFI на флешке делается резервная копия
    (``backup=True``); путь к ней возвращается в ``USBWriteResult.backup_path``.
    """
    res = USBWriteResult(ok=False, log=[])
    if log:
        res.log = log
    try:
        if skip_format:
            letter = device.rstrip(":\\").upper()
            if letter.startswith("RAWDISK"):
                raise RuntimeError(
                    "У этой флешки нет файловой системы (RAW). Используйте "
                    "«Полную запись», чтобы HackicLab отформатировал её."
                )
            # проверка доступности
            if not os.path.exists(f"{letter}:\\"):
                raise RuntimeError(
                    f"{letter}: недоступна — возможно, флешка RAW. Отформатируйте её "
                    f"в FAT32 вручную или выберите «Полную запись»."
                )
            target_letter = f"{letter}:"
        else:
            if log:
                log("Форматирую флешку (GPT + FAT32 + ESP)…")
            target_letter = format_usb(device)
            if log:
                log(f"Флешка отформатирована: {target_letter}")

        backup_path = copy_efi(source_efi, target_letter, log=log,
                               backup=backup, backup_root=backup_root)
        if backup_path:
            res.backup_path = str(backup_path)
            if log:
                log(f"Резервная копия старой EFI: {backup_path}")

        recovery_msg = ""
        if recovery_macos:
            recovery_msg = install_recovery_layer(target_letter, recovery_macos, log=log)

        if log:
            log("Готово. Флешка записана и отключена безопасно.")
        res.ok = True
        res.target_letter = target_letter
        res.log = log if log else []
        if recovery_msg:
            res.target_letter += f" | {recovery_msg}"
        return res
    except Exception as e:
        res.error = str(e)
        res.ok = False
        if log:
            log(f"ОШИБКА: {e}")
        return res


def install_recovery_layer(target_letter: str, macos_name: str, log=None) -> str:
    """Скачивает macOS recovery и раскладывает com.apple.recovery.boot на флешку.

    Используется для полноценного установщика (как в hackmate). Возвращает сообщение.
    """
    def _log(msg):
        if log:
            log(msg)

    from .recovery import macos_version_by_name, download_recovery

    if macos_name is None or not str(macos_name).strip():
        macos_name = "macOS Sonoma"
    version = macos_version_by_name(str(macos_name))
    if version is None:
        # иначе берём последнюю поддерживаемую
        version = macos_version_by_name("macOS Sonoma")

    letter = target_letter.rstrip(":\\")
    dst_root = Path(f"{letter}:\\")
    if not dst_root.exists():
        raise RuntimeError(f"Флешка {letter}: недоступна.")

    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="hackiclab_recovery_"))
    try:
        _log(f"Скачиваю macOS recovery ({version.name})… может занять время.")
        ok, msg = download_recovery(version, tmp, progress_cb=_log)
        if not ok:
            raise RuntimeError(msg)
        _log(msg)

        # кладём в com.apple.recovery.boot в корень флешки
        boot_dir = dst_root / "com.apple.recovery.boot"
        if boot_dir.exists():
            shutil.rmtree(str(boot_dir))
        boot_dir.mkdir(parents=True, exist_ok=True)
        copied = 0
        for f in tmp.iterdir():
            if f.is_file():
                shutil.copy2(str(f), str(boot_dir / f.name))
                copied += 1
                _log(f"  {f.name} → com.apple.recovery.boot/")
        _log(f"Recovery установлена на флешку ({copied} файл(ов)).")
        return f"recovery: {version.name} ({copied} файлов)"
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)