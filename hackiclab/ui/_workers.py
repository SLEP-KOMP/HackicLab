"""Фоновые QThread-воркеры интерфейса.

Каждая длительная операция (скан железа, сборка EFI, запись на USB, прогон
ocvalidate, анализ файлов и т.д.) выполняется в отдельном потоке, чтобы не
блокировать интерфейс. Сигналы ``done``/``failed``/``progress`` доставляют
результат в главный поток Qt.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ..analyzer import Analyzer
from ..builder import BuildPlan, EFIBuilder
from ..scanner import Scanner


class ScanWorker(QThread):
    """Сканирование железа в фоне."""
    done = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            p = Scanner().scan()
            self.done.emit(p)
        except Exception as e:
            self.failed.emit(str(e))


class BuildWorker(QThread):
    """Сборка EFI в фоне: возвращает результат и шлёт шаги прогресса."""
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, str)

    def __init__(self, plan: BuildPlan, target: Path):
        super().__init__()
        self.plan = plan
        self.target = target

    def run(self):
        try:
            res = EFIBuilder(self.plan, on_progress=self._progress).build(self.target)
            self.done.emit(res)
        except Exception as e:
            self.failed.emit(str(e))

    def _progress(self, percent: int, message: str):
        self.progress.emit(int(percent), str(message))


class USBWriteWorker(QThread):
    """Запись EFI на флешку в фоне."""
    done = Signal(object)
    failed = Signal(str)
    signal = Signal(str)

    def __init__(self, source_efi: Path, device: str, skip_format: bool,
                 recovery_macos: str = "", drive_letter: str = "",
                 make_usb_map: bool = True):
        super().__init__()
        self.source_efi = source_efi
        self.device = device
        self.skip_format = skip_format
        self.recovery_macos = recovery_macos
        self.drive_letter = drive_letter
        self.make_usb_map = make_usb_map

    def run(self):
        try:
            from ..builder.usb_backend import write_efi_to_usb
            res = write_efi_to_usb(self.source_efi, self.device,
                                   skip_format=self.skip_format,
                                   recovery_macos=self.recovery_macos,
                                   drive_letter=self.drive_letter,
                                   make_usb_map=self.make_usb_map,
                                   log=self._log)
            self.done.emit(res)
        except Exception as e:
            self.failed.emit(str(e))

    def _log(self, msg: str):
        self.signal.emit(msg)


class ValidateWorker(QThread):
    """Прогон ocvalidate в фоне."""
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, config_path: Path):
        super().__init__()
        self.config_path = config_path

    def run(self):
        try:
            from ..builder.ocvalidate import find_ocvalidate, run_ocvalidate
            tool = find_ocvalidate()
            res = run_ocvalidate(self.config_path, ocvalidate=tool)
            res_dict = {
                "ok": res.ok,
                "warnings": res.warnings,
                "errors": res.errors,
                "missing_keys": res.missing_keys,
                "schema_errors": res.schema_errors,
                "version_note": res.version_note,
                "tool_version": res.tool_version,
                "tool_missing": res.tool_missing,
                "full_output": res.full_output,
            }
            self.done.emit(res_dict)
        except Exception as e:
            self.failed.emit(str(e))


class AnalyzeWorker(QThread):
    """Анализ файлов в фоне."""
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, profile, folder, target_macos: str = ""):
        super().__init__()
        self.profile = profile
        self.folder = folder
        self.target_macos = target_macos

    def run(self):
        try:
            issues = Analyzer(self.profile, self.target_macos).analyze_folder(self.folder)
            self.done.emit(issues)
        except Exception as e:
            self.failed.emit(str(e))


class AuditWorker(QThread):
    """Структурный аудит EFI в фоне (kexts, ACPI, драйверы, SIP)."""
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, efi_root: Path):
        super().__init__()
        self.efi_root = efi_root

    def run(self):
        try:
            from ..analyzer.engine import audit_efi
            self.done.emit(audit_efi(self.efi_root))
        except Exception as e:
            self.failed.emit(str(e))


class UsbMapWorker(QThread):
    """Карта USB-портов: DSDT -> usbdump.exe -> plist."""
    done = Signal(object, str)
    failed = Signal(str)

    def run(self):
        import tempfile
        lines: list[str] = []

        def log(msg, level="info"):
            lines.append(f"[{level}] {msg}")

        try:
            from ..builder.usb_map import generate_auto_map
            tmp = Path(tempfile.mkdtemp(prefix="hackiclab_usbmap_"))
            # limit=None: вкладка показывает все порты, лишние пользователь
            # отключает сам — иначе порты сверх 15 исчезали бы молча.
            plist = generate_auto_map(tmp, log=log, limit=None)
            self.done.emit(plist, "\n".join(lines))
        except Exception as e:
            self.failed.emit(str(e))


class DiskMapWorker(QThread):
    """Скан дисков и загрузчиков в фоне (PowerShell, только чтение)."""
    done = Signal(str, list)
    failed = Signal(str)

    def run(self):
        try:
            from ..scanner.diskmap import (
                build_disk_tree,
                check_conflicts,
                scan_all_bootloaders,
                scan_disks,
            )
            disks = scan_disks()
            bootloaders = scan_all_bootloaders(disks)
            self.done.emit(build_disk_tree(disks, bootloaders),
                           check_conflicts(disks, bootloaders))
        except Exception as e:
            self.failed.emit(str(e))


class OCLogWorker(QThread):
    """Разбор лога OpenCore в фоне."""
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, path: Path):
        super().__init__()
        self.path = Path(path)

    def run(self):
        try:
            from ..analyzer.oc_log import parse_log_file
            self.done.emit(parse_log_file(self.path))
        except Exception as e:
            self.failed.emit(str(e))


class UsbListWorker(QThread):
    """Список USB-флешек в фоне: PowerShell не должен блокировать интерфейс."""
    done = Signal(list)
    failed = Signal(str)

    def run(self):
        try:
            from ..builder.usb_backend import get_usb_devices
            self.done.emit(get_usb_devices())
        except Exception as e:
            self.failed.emit(str(e))


class UpdateCheckWorker(QThread):
    """Проверка последнего релиза на GitHub в фоне."""
    found = Signal(object)
    up_to_date = Signal()
    failed = Signal(str)

    def run(self):
        try:
            from .. import updater
            info = updater.check_for_update()
            if info is None:
                self.up_to_date.emit()
            else:
                self.found.emit(info)
        except Exception as e:
            self.failed.emit(str(e))


class UpdateDownloadWorker(QThread):
    """Скачивание EXE обновления в фоне."""
    done = Signal(object)
    failed = Signal(object)

    def __init__(self, info):
        super().__init__()
        self.info = info

    def run(self):
        try:
            from .. import updater
            self.done.emit(updater.download_update(self.info))
        except Exception as e:
            self.failed.emit(e)
