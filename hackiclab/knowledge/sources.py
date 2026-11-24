"""Каталог внешних источников и правила их релевантности железу.

Модуль не делает сетевых запросов: здесь только ссылки, которые реально
использовались при разработке правил (Dortania, AMD-OSX, репозитории
сообщества), и функция подбора подсказок под конкретный профиль.

Ссылка попадает в каталог, только если она проверена. Тексты даны на двух
языках, чтобы страница «Источники» пересобиралась вместе с остальным UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

GROUP_GUIDES = "guides"
GROUP_HARDWARE = "hardware"
GROUP_EFI = "efi"
GROUP_COMMUNITY = "community"

GROUPS: tuple[str, ...] = (
    GROUP_GUIDES, GROUP_HARDWARE, GROUP_EFI, GROUP_COMMUNITY,
)


@dataclass(frozen=True)
class Source:
    key: str
    url: str
    group: str
    title: str
    title_en: str
    note: str = ""
    note_en: str = ""


SOURCES: dict[str, Source] = {
    # --- официальные гайды OpenCore ---
    "oc_guide": Source(
        "oc_guide",
        "https://dortania.github.io/OpenCore-Install-Guide/",
        GROUP_GUIDES,
        "OpenCore Install Guide (Dortania)",
        "OpenCore Install Guide (Dortania)",
        "Основной гайд: структура EFI, config.plist, порядок установки",
        "The main guide: EFI layout, config.plist, install order",
    ),
    "mist": Source(
        "mist",
        "https://github.com/ninxsoft/Mist",
        GROUP_COMMUNITY,
        "Mist — загрузка образов macOS",
        "Mist — macOS installer downloader",
        "Альтернатива macrecovery: скачивает полные установщики macOS",
        "An alternative to macrecovery: downloads full macOS installers",
    ),
    "oc_amd": Source(
        "oc_amd",
        "https://dortania.github.io/OpenCore-Install-Guide/AMD/zen.html",
        GROUP_GUIDES,
        "Гайд для AMD Ryzen (Zen/Zen 2/Zen 3)",
        "AMD Ryzen guide (Zen/Zen 2/Zen 3)",
        "Патчи ядра AMD Vanilla, quirks и SSDT для платформы AMD",
        "AMD Vanilla kernel patches, quirks and SSDTs for AMD",
    ),
    "oc_kexts": Source(
        "oc_kexts",
        "https://dortania.github.io/OpenCore-Install-Guide/ktext.html",
        GROUP_GUIDES,
        "Кексты: что и зачем нужно",
        "Kexts: what is required and why",
        "Список обязательных и опциональных кекстов, включая сетевые",
        "Required and optional kexts, network drivers included",
    ),
    "laptop_guide": Source(
        "laptop_guide",
        "https://dortania.github.io/OpenCore-Install-Guide/config-laptop.plist/",
        GROUP_GUIDES,
        "Гайд для ноутбуков",
        "Laptop guide",
        "Тачпад, яркость, батарея, сон и патчи для мобильных платформ",
        "Touchpad, brightness, battery, sleep and mobile-platform patches",
    ),

    # --- совместимость железа ---
    "gpu_guide": Source(
        "gpu_guide",
        "https://dortania.github.io/GPU-Buyers-Guide/",
        GROUP_HARDWARE,
        "GPU Buyers Guide",
        "GPU Buyers Guide",
        "Какие видеокарты работают нативно, какие требуют патчей",
        "Which GPUs work natively and which need patches",
    ),
    "gpu_amd": Source(
        "gpu_amd",
        "https://github.com/dortania/GPU-Buyers-Guide/blob/master/modern-gpus/amd-gpu.md",
        GROUP_HARDWARE,
        "AMD GPU: таблица device-id и статусов",
        "AMD GPUs: device-id and status table",
        "Polaris, Navi и Vega: точные device-id и отметки поддержи",
        "Polaris, Navi and Vega: exact device-ids and support marks",
    ),
    "wireless_guide": Source(
        "wireless_guide",
        "https://github.com/dortania/Wireless-Buyers-Guide",
        GROUP_HARDWARE,
        "Wireless Buyers Guide",
        "Wireless Buyers Guide",
        "Wi-Fi и Bluetooth: поддерживаемые чипсеты и ограничения по версиям",
        "Wi-Fi and Bluetooth: supported chipsets and version limits",
    ),
    "anti_hackintosh_net": Source(
        "anti_hackintosh_net",
        "https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/Networking.html",
        GROUP_HARDWARE,
        "Anti-Hackintosh: проблемная сеть",
        "Anti-Hackintosh: networking",
        "Железо, с которым macOS не работает или работает плохо",
        "Hardware that macOS does not support or supports poorly",
    ),
    "appleigb": Source(
        "appleigb",
        "https://github.com/ayushere/AppleIGB",
        GROUP_HARDWARE,
        "AppleIGB: Intel I210/I211/I350",
        "AppleIGB: Intel I210/I211/I350",
        "Драйвер для I211 на Monterey и новее (IntelMausi её не покрывает)",
        "Driver for I211 on Monterey and newer (IntelMausi does not cover it)",
    ),
    "itlwm_compat": Source(
        "itlwm_compat",
        "https://openintelwireless.github.io/itlwm/Compat.html",
        GROUP_HARDWARE,
        "itlwm: список поддерживаемых Wi-Fi",
        "itlwm: supported Wi-Fi list",
        "Только Intel; MediaTek и Realtek в списке отсутствуют",
        "Intel only; MediaTek and Realtek are absent from the list",
    ),
    "oclp_wifi": Source(
        "oclp_wifi",
        "https://github.com/perez987/Fenvi-wifi-back-on-Sonoma-Sequoia-Tahoe",
        GROUP_HARDWARE,
        "Broadcom в Sonoma+: root patch OCLP",
        "Broadcom on Sonoma+: OCLP root patch",
        "BCM4360/BCM43602 потеряли поддержку в Sonoma, нужен патч OCLP",
        "BCM4360/BCM43602 lost support in Sonoma, an OCLP patch is required",
    ),

    # --- готовые EFI и примеры ---
    "efi_mikigal": Source(
        "efi_mikigal",
        "https://github.com/mikigal/ryzen-hackintosh",
        GROUP_EFI,
        "EFI: mikigal (Ryzen)",
        "EFI: mikigal (Ryzen)",
        "Рабочий пример EFI для Ryzen: сверять порядок кекстов и quirks",
        "Working Ryzen EFI example: compare kext order and quirks",
    ),
    "oclp": Source(
        "oclp",
        "https://github.com/dortania/OpenCore-Legacy-Patcher",
        GROUP_EFI,
        "OpenCore Legacy Patcher",
        "OpenCore Legacy Patcher",
        "Запуск новых macOS на снятом с поддержки железе (Ivy Bridge, Skylake, BCM4360)",
        "Running newer macOS on dropped hardware (Ivy Bridge, Skylake, BCM4360)",
    ),
    "efi_subhead": Source(
        "efi_subhead",
        "https://github.com/subhead/opencore-ryzen-macos",
        GROUP_EFI,
        "EFI: subhead (Ryzen)",
        "EFI: subhead (Ryzen)",
        "Ещё один пример сборки под AMD, включая патчи ядра",
        "Another AMD build example, kernel patches included",
    ),
    "efi_maxritz": Source(
        "efi_maxritz",
        "https://github.com/Maxritz/ryzen-hackintosh-Sequoia",
        GROUP_EFI,
        "EFI: Maxritz (Sequoia)",
        "EFI: Maxritz (Sequoia)",
        "Пример под Sequoia на Ryzen: что меняется относительно Ventura",
        "Sequoia example on Ryzen: what changes versus Ventura",
    ),

    # --- сообщество ---
    "amd_osx": Source(
        "amd_osx",
        "https://forum.amd-osx.com/",
        GROUP_COMMUNITY,
        "AMD OS X — форум",
        "AMD OS X forum",
        "Патчи AMD Vanilla и разбор ошибок загрузки на Ryzen",
        "AMD Vanilla patches and Ryzen boot failures",
    ),
    "insanelymac": Source(
        "insanelymac",
        "https://www.insanelymac.com/",
        GROUP_COMMUNITY,
        "InsanelyMac",
        "InsanelyMac",
        "Обсуждения конкретных моделей карт и адаптеров",
        "Discussions of specific card and adapter models",
    ),
    "tonymacx86": Source(
        "tonymacx86",
        "https://www.tonymacx86.com/",
        GROUP_COMMUNITY,
        "tonymacx86",
        "tonymacx86",
        "Сборки под настольные платформы Intel и AMD",
        "Desktop builds for Intel and AMD platforms",
    ),
    "rx580_2048sp": Source(
        "rx580_2048sp",
        "https://www.insanelymac.com/forum/topic/356702-getting-a-chinese-rx580-2048sp-working-on-macos",
        GROUP_COMMUNITY,
        "RX 580 2048SP: почему не заводится",
        "RX 580 2048SP: why it does not work",
        "Подмена device-id на 67DF не даёт ускорения, помогает прошивка VBIOS",
        "Spoofing device-id to 67DF gives no acceleration; a VBIOS flash does",
    ),
    "sonoma_broadcom": Source(
        "sonoma_broadcom",
        "https://forum.amd-osx.com/threads/sonoma-broadcom-network-card-problem.4682",
        GROUP_COMMUNITY,
        "Sonoma и карты Broadcom",
        "Sonoma and Broadcom cards",
        "Разбор потери поддержки BCM4360 и способа вернуть её через OCLP",
        "Why BCM4360 support was dropped and how OCLP restores it",
    ),

    # --- официальные релизы и утилиты ---
    "ocpkg_releases": Source(
        "ocpkg_releases",
        "https://github.com/acidanthera/OpenCorePkg/releases",
        GROUP_EFI,
        "OpenCore: официальные релизы",
        "OpenCore: official releases",
        "Актуальные сборки OpenCore, драйверы и ocvalidate",
        "Current OpenCore builds, drivers and ocvalidate",
    ),
    "usbtoolbox": Source(
        "usbtoolbox",
        "https://github.com/USBToolBox/tool",
        GROUP_EFI,
        "USBToolBox: карта USB-портов",
        "USBToolBox: USB port map",
        "Картирование портов под лимит macOS в 15 портов на контроллер",
        "Port mapping for the macOS 15-port-per-controller limit",
    ),
    "ssdttime": Source(
        "ssdttime",
        "https://github.com/corpnewt/SSDTTime",
        GROUP_EFI,
        "SSDTTime: генерация SSDT по DSDT",
        "SSDTTime: SSDT generation from DSDT",
        "PLUG, EC, USBX, HPET и другие таблицы под конкретную плату",
        "PLUG, EC, USBX, HPET and other tables for a specific board",
    ),
    "proper_tree": Source(
        "proper_tree",
        "https://github.com/corpnewt/ProperTree",
        GROUP_EFI,
        "ProperTree: редактор plist",
        "ProperTree: plist editor",
        "Кроссплатформенный редактор config.plist с проверкой структуры",
        "Cross-platform config.plist editor with structure checks",
    ),
    "gensmbios": Source(
        "gensmbios",
        "https://github.com/corpnewt/GenSMBIOS",
        GROUP_EFI,
        "GenSMBIOS: генерация SMBIOS",
        "GenSMBIOS: SMBIOS generation",
        "Serial, MLB, UUID и ROM для выбранной модели Mac",
        "Serial, MLB, UUID and ROM for the chosen Mac model",
    ),

    # --- официальные справки по кекстам ---
    "applealc_codecs": Source(
        "applealc_codecs",
        "https://github.com/acidanthera/AppleALC/wiki/Supported-codecs",
        GROUP_HARDWARE,
        "AppleALC: поддерживаемые кодеки и layout-id",
        "AppleALC: supported codecs and layout-id",
        "Официальная таблица layout-id; брать значения только отсюда",
        "Official layout-id table; use values only from here",
    ),
    "whatevergreen_faq": Source(
        "whatevergreen_faq",
        "https://github.com/acidanthera/WhateverGreen/blob/master/Manual/FAQ.Chart.md",
        GROUP_HARDWARE,
        "WhateverGreen: FAQ по GPU",
        "WhateverGreen: GPU FAQ",
        "Артефакты, чёрный экран, HDMI-звук и порядок фреймбуферов",
        "Artifacts, black screen, HDMI audio and framebuffer order",
    ),
    "itlwm_repo": Source(
        "itlwm_repo",
        "https://github.com/OpenIntelWireless/itlwm",
        GROUP_HARDWARE,
        "itlwm: драйвер Intel Wi-Fi",
        "itlwm: Intel Wi-Fi driver",
        "Свежие релизы itlwm и HeliPort; AirportItlwm ограничен Sonoma",
        "Latest itlwm and HeliPort releases; AirportItlwm is capped at Sonoma",
    ),

    # --- диагностика ---
    "troubleshooting": Source(
        "troubleshooting",
        "https://dortania.github.io/OpenCore-Install-Guide/troubleshooting/extended/",
        GROUP_GUIDES,
        "Dortania: устранение проблем",
        "Dortania: troubleshooting",
        "Разбор зависаний, паник ядра и ошибок загрузки OpenCore",
        "Diagnosing hangs, kernel panics and OpenCore boot failures",
    ),
}


def all_sources() -> tuple[Source, ...]:
    """Все источники в порядке групп."""
    order = {g: i for i, g in enumerate(GROUPS)}
    return tuple(sorted(SOURCES.values(), key=lambda s: (order.get(s.group, 99), s.title)))


def sources_by_group(group: str, lang: str = "ru") -> list[Source]:
    items = [s for s in all_sources() if s.group == group]
    items.sort(key=lambda s: s.title_en if lang == "en" else s.title)
    return items


def title_of(src: Source, lang: str = "ru") -> str:
    return src.title_en if lang == "en" else src.title


def note_of(src: Source, lang: str = "ru") -> str:
    return src.note_en if lang == "en" else src.note


def _wifi_chipset(profile) -> str:
    net = getattr(profile, "net", None)
    return (getattr(net, "wifi_chipset", "") or "").lower() if net else ""


def _cpu_vendor(profile) -> str:
    cpu = getattr(profile, "cpu", None)
    return (getattr(cpu, "vendor", "") or "").lower() if cpu else ""


def relevant_keys(profile: Optional[object]) -> list[str]:
    """Ключи источников под конкретное железо, без повторов, по смыслу."""
    keys: list[str] = ["oc_guide"]
    if profile is None:
        keys += ["gpu_guide", "wireless_guide", "insanelymac"]
        return keys

    vendor = _cpu_vendor(profile)
    dgpu = getattr(profile, "dgpu", None)
    device_id = (getattr(dgpu, "device_id", "") or "").lower() if dgpu else ""

    if vendor == "amd":
        keys += ["oc_amd", "amd_osx"]
    if dgpu is not None and (getattr(dgpu, "vendor", "") or "").lower() == "amd":
        keys += ["gpu_guide", "gpu_amd"]
    if device_id == "6fdf":
        keys += ["rx580_2048sp"]

    net = getattr(profile, "net", None)
    eth = (getattr(net, "eth_name", "") or "").lower() if net else ""
    if "i211" in eth or "i210" in eth:
        keys += ["oc_kexts", "appleigb"]
    elif "intel" in eth:
        keys += ["oc_kexts"]

    wifi = _wifi_chipset(profile)
    if wifi == "intel":
        keys += ["itlwm_compat"]
    elif wifi == "mediatek":
        keys += ["itlwm_compat", "wireless_guide"]
    elif wifi == "broadcom":
        keys += ["wireless_guide", "oclp_wifi", "sonoma_broadcom"]
    elif wifi in ("realtek", "atheros"):
        keys += ["wireless_guide", "anti_hackintosh_net"]

    if vendor == "amd":
        keys += ["efi_mikigal", "efi_subhead", "efi_maxritz"]

    keys += ["insanelymac", "tonymacx86"]
    seen: set[str] = set()
    result: list[str] = []
    for k in keys:
        if k in SOURCES and k not in seen:
            seen.add(k)
            result.append(k)
    return result


def sources_for(profile: Optional[object]) -> list[Source]:
    """Источники, релевантные профилю, в порядке приоритета."""
    return [SOURCES[k] for k in relevant_keys(profile)]
