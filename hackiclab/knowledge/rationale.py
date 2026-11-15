"""Объяснение решений сборки.

Для каждой настройки, которую реально выставляет генератор config.plist,
даёт причину простым языком и ссылку на документацию Dortania. Источник
истины — сам сгенерированный конфиг, поэтому объяснения не расходятся
с тем, что попадает в EFI.

Тексты двуязычные: ``lang="ru"`` или ``lang="en"``.
"""

from __future__ import annotations

import plistlib
from dataclasses import dataclass
from typing import Optional

from ..scanner.models import HardwareProfile
from .kexts import KEXT_DB, select_kexts, smbios_model_for
from ..builder.config_gen import BuildOptions, generate_config_plist

GUIDE = "https://dortania.github.io/OpenCore-Install-Guide/"
CONFIG_DOC = GUIDE + "config.plist/"
ACPI_DOC = "https://dortania.github.io/Getting-Started-With-ACPI/"
AMD_GUIDE = GUIDE + "AMD/"

_R: dict[str, dict[str, str]] = {
    "ru": {
        "on": "вкл", "off": "выкл",
        "smbios.desktop_no_igpu":
            "Десктоп без рабочей iGPU: ближайшая Mac-модель с нужным board-id "
            "и управлением питанием CPU.",
        "smbios.laptop":
            "Ноутбук: модель с подходящим управлением питанием и подсветкой экрана.",
        "smbios.desktop_igpu":
            "Десктоп с iGPU: совпадает по графике и платформе, даёт рабочий framebuffer.",
        "sb.default":
            "SecureBootModel=Default не привязан к конкретной модели SMBIOS "
            "и проходит ocvalidate.",
        "sb.j160":
            "Big Sur и старше требуют конкретную модель Secure Boot (j160).",
        "acpi.SSDT-PLUG": "Управление питанием CPU через X86PlatformPlugin.",
        "acpi.SSDT-EC": "Заглушка EC-устройства, которое macOS ожидает на десктопных платах.",
        "acpi.SSDT-EC-USBX": "Заглушка EC и свойства питания USB (USBX) для ноутбуков.",
        "acpi.SSDT-PNLF": "Устройство управления подсветкой встроенного экрана.",
        "acpi.SSDT-USBX": "Свойства питания USB (USBX) для Skylake и новее.",
        "acpi.generic": "Таблица ACPI из матрицы Dortania для этой платформы.",
        "kext.generic": "Требуется для этого железа.",
        "kernel.ProvideCurrentCpuInfo":
            "На AMD ядро должно получать реальные данные CPU для патчей и XCPM.",
        "kernel.DisableIoMapper":
            "Таблица DMAR не вырезана — IOMapper отключается на стороне macOS.",
        "kernel.DisableLinkeditJettison":
            "Lilu и плагины остаются резидентными без lilubetaall.",
        "kernel.PowerTimeoutKernelPanic":
            "Big Sur+ паникует, если драйвер пропускает срок смены питания.",
        "kernel.ThirdPartyDrives":
            "Корректная работа сторонних SSD (TRIM, иконки).",
        "booter.AvoidRuntimeDefrag":
            "Runtime-сервисы прошивки продолжают работать под macOS.",
        "booter.SetupVirtualMap":
            "SetVirtualAddresses отображается в безопасную память.",
        "booter.ProvideCustomSlide":
            "Безопасный kernel slide, когда прошивка оставляет дыры в памяти.",
        "booter.EnableWriteUnprotector":
            "Снимает защиту записи таблиц страниц на старом firmware.",
        "booter.FixupAppleEfiImages":
            "Исправляет EFI-образы с неверными правами доступа.",
        "bootargs.verbose":
            "Диагностика первой загрузки: подробный лог и символы паники.",
        "sip.enabled": "SIP включён: полная защита системы.",
        "sip.weakened":
            "SIP ослаблен (0x{value:X}): разрешены неподписанные kexts и правка NVRAM.",
        "igpu.headless":
            "Безмониторный framebuffer: вывод идёт через поддерживаемую AMD dGPU.",
        "igpu.display":
            "Framebuffer для {gpu} на встроенной графике.",
    },
    "en": {
        "on": "on", "off": "off",
        "smbios.desktop_no_igpu":
            "Desktop without a working iGPU: the closest Mac with the right board-id "
            "and CPU power management.",
        "smbios.laptop":
            "Laptop: a model with matching power management and backlight.",
        "smbios.desktop_igpu":
            "Desktop with an iGPU: matches the graphics and platform, gives a working framebuffer.",
        "sb.default":
            "SecureBootModel=Default is not tied to a specific SMBIOS model "
            "and passes ocvalidate.",
        "sb.j160":
            "Big Sur and older need a concrete Secure Boot model (j160).",
        "acpi.SSDT-PLUG": "CPU power management via X86PlatformPlugin.",
        "acpi.SSDT-EC": "Stub EC device that macOS expects on desktop boards.",
        "acpi.SSDT-EC-USBX": "Stub EC plus USB power properties (USBX) for laptops.",
        "acpi.SSDT-PNLF": "Backlight control device for the internal panel.",
        "acpi.SSDT-USBX": "USB power properties (USBX) for Skylake and newer.",
        "acpi.generic": "ACPI table from the Dortania matrix for this platform.",
        "kext.generic": "Required by this hardware configuration.",
        "kernel.ProvideCurrentCpuInfo":
            "On AMD the kernel must receive real CPU data for the patches and XCPM.",
        "kernel.DisableIoMapper":
            "The DMAR table is not stripped — IOMapper is disabled from the macOS side.",
        "kernel.DisableLinkeditJettison":
            "Keeps Lilu and its plugins resident without lilubetaall.",
        "kernel.PowerTimeoutKernelPanic":
            "Big Sur+ panics when a driver misses a power-change deadline.",
        "kernel.ThirdPartyDrives":
            "Correct handling of third-party SSDs (TRIM, icons).",
        "booter.AvoidRuntimeDefrag":
            "Firmware runtime services keep working under macOS.",
        "booter.SetupVirtualMap":
            "Maps SetVirtualAddresses calls into safe memory.",
        "booter.ProvideCustomSlide":
            "Picks a safe kernel slide when the firmware leaves memory gaps.",
        "booter.EnableWriteUnprotector":
            "Removes page-table write protection on older firmware.",
        "booter.FixupAppleEfiImages":
            "Fixes EFI images that carry wrong memory permissions.",
        "bootargs.verbose":
            "First-boot diagnostics: verbose log and panic symbols.",
        "sip.enabled": "SIP is on: full system protection.",
        "sip.weakened":
            "SIP is weakened (0x{value:X}): unsigned kexts and NVRAM edits allowed.",
        "igpu.headless":
            "Connectorless framebuffer: display output goes through the supported AMD dGPU.",
        "igpu.display":
            "Framebuffer for {gpu} on the integrated GPU.",
    },
}


def _r(lang: str, key: str, **kw) -> str:
    text = _R.get(lang, _R["ru"]).get(key) or _R["ru"].get(key) or key
    try:
        return text.format(**kw) if kw else text
    except (KeyError, IndexError):
        return text


@dataclass(frozen=True)
class Decision:
    """Одно объяснённое решение сборки."""
    section: str
    setting: str
    value: str
    reason: str
    doc: str = ""


def _hex_le(raw: bytes) -> str:
    """bytes -> 0x… в порядке байтов, как принято в OpenCore."""
    if not raw:
        return "—"
    value = int.from_bytes(raw[:4].ljust(4, b"\x00"), "little")
    return f"0x{value:X}" if value <= 0xFFFF else f"0x{value:08X}"


def _flag(value, lang: str) -> str:
    if isinstance(value, bool):
        return _r(lang, "on" if value else "off")
    return str(value)


def _section(cfg: dict, name: str) -> dict:
    data = cfg.get(name, {})
    return data if isinstance(data, dict) else {}


def _smbios_decision(profile: HardwareProfile, model: str, lang: str) -> list[Decision]:
    if not model:
        return []
    if profile.platform == "laptop":
        key = "smbios.laptop"
    elif profile.dgpu and profile.dgpu.vendor == "amd" and not (
            profile.igpu and profile.igpu.vendor == "intel"):
        key = "smbios.desktop_no_igpu"
    else:
        key = "smbios.desktop_igpu"
    return [Decision("SMBIOS", "SystemProductName", model, _r(lang, key),
                     CONFIG_DOC + "#platforminfo")]


def _acpi_decisions(cfg: dict, lang: str) -> list[Decision]:
    out: list[Decision] = []
    for entry in _section(cfg, "ACPI").get("Add", []) or []:
        if not isinstance(entry, dict) or not entry.get("Enabled"):
            continue
        name = (entry.get("Path") or "").replace(".aml", "")
        if not name:
            continue
        key = f"acpi.{name}"
        out.append(Decision("ACPI", name, "added", _r(lang, key), ACPI_DOC))
    return out


def _kext_decisions(profile: HardwareProfile, options: BuildOptions,
                    lang: str) -> list[Decision]:
    out: list[Decision] = []
    for entry in select_kexts(profile, options.wifi_kext_mode):
        reason = entry.note if (lang == "ru" and entry.note) else _r(lang, "kext.generic")
        out.append(Decision("Kexts", entry.name, "included", reason, GUIDE))
    return out


def _quirk_decisions(cfg: dict, lang: str) -> list[Decision]:
    out: list[Decision] = []
    for quirk, value in (_section(cfg, "Kernel").get("Quirks") or {}).items():
        key = f"kernel.{quirk}"
        if value and key in _R["ru"]:
            out.append(Decision("Kernel", f"Quirks/{quirk}", _flag(value, lang),
                                _r(lang, key), CONFIG_DOC + "#kernel"))
    for quirk, value in (_section(cfg, "Booter").get("Quirks") or {}).items():
        key = f"booter.{quirk}"
        if value and key in _R["ru"]:
            out.append(Decision("Booter", f"Quirks/{quirk}", _flag(value, lang),
                                _r(lang, key), CONFIG_DOC + "#booter"))
    return out


def _bootarg_decisions(cfg: dict, lang: str) -> list[Decision]:
    nvram = _section(cfg, "NVRAM").get("Add", {}) or {}
    section = nvram.get("7C436110-AB2A-4BBB-A880-FE41995C9F82", {}) or {}
    args = section.get("boot-args") or ""
    if isinstance(args, bytes):
        args = args.decode("utf-8", "replace")
    out: list[Decision] = []
    if args:
        reason = _r(lang, "bootargs.verbose")
        out.append(Decision("boot-args", "boot-args", str(args), reason,
                            CONFIG_DOC + "#nvram"))
    csr = section.get("csr-active-config")
    if isinstance(csr, bytes):
        value = int.from_bytes(csr[:4].ljust(4, b"\x00"), "little")
        if value == 0:
            out.append(Decision("SIP", "csr-active-config", "0x0",
                                _r(lang, "sip.enabled"), CONFIG_DOC + "#nvram"))
        else:
            out.append(Decision("SIP", "csr-active-config", f"0x{value:X}",
                                _r(lang, "sip.weakened", value=value),
                                CONFIG_DOC + "#nvram"))
    return out


def _secureboot_decision(cfg: dict, lang: str) -> list[Decision]:
    model = _section(cfg, "Misc").get("Security", {}).get("SecureBootModel", "")
    if not model:
        return []
    key = "sb.default" if model == "Default" else "sb.j160"
    return [Decision("Misc", "SecureBootModel", str(model), _r(lang, key),
                     CONFIG_DOC + "#misc")]


def _igpu_decisions(cfg: dict, profile: HardwareProfile, lang: str) -> list[Decision]:
    add = _section(cfg, "DeviceProperties").get("Add", {}) or {}
    props = add.get("PciRoot(0x0)/Pci(0x2,0x0)")
    if not isinstance(props, dict) or "AAPL,ig-platform-id" not in props:
        return []
    headless = bool(profile.dgpu and profile.dgpu.vendor == "amd")
    reason_key = "igpu.headless" if headless else "igpu.display"
    gpu_name = (profile.igpu.name if profile.igpu else "") or "iGPU"
    return [Decision("DeviceProperties", "AAPL,ig-platform-id",
                     _hex_le(props["AAPL,ig-platform-id"]),
                     _r(lang, reason_key, gpu=gpu_name),
                     CONFIG_DOC + "#deviceproperties")]


def explain(profile: HardwareProfile, options: Optional[BuildOptions] = None,
            smbios=None, lang: str = "ru") -> list[Decision]:
    """Собирает объяснения по реально сгенерированному config.plist.

    ``smbios`` — объект SMBIOSData из сборки (если есть), иначе модель
    подбирается тем же правилом, что и в BuildPlan.
    """
    options = options or BuildOptions()
    try:
        cfg = plistlib.loads(generate_config_plist(profile, options))
    except Exception:
        return []
    model = getattr(smbios, "model", "") or None
    if not model:
        model = smbios_model_for(profile, options.target_macos)

    decisions: list[Decision] = []
    decisions += _smbios_decision(profile, model, lang)
    decisions += _secureboot_decision(cfg, lang)
    decisions += _acpi_decisions(cfg, lang)
    decisions += _kext_decisions(profile, options, lang)
    decisions += _quirk_decisions(cfg, lang)
    decisions += _bootarg_decisions(cfg, lang)
    decisions += _igpu_decisions(cfg, profile, lang)
    return decisions


_SECTION_ORDER = ["SMBIOS", "Misc", "ACPI", "Kexts", "Kernel", "Booter",
                  "boot-args", "SIP", "DeviceProperties"]


def render(decisions: list[Decision]) -> str:
    """Читаемый текст: разделы, настройки, причины, ссылки.

    Причины уже локализованы в :func:`explain` (параметр ``lang``).
    """
    if not decisions:
        return ""
    by_section: dict[str, list[Decision]] = {}
    for d in decisions:
        by_section.setdefault(d.section, []).append(d)

    ordered = [s for s in _SECTION_ORDER if s in by_section]
    ordered += [s for s in by_section if s not in _SECTION_ORDER]

    lines: list[str] = []
    for section in ordered:
        lines.append(f"## {section}")
        for d in by_section[section]:
            head = f"- {d.setting}"
            if d.value:
                head += f" = {d.value}"
            lines.append(head)
            lines.append(f"  {d.reason}")
            if d.doc:
                lines.append(f"  {d.doc}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def to_rows(decisions: list[Decision]) -> list[dict]:
    return [
        {"section": d.section, "setting": d.setting, "value": d.value,
         "reason": d.reason, "doc": d.doc}
        for d in decisions
    ]
