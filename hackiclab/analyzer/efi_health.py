"""Аудит готового OpenCore EFI.

Проверяет любой EFI — включая собранный вручную, а не только наш — по данным,
которые лежат на диске: структуру, файлы OpenCore и UEFI-драйверов, kext-бандлы
и порядок их загрузки, ACPI-добавления и «осиротевшие» ренеймы, USB-маппинг,
PlatformInfo, SIP и известные конфликты квирков.

Результат — список AnalysisIssue с уровнями Severity; внешних зависимостей нет,
файлы только читаются.
"""

from __future__ import annotations

import plistlib
import re
import sys
from pathlib import Path
from typing import Any, Optional

from .models import KEXT_CONFLICTS, AnalysisIssue, Severity

_KNOWN_KEXTS: frozenset | None = None


def _known_kexts() -> frozenset:
    """Имена кекстов из базы HackicLab; импорт ленивый — модуль автономен."""
    global _KNOWN_KEXTS
    if _KNOWN_KEXTS is None:
        try:
            from ..knowledge.kexts import KEXT_DB
            _KNOWN_KEXTS = frozenset(KEXT_DB)
        except Exception:
            _KNOWN_KEXTS = frozenset()
    return _KNOWN_KEXTS

# --- Справочники -----------------------------------------------------------

#: Kexts, которые не работают без Lilu и должны грузиться после него.
LILU_DEPENDENTS: set[str] = {
    "AppleALC", "WhateverGreen", "AirportBrcmFixup", "RestrictEvents",
    "CPUFriend", "NVMeFix", "BrightnessKeys", "HibernationFixup",
    "CryptexFixup", "FeatureUnlock", "DebugEnhancer", "SMCLightSensor",
    "AppleMCEReporterDisabler", "SMCAMDProcessor",
}

#: Устаревшие/конфликтующие kexts: имя -> пояснение.
LEGACY_KEXTS: dict[str, str] = {
    "NullCPUPowerManagement": "Устарел; ломает управление питанием",
    "VoodooHDA": "Устаревший аудио-драйвер; используйте AppleALC",
    "ApplePS2SmartTouchPad": "Устарел; используйте VoodooPS2/VoodooI2C",
    "AtherosE2200Ethernet": "Нет поддержки в новых macOS",
}

#: Флаги SIP (csr-active-config), документированные Apple.
CSR_FLAGS: list[tuple[int, str]] = [
    (0x001, "разрешены неподписанные kexts"),
    (0x002, "task_for_pid"),
    (0x004, "отладка ядра"),
    (0x008, "Apple Internal"),
    (0x010, "неограниченная ФС"),
    (0x020, "dtrace без ограничений"),
    (0x040, "неограниченный NVRAM"),
    (0x080, "настройка устройств"),
    (0x100, "любой Recovery OS"),
    (0x200, "неодобренные kexts"),
    (0x400, "переопределение политики запуска"),
    (0x800, "неаутентифицированный root"),
]

#: Бандлы, которые действительно содержат карту портов.
#: USBToolBox.kext — это загрузчик, карта лежит в UTBMap/UTBDefault/USBMap.
USB_MAP_BUNDLES = ("USBMap", "UTBMap", "USBPorts", "UTBDefault")


# --- Вспомогательные функции ----------------------------------------------

def find_oc_dir(root: Path) -> Optional[Path]:
    """Находит каталог OC по корню EFI, по OC напрямую или вложенно."""
    root = Path(root)
    if root.name.lower() == "oc" and (root / "config.plist").exists():
        return root
    for candidate in (root / "OC", root / "EFI" / "OC"):
        if (candidate / "config.plist").exists():
            return candidate
    try:
        for cfg in root.glob("**/OC/config.plist"):
            return cfg.parent
    except OSError:
        pass
    return None


def _read_plist(path: Path) -> Optional[dict]:
    try:
        data = plistlib.loads(Path(path).read_bytes())
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _enabled(entry: dict) -> bool:
    """Запись включена? В OpenCore отсутствующий Enabled = выключено."""
    return bool(entry.get("Enabled", False))


def _as_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value) if value is not None else ""


def _decode_csr(raw: Any) -> tuple[int, list[str]]:
    """csr-active-config -> (число, список включённых послаблений)."""
    if isinstance(raw, bytes):
        value = int.from_bytes(raw[:4].ljust(4, b"\x00"), "little")
    elif isinstance(raw, int):
        value = raw
    else:
        value = 0
    allowed = [label for bit, label in CSR_FLAGS if value & bit]
    return value, allowed


def _acpi_names_in_aml(data: bytes) -> set[str]:
    """Имена ACPI (4 символа A-Z/0-9/_) в AML. Даёт ложные срабатывания —
    это нормально: проверка «не предупреждать лишнего», а не дизассемблер."""
    return {m.group(0).decode("ascii")
            for m in re.finditer(rb"[A-Z_][A-Z0-9_]{3}", data)}


def _defined_acpi_names(acpi_dir: Path) -> set[str]:
    names: set[str] = set()
    if not acpi_dir.is_dir():
        return names
    for aml in acpi_dir.glob("*.aml"):
        try:
            names |= _acpi_names_in_aml(aml.read_bytes())
        except OSError:
            continue
    return names


def _driver_names(cfg: dict) -> list[str]:
    """UEFI/Drivers: поддерживает и строки (OC 0.7.3+), и словари."""
    out: list[str] = []
    for item in cfg.get("UEFI", {}).get("Drivers", []) or []:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict) and _enabled(item):
            path = item.get("Path") or ""
            if path:
                out.append(path)
    return out


def _kext_entries(cfg: dict) -> list[dict]:
    return [e for e in (cfg.get("Kernel", {}).get("Add", []) or [])
            if isinstance(e, dict) and _enabled(e)]


def _blocked_bundles(cfg: dict) -> set[str]:
    """Kernel/Block: идентификаторы, которые сборка реально блокирует."""
    return {str(e.get("Identifier") or "")
            for e in (cfg.get("Kernel", {}).get("Block", []) or [])
            if isinstance(e, dict) and _enabled(e)}


# --- Отдельные проверки ----------------------------------------------------

def _check_structure(oc: Path, issues: list[AnalysisIssue]) -> None:
    efi = oc.parent
    if not (oc / "OpenCore.efi").exists():
        issues.append(AnalysisIssue(
            Severity.ERROR, "efi_no_opencore",
            "Отсутствует OpenCore.efi",
            f"Файл не найден: {oc / 'OpenCore.efi'}",
            suggestion="Переустановите OpenCore или укажите другой EFI."))
    boot = efi / "BOOT" / "BOOTx64.efi"
    if not boot.exists():
        issues.append(AnalysisIssue(
            Severity.WARNING, "efi_no_bootx64",
            "Отсутствует BOOT/BOOTx64.efi",
            "Без него прошивка не найдёт загрузчик в режиме по умолчанию.",
            suggestion="Скопируйте BOOTx64.efi из OpenCorePkg."))


def _check_drivers(oc: Path, cfg: dict, issues: list[AnalysisIssue]) -> None:
    drivers_dir = oc / "Drivers"
    names = _driver_names(cfg)
    for name in names:
        if not (drivers_dir / name).exists():
            issues.append(AnalysisIssue(
                Severity.ERROR, "driver_missing",
                f"Драйвер не найден: {name}",
                f"В config.plist указан {name}, но файла нет в OC/Drivers.",
                suggestion="Скачайте файл драйвера или уберите запись из UEFI/Drivers."))
    lowered = {n.lower() for n in names}
    if "openruntime.efi" not in lowered:
        issues.append(AnalysisIssue(
            Severity.ERROR, "driver_openruntime",
            "Не подключён OpenRuntime.efi",
            "Без OpenRuntime не работают квирки Booter и NVRAM.",
            suggestion="Добавьте OpenRuntime.efi в UEFI/Drivers и в OC/Drivers."))
    if "hfsplus.efi" not in lowered and "openhfsplus.efi" not in lowered:
        issues.append(AnalysisIssue(
            Severity.WARNING, "driver_hfs",
            "Нет HFS+-драйвера",
            "Без HFSPlus/OpenHfsPlus macOS не увидит HFS-разделы.",
            suggestion="Добавьте HfsPlus.efi (или OpenHfsPlus.efi)."))


def _check_acpi(oc: Path, cfg: dict, issues: list[AnalysisIssue]) -> None:
    acpi_dir = oc / "ACPI"
    for entry in cfg.get("ACPI", {}).get("Add", []) or []:
        if not isinstance(entry, dict) or not _enabled(entry):
            continue
        path = entry.get("Path") or ""
        if path and not (acpi_dir / path).exists():
            issues.append(AnalysisIssue(
                Severity.ERROR, "acpi_file_missing",
                f"ACPI-файл не найден: {path}",
                "Запись включена в config.plist, но таблицы нет в OC/ACPI.",
                suggestion="Скачайте таблицу или отключите запись."))

    defined = _defined_acpi_names(acpi_dir)
    if not defined:
        return
    for patch in cfg.get("ACPI", {}).get("Patch", []) or []:
        if not isinstance(patch, dict) or not _enabled(patch):
            continue
        find, replace = patch.get("Find"), patch.get("Replace")
        if not isinstance(find, bytes) or not isinstance(replace, bytes):
            continue
        if len(find) != 4 or len(replace) != 4:
            continue
        target = replace.decode("ascii", "ignore")
        if not re.fullmatch(r"[A-Z_][A-Z0-9_]{3}", target or ""):
            continue
        if target in defined:
            continue
        # Сам по себе отсутствующий target — норма: ренейм освобождает имя,
        # чтобы SSDT объявил исходное (_CRS → XCRS + SSDT-HPET с новым _CRS,
        # _OSI → XOSI + SSDT-XOSI, _PRW → XPRW + SSDT-GPRW). Предупреждаем
        # только если ни одна таблица в OC/ACPI не объявляет исходное имя —
        # тогда патч действительно ни на что не влияет.
        original = find.decode("ascii", "ignore")
        if re.fullmatch(r"[A-Z_][A-Z0-9_]{3}", original or "") and original in defined:
            continue
        issues.append(AnalysisIssue(
            Severity.WARNING, "acpi_orphan_rename",
            f"Осиротевший ACPI-ренейм: {target}",
            f"Патч «{_as_text(patch.get('Comment')) or target}» заменяет "
            f"{original or 'имя'} на {target}, но ни одна таблица OC/ACPI "
            f"не объявляет ни {original}, ни {target}.",
            suggestion="Добавьте SSDT с этим именем или отключите патч."))


def _check_kexts(oc: Path, cfg: dict, issues: list[AnalysisIssue]) -> None:
    kext_dir = oc / "Kexts"
    entries = _kext_entries(cfg)
    order: list[str] = []
    for entry in entries:
        bundle = entry.get("BundlePath") or ""
        if not bundle:
            continue
        stem = Path(bundle).stem
        order.append(stem)
        bundle_path = kext_dir / bundle
        if not bundle_path.exists():
            issues.append(AnalysisIssue(
                Severity.ERROR, "kext_bundle_missing",
                f"kext не найден: {stem}",
                f"В config.plist указан {bundle}, но папки нет в OC/Kexts.",
                kext=stem,
                suggestion="Скачайте kext заново или отключите запись."))
            continue
        exe = entry.get("ExecutablePath") or ""
        if exe and not (bundle_path / exe).exists():
            issues.append(AnalysisIssue(
                Severity.ERROR, "kext_exec_missing",
                f"Нет исполняемого файла: {stem}",
                f"{bundle}/{exe} отсутствует — kext не загрузится.",
                kext=stem,
                suggestion="Бандл повреждён: перекачайте kext."))
        if stem in LEGACY_KEXTS:
            issues.append(AnalysisIssue(
                Severity.WARNING, "kext_legacy",
                f"Устаревший kext: {stem}",
                LEGACY_KEXTS[stem],
                kext=stem,
                suggestion="Уберите его или замените современным аналогом."))

    names = set(order)
    if "Lilu" not in names:
        deps = sorted(names & LILU_DEPENDENTS)
        if deps:
            issues.append(AnalysisIssue(
                Severity.ERROR, "lilu_missing",
                "Отсутствует Lilu",
                "Без Lilu не загрузятся: " + ", ".join(deps),
                suggestion="Добавьте Lilu.kext первым в Kernel/Add."))
    else:
        idx = order.index("Lilu")
        for dep in sorted(names & LILU_DEPENDENTS):
            if order.index(dep) < idx:
                issues.append(AnalysisIssue(
                    Severity.WARNING, "lilu_order",
                    f"Порядок загрузки: {dep} раньше Lilu",
                    "Плагины Lilu должны грузиться после него.",
                    kext=dep,
                    suggestion="Переместите Lilu.kext выше в Kernel/Add."))

    if "FakeSMC" in names and "VirtualSMC" in names:
        issues.append(AnalysisIssue(
            Severity.ERROR, "smc_conflict",
            "Конфликт SMC: FakeSMC и VirtualSMC одновременно",
            "Два эмулятора SMC несовместимы.",
            suggestion="Оставьте только VirtualSMC (или только FakeSMC)."))

    for first, second, note in KEXT_CONFLICTS:
        if (first, second) == ("VirtualSMC", "FakeSMC"):
            continue  # про SMC уже сказано выше, не дублируем
        if first in names and second in names:
            issues.append(AnalysisIssue(
                Severity.ERROR, f"kext_conflict_{first.lower()}_{second.lower()}",
                f"Конфликт кекстов: {first} и {second}",
                note,
                kext=second,
                suggestion=f"Уберите {second}.kext из OC/Kexts и запись "
                           f"из Kernel/Add — иначе один из двух не загрузится."))

    if ("IO80211FamilyLegacy" in names
            and "com.apple.iokit.IOSkywalkFamily" not in _blocked_bundles(cfg)):
        issues.append(AnalysisIssue(
            Severity.WARNING, "ioskywalk_not_blocked",
            "Broadcom Wi-Fi: IOSkywalkFamily не заблокирован",
            "IO80211FamilyLegacy не поднимется, пока штатный "
            "com.apple.iokit.IOSkywalkFamily грузится из системы: в Kernel/Block "
            "нужна запись Strategy=Exclude, MinKernel=23.0.0. Сами кексты "
            "Wi-Fi не возвращают — ещё нужен root patch OCLP.",
            kext="IOSkywalkFamily",
            suggestion="Добавьте блок IOSkywalkFamily и примените root patch OCLP."))

    # Кексты вне нашей базы: они могут быть нужны (VoodooRMI, Sinetek-rtsx
    # для картридера), поэтому это не ошибка — просто совет на будущее, чтобы
    # при пересборке в HackicLab не потерять то, что автор подобрал руками.
    # UTBMap/USBMap — наша же карта портов, её в базе кекстов нет намеренно.
    outside = sorted(stem for stem in names
                     if stem not in _known_kexts()
                     and stem not in USB_MAP_BUNDLES
                     and not stem.startswith("."))
    if outside:
        issues.append(AnalysisIssue(
            Severity.INFO, "kexts_outside_db",
            f"Кексты вне базы HackicLab: {len(outside)}",
            ", ".join(outside[:8]) + ("…" if len(outside) > 8 else ""),
            suggestion="При пересборке они не добавятся автоматически: "
                       "перенесите их в свой EFI вручную."))


def _check_usb_map(oc: Path, issues: list[AnalysisIssue]) -> None:
    kext_dir = oc / "Kexts"
    if not kext_dir.is_dir():
        return
    for name in USB_MAP_BUNDLES:
        for bundle in kext_dir.glob(f"{name}*.kext"):
            info = _read_plist(bundle / "Contents" / "Info.plist")
            if info is None:
                continue
            personalities = info.get("IOKitPersonalities") or {}
            if not personalities:
                issues.append(AnalysisIssue(
                    Severity.WARNING, "usbmap_empty",
                    f"USB-маппинг пуст: {bundle.stem}",
                    "В Info.plist нет IOKitPersonalities — порты не заданы.",
                    suggestion="Пересоберите маппинг в USBToolBox для этого железа."))
                continue
            ports = 0
            for personality in personalities.values():
                if not isinstance(personality, dict):
                    continue
                merge = personality.get("IOProviderMergeProperties") or {}
                if isinstance(merge, dict):
                    ports += len(merge.get("ports") or {})
                ports += len(personality.get("ports") or {})
            if ports:
                continue
            if bundle.stem.startswith("UTBDefault"):
                issues.append(AnalysisIssue(
                    Severity.INFO, "usbmap_generic",
                    f"USB: генерическая карта {bundle.stem}",
                    "Порты не перечислены — раскрываются все порты контроллера. "
                    "Для ноутбуков и >15 портов лучше собрать карту под своё железо.",
                    suggestion="При проблемах с USB соберите карту в USBToolBox."))
                continue
            issues.append(AnalysisIssue(
                Severity.WARNING, "usbmap_no_ports",
                f"USB-маппинг без портов: {bundle.stem}",
                "Персоналии есть, но ни один порт не описан.",
                suggestion="Проверьте маппинг в USBToolBox."))


def _check_platform_info(cfg: dict, issues: list[AnalysisIssue]) -> None:
    info = cfg.get("PlatformInfo", {}) or {}
    if not isinstance(info, dict):
        return
    generic = info.get("Generic", {}) or {}
    if not isinstance(generic, dict):
        return
    required = {
        "SystemProductName": "SMBIOS-модель",
        "SystemSerialNumber": "серийный номер",
        "MLB": "MLB (board serial)",
        "SystemUUID": "SystemUUID",
    }
    empty = [label for key, label in required.items()
             if not _as_text(generic.get(key)).strip()]
    if not empty:
        return
    # OpenCore c Automatic=true и UpdateSMBIOSMode Create/Minimal сам
    # сгенерирует серийник и UUID: в конфиге их держат пустыми нарочно,
    # чтобы не переносить чужие серийники. Это не ошибка сборки.
    automatic = bool(info.get("Automatic"))
    mode = _as_text(info.get("UpdateSMBIOSMode")).strip()
    if automatic and mode.lower() != "custom" and not _as_text(
            generic.get("SystemProductName")).strip():
        issues.append(AnalysisIssue(
            Severity.WARNING, "platforminfo_incomplete",
            "PlatformInfo заполнен не полностью",
            "Не указана SMBIOS-модель (SystemProductName).",
            suggestion="Выберите модель: iMac19,1 для Intel, MacPro7,1 для AMD."))
        return
    if automatic and mode.lower() != "custom":
        issues.append(AnalysisIssue(
            Severity.INFO, "platforminfo_generated",
            "Серийник и UUID генерирует OpenCore",
            f"Automatic=true, UpdateSMBIOSMode={mode or 'Create'}: пусто "
            f"({', '.join(empty)}). Так делают, чтобы не брать чужие серийники.",
            suggestion="Сгенерируйте свои через GenSMBIOS, если нужен iMessage."))
        return
    issues.append(AnalysisIssue(
        Severity.WARNING, "platforminfo_incomplete",
        "PlatformInfo заполнен не полностью",
        "Пусто: " + ", ".join(empty),
        suggestion="Сгенерируйте SMBIOS заново (кнопка сборки или GenSMBIOS)."))


def _check_sip(cfg: dict, issues: list[AnalysisIssue]) -> None:
    nvram = cfg.get("NVRAM", {}).get("Add", {}) or {}
    section = nvram.get("7C436110-AB2A-4BBB-A880-FE41995C9F82", {}) or {}
    raw = section.get("csr-active-config")
    if raw is None:
        issues.append(AnalysisIssue(
            Severity.INFO, "sip_undefined",
            "SIP: csr-active-config не задан",
            "Будет использовано значение по умолчанию (SIP включён)."))
        return
    value, allowed = _decode_csr(raw)
    if value == 0:
        issues.append(AnalysisIssue(
            Severity.INFO, "sip_enabled",
            "SIP включён (csr-active-config = 0x0)",
            "Полная защита системы. Для установки сторонних kext обычно нужен 0x67."))
        return
    if len(allowed) >= 8:
        issues.append(AnalysisIssue(
            Severity.WARNING, "sip_wide_open",
            f"SIP почти полностью отключён (0x{value:X})",
            "Включено: " + "; ".join(allowed),
            suggestion="Оставьте только необходимые послабления (обычно 0x67)."))
        return
    issues.append(AnalysisIssue(
        Severity.INFO, "sip_partial",
        f"SIP: частично отключён (0x{value:X})",
        "Разрешено: " + "; ".join(allowed)))


def _check_boot_args(cfg: dict, issues: list[AnalysisIssue]) -> None:
    nvram = cfg.get("NVRAM", {}).get("Add", {}) or {}
    section = nvram.get("7C436110-AB2A-4BBB-A880-FE41995C9F82", {}) or {}
    args = _as_text(section.get("boot-args") or "").strip()
    if not args:
        issues.append(AnalysisIssue(
            Severity.INFO, "boot_args_empty",
            "boot-args пуст",
            "Для первой загрузки полезно: -v debug=0x100 keepsyms=1",
            suggestion="Добавьте -v для диагностики в случае проблем."))
        return
    if "-v" not in args:
        issues.append(AnalysisIssue(
            Severity.INFO, "boot_args_quiet",
            "boot-args без -v",
            f"Текущие: {args}. При отладке добавьте -v."))


def _check_quirks(cfg: dict, issues: list[AnalysisIssue]) -> None:
    kernel = cfg.get("Kernel", {}).get("Quirks", {}) or {}
    if kernel.get("EnableWriteUnprotector") and kernel.get("RebuildAppleMemoryMap"):
        issues.append(AnalysisIssue(
            Severity.WARNING, "quirk_conflict",
            "Конфликт квирков: EnableWriteUnprotector + RebuildAppleMemoryMap",
            "Оба одновременно не рекомендуются: RebuildAppleMemoryMap их заменяет.",
            suggestion="Оставьте RebuildAppleMemoryMap, EnableWriteUnprotector выключите."))


# --- Публичный API ---------------------------------------------------------

def _clover_dir(root: Path) -> Optional[Path]:
    """Папка Clover внутри EFI, если OpenCore нет."""
    for name in ("CLOVER", "Clover"):
        cand = root / name
        if (cand / "config.plist").exists():
            return cand
    for cfg in root.glob("**/CLOVER/config.plist"):
        return cfg.parent
    return None


def _audit_clover(clover: Path) -> list[AnalysisIssue]:
    """Разбор Clover EFI: что там есть и почему нужен переход на OpenCore."""
    issues: list[AnalysisIssue] = []
    cfg = _read_plist(clover / "config.plist") or {}
    issues.append(AnalysisIssue(
        Severity.WARNING, "clover_efi",
        "Найден Clover EFI",
        "Clover не развивается и не подходит для macOS Ventura и новее: "
        "для современных систем нужен OpenCore.",
        suggestion="Соберите EFI в HackicLab под это железо и перенесите настройки."))

    smbios = (cfg.get("SMBIOS") or {}).get("ProductName") or ""
    if smbios:
        issues.append(AnalysisIssue(
            Severity.INFO, "clover_smbios", f"SMBIOS: {smbios}",
            "Проверьте, что выбранная модель поддерживает нужную macOS."))

    boot = cfg.get("Boot") if isinstance(cfg.get("Boot"), dict) else {}
    args = _as_text((boot or {}).get("Arguments"))
    if args:
        issues.append(AnalysisIssue(
            Severity.INFO, "clover_boot_args", "boot-args: " + args,
            "Перенесите нужные флаги в NVRAM → boot-args OpenCore."))

    kexts: set[str] = set()
    kext_root = clover / "kexts"
    if kext_root.exists():
        for sub in kext_root.iterdir():
            if sub.is_dir():
                kexts.update(k.stem for k in sub.glob("*.kext"))
    if kexts:
        issues.append(AnalysisIssue(
            Severity.INFO, "clover_kexts",
            f"kexts: {len(kexts)}",
            ", ".join(sorted(kexts)),
            suggestion="В OpenCore порядок загрузки задаётся в Kernel → Add."))
        for name in sorted(kexts & set(LEGACY_KEXTS)):
            issues.append(AnalysisIssue(
                Severity.WARNING, "legacy_kext", f"{name}: {LEGACY_KEXTS[name]}",
                suggestion="Замените на современный аналог."))

    drivers = sorted(p.name for p in
                     list((clover / "drivers" / "UEFI").glob("*.efi"))
                     + list((clover / "drivers64UEFI").glob("*.efi"))
                     if p.is_file())
    if drivers:
        issues.append(AnalysisIssue(
            Severity.INFO, "clover_drivers",
            f"UEFI-драйверы: {len(drivers)}", ", ".join(drivers),
            suggestion="В OpenCore обязательны OpenRuntime.efi и HfsPlus.efi."))

    acpi = sorted(p.name for p in (clover / "ACPI" / "patched").glob("*.aml")
                  if p.is_file())
    if acpi:
        issues.append(AnalysisIssue(
            Severity.INFO, "clover_acpi",
            f"ACPI-таблицы: {len(acpi)}", ", ".join(acpi),
            suggestion="Перенесите нужные SSDT в OC/ACPI и включите в config.plist."))
    return issues


def audit(efi_root: Path) -> list[AnalysisIssue]:
    """Полный аудит EFI. Возвращает список замечаний (пусто = всё в порядке)."""
    issues: list[AnalysisIssue] = []
    oc = find_oc_dir(Path(efi_root))
    if oc is None:
        clover = _clover_dir(Path(efi_root))
        if clover is not None:
            return _audit_clover(clover)
        return [AnalysisIssue(
            Severity.ERROR, "efi_structure",
            "Структура EFI/OC не найдена",
            "Укажите корень EFI (папку EFI или каталог, где лежит EFI/OC).",
            suggestion="Проверьте путь: нужен EFI/OC/config.plist.")]

    cfg = _read_plist(oc / "config.plist")
    if cfg is None:
        return [AnalysisIssue(
            Severity.ERROR, "config_unreadable",
            "config.plist не читается",
            "Файл повреждён или это не plist.",
            suggestion="Восстановите config.plist из бэкапа.")]

    _check_structure(oc, issues)
    _check_drivers(oc, cfg, issues)
    _check_acpi(oc, cfg, issues)
    _check_kexts(oc, cfg, issues)
    _check_usb_map(oc, issues)
    _check_platform_info(cfg, issues)
    _check_sip(cfg, issues)
    _check_boot_args(cfg, issues)
    _check_quirks(cfg, issues)
    _check_integrity(oc.parent, issues)
    return issues


def _check_integrity(efi_root: Path, issues: list[AnalysisIssue]) -> None:
    """Сверка с манифестом сборки: изменился ли EFI после сборки."""
    from ..builder.integrity_manifest import verify_manifest

    # Манифест лежит в корне сборки, а аудит получает EFI/OC. Пробуем оба
    # уровня, иначе собственная сборка сообщала «нет манифеста».
    report = None
    for candidate in (Path(efi_root), Path(efi_root).parent):
        report = verify_manifest(candidate)
        if report is not None:
            break
    if report is None:
        issues.append(AnalysisIssue(
            Severity.INFO, "efi_no_manifest",
            "Нет манифеста целостности",
            "EFI собран не в HackicLab или манифест удалён — сверять не с чем.",
            suggestion="Пересоберите EFI в HackicLab, чтобы включить проверку."))
        return
    if report.ok:
        extra = (f" После сборки добавлено файлов: {len(report.added)}."
                 if report.added else "")
        issues.append(AnalysisIssue(
            Severity.INFO, "efi_integrity_ok",
            f"Целостность EFI подтверждена: {report.checked} файлов",
            "sha256 совпадают с манифестом сборки." + extra))
        return
    details = []
    if report.changed:
        details.append("изменены: " + ", ".join(report.changed[:8]))
    if report.missing:
        details.append("удалены: " + ", ".join(report.missing[:8]))
    if report.added:
        details.append("добавлены: " + ", ".join(report.added[:8]))
    issues.append(AnalysisIssue(
        Severity.WARNING, "efi_integrity_changed",
        f"EFI изменён после сборки: {report.drift} файлов",
        "; ".join(details),
        suggestion="Если правили сами — пересоберите EFI; иначе проверьте, "
                   "кто и зачем менял файлы."))


def summarise(issues: list[AnalysisIssue]) -> dict[str, int]:
    """Счётчики по уровням."""
    return {
        "error": sum(1 for i in issues if i.severity == Severity.ERROR),
        "warning": sum(1 for i in issues if i.severity == Severity.WARNING),
        "info": sum(1 for i in issues if i.severity == Severity.INFO),
        "total": len(issues),
    }


def format_report(issues: list[AnalysisIssue], efi_root: Path) -> str:
    """Текстовый отчёт для сохранения рядом с EFI."""
    counts = summarise(issues)
    lines = [
        "HackicLab — аудит EFI",
        f"Путь: {efi_root}",
        f"Ошибки: {counts['error']} · Предупреждения: {counts['warning']} · "
        f"Информация: {counts['info']}",
        "",
    ]
    if not issues:
        lines.append("Замечаний нет — EFI выглядит корректным.")
        return "\n".join(lines)
    marks = {Severity.ERROR: "[ОШИБКА]", Severity.WARNING: "[ВНИМАНИЕ]",
             Severity.INFO: "[ИНФО]"}
    for issue in sorted(issues, key=lambda i: -int(i.severity)):
        lines.append(f"{marks.get(issue.severity, '[?]')} {issue.title}")
        if issue.detail:
            lines.append(f"    {issue.detail}")
        if issue.suggestion:
            lines.append(f"    → {issue.suggestion}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# --- Консольный аудит: python -m hackiclab.analyzer.efi_health <EFI> ---------

def _volume_roots() -> list[Path]:
    """Корни, где может лежать смонтированный EFI (по платформам)."""
    if sys.platform == "darwin":
        return [Path("/Volumes")]
    if sys.platform.startswith("win"):
        return [Path(f"{chr(letter)}:\\") for letter in range(ord("A"), ord("Z") + 1)]
    return [Path("/media"), Path("/mnt")]


def find_efi_candidates() -> list[Path]:
    """Тома, где есть EFI/OC (или сам том является EFI)."""
    found: list[Path] = []
    for root in _volume_roots():
        if not root.is_dir():
            continue
        try:
            volumes = list(root.iterdir())
        except (PermissionError, OSError):
            continue
        for volume in volumes:
            for efi in (volume / "EFI", volume):
                try:
                    if not efi.is_dir():
                        continue
                    children = {child.name.lower() for child in efi.iterdir() if child.is_dir()}
                except (PermissionError, OSError):
                    continue
                if "oc" in children:
                    found.append(efi)
                    break
    return found


def _usage(candidates: list[Path]) -> None:
    print("\nИспользование: python -m hackiclab.analyzer.efi_health <папка EFI>\n")
    print("  Проверяет OpenCore EFI — папку, в которой лежат OC/ и BOOT/.\n")
    if candidates:
        print("  Найдено на этом ПК:")
        for path in candidates:
            print(f"    {path}")
    else:
        print("  Смонтированный EFI не найден — сначала смонтируйте EFI-раздел.")
    print()


def main(argv: list[str] | None = None) -> int:
    """Аудит EFI из консоли. Код возврата: 0 — чисто, 1 — есть ошибки, 2 — нет цели."""
    args = [a for a in (argv if argv is not None else sys.argv[1:]) if not a.startswith("-")]
    if args:
        target = Path(args[0])
    else:
        candidates = find_efi_candidates()
        if len(candidates) != 1:
            _usage(candidates)
            return 2
        target = candidates[0]
        print(f"Проверяю единственный найденный EFI: {target}")
    if not target.is_dir():
        print(f"Не найдена папка: {target}")
        return 2
    issues = audit(target)
    print(format_report(issues, target))
    return 1 if summarise(issues)["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
