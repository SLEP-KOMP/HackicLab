"""Совместимость Wi-Fi/Bluetooth: модель -> драйвер, кексты и ограничения.

База собрана по первоисточникам: OpenIntelWireless (itlwm/AirportItlwm
Compat, релизы и issues), Dortania Wireless Buyers Guide, AirportBrcmFixup,
BrcmPatchRAM, ATH9KFixup, а также README сторонних драйверов (SimpleMtkWlan,
RealtekRTL8822C, Ath10kMac, chris1111 USB). Правило простое: «работает» —
только то, что заводится штатным кекстом без ручной правки системы.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Adapter:
    """Один чипсет/семейство: как заводится и до какой macOS."""

    key: str
    family: str
    models: str
    patterns: tuple[str, ...]
    kexts: str
    macos: str
    ru: str
    en: str
    supported: bool = True
    bt: str = ""


#: Порядок важен: сначала конкретные модели, в конце — семейство целиком.
ADAPTERS: tuple[Adapter, ...] = (
    # --- Broadcom: нативные Apple-модули ---
    Adapter(
        "bcm94360", "Broadcom",
        "BCM94360CD/CS2/CS/CSAX, BCM943602CDP/CD/CS, BCM94360NG, "
        "Fenvi FV-T919 / FV-HB1200",
        ("94360", "943602", "fv-t919", "fv-hb1200", "bcm94360"),
        "нативно (до Ventura), Sonoma+ — OCLP root patch",
        "Big Sur–Ventura без кекстов; Sonoma 14+ — root patch OCLP",
        "Нативный Apple AirPort: до Ventura кексты не нужны, на Sonoma и новее "
        "нужен root patch OCLP (IOSkywalkFamily + IO80211FamilyLegacy).",
        "Native Apple AirPort: no kexts up to Ventura; Sonoma and newer need the "
        "OCLP root patch (IOSkywalkFamily + IO80211FamilyLegacy).",
    ),
    Adapter(
        "bcm94352", "Broadcom",
        "BCM94352Z/HMB, Dell DW1560, Fenvi AC1200, AzureWave AW-CB162NF",
        ("94352", "dw1560", "aw-cb162", "bcm94352"),
        "AirportBrcmFixup + BrcmPatchRAM + BlueToolFixup",
        "до Ventura; Sonoma+ — вместе с OCLP",
        "Комбо-карта: Wi-Fi через AirportBrcmFixup, Bluetooth через "
        "BrcmPatchRAM. С Sonoma 14 требуется root patch OCLP.",
        "Combo card: Wi-Fi via AirportBrcmFixup, Bluetooth via BrcmPatchRAM. "
        "Sonoma 14+ requires the OCLP root patch.",
    ),
    Adapter(
        "bcm94350", "Broadcom",
        "BCM94350ZAE, Dell DW1820A, Lenovo T77H649, Lite-On WCBN808B",
        ("94350", "dw1820a", "94350zae"),
        "AirportBrcmFixup (pci-aspm-default=00) + BrcmPatchRAM",
        "до Ventura; Sonoma+ — вместе с OCLP",
        "Капризная карта: нужен AirportBrcmFixup и pci-aspm-default=<00>. "
        "На ноутбуках стабильность не гарантирована.",
        "Finicky card: needs AirportBrcmFixup and pci-aspm-default=<00>. "
        "Laptop stability is not guaranteed.",
    ),
    Adapter(
        "bcm43602", "Broadcom",
        "BCM43602 (MacBook Pro 2016–17, iMac), PCI 14e4:43ba",
        ("43602", "43ba"),
        "AirPortBrcmNIC (в IO80211FamilyLegacy на 12+)",
        "до Ventura; Sonoma+ — OCLP",
        "Драйвер AirPortBrcmNIC: до Ventura нативно, на Sonoma+ только через OCLP.",
        "AirPortBrcmNIC driver: native up to Ventura, Sonoma+ only via OCLP.",
    ),
    Adapter(
        "bcm4350", "Broadcom",
        "BCM4350, PCI 14e4:43a3",
        ("4350", "43a3"),
        "AirPortBrcmNIC",
        "до Ventura; Sonoma+ — OCLP",
        "Нативный модуль MacBook; на Sonoma и новее требуется OCLP.",
        "Native MacBook module; Sonoma and newer require OCLP.",
    ),
    Adapter(
        "bcm94331", "Broadcom",
        "BCM94331CD",
        ("94331",),
        "нативно (IO80211Family)",
        "до Catalina",
        "Работает нативно только на старых системах (до Catalina).",
        "Native only on older systems (up to Catalina).",
    ),
    Adapter(
        "bcm943224", "Broadcom",
        "BCM943224HMB, BCM943225HMB",
        ("943224", "943225"),
        "нативно до Catalina; Bluetooth — BrcmPatchRAM",
        "до Catalina",
        "Старый комбо-модуль: Wi-Fi до Catalina, Bluetooth через BrcmPatchRAM.",
        "Old combo module: Wi-Fi up to Catalina, Bluetooth via BrcmPatchRAM.",
    ),
    # --- Intel (OpenIntelWireless) ---
    Adapter(
        "intel-iwx", "Intel",
        "AX101, AX200/AX200D2, AX201, AX210, AX211, AX411, 9560, 9260, 9461/9462, "
        "Killer 1550/1550i, 1650/1650i/1650w/1650x/1690i/1690s",
        ("ax101", "ax200", "ax201", "ax210", "ax211", "ax411", "9560", "9260",
         "9461", "9462", "killer 1550", "killer 1650", "killer 1690", "1550i",
         "1650i", "1650x", "1690i", "1690s"),
        "itlwm + HeliPort (или AirportItlwm до Sonoma 14.4)",
        "itlwm — любая macOS; AirportItlwm — ≤ Sonoma 14.4",
        "Рабочий вариант для macOS: itlwm + HeliPort (сеть как Ethernet). "
        "AirportItlwm даёт нативный интерфейс, но не обновляется после Sonoma 14.4. "
        "AirDrop/Handoff не будет. BT — IntelBluetoothFirmware + IntelBTPatcher + "
        "BlueToolFixup.",
        "Working macOS path: itlwm + HeliPort (network as Ethernet). AirportItlwm "
        "gives the native interface but is not updated past Sonoma 14.4. No "
        "AirDrop/Handoff. BT via IntelBluetoothFirmware + IntelBTPatcher + "
        "BlueToolFixup.",
        bt="IntelBluetoothFirmware + IntelBTPatcher + BlueToolFixup",
    ),
    Adapter(
        "intel-iwm", "Intel",
        "7260, 7265/7265D, 3160, 3165, 3168, 8260, 8265, 8275, 4165, 9162",
        ("7260", "7265", "3160", "3165", "3168", "8260", "8265", "8275",
         "4165", "9162"),
        "itlwm + HeliPort (AirportItlwm ≤ Sonoma)",
        "itlwm — любая macOS",
        "Старые Intel-карты: только itlwm (или AirportItlwm до Sonoma). "
        "Скорость ниже, чем у AX-серии.",
        "Older Intel cards: itlwm only (or AirportItlwm up to Sonoma). Slower "
        "than the AX series.",
        bt="IntelBluetoothFirmware + IntelBTPatcher",
    ),
    Adapter(
        "intel-iwn", "Intel",
        "Centrino N 1000/105/130/135/2200/2230/6150/6250, WiFi Link "
        "5100/5300/5350/5150, Advanced-N 6200/6205/6230/6235/6300",
        ("centrino", "wifi link", "advanced-n", "2200", "2230", "5100", "5300",
         "5350", "5150", "6250", "6150", "6200", "6205", "6230", "6235", "6300"),
        "itlwm + HeliPort",
        "itlwm — любая macOS",
        "Очень старые Intel-карты: работают через itlwm на скорости 802.11n.",
        "Very old Intel cards: work via itlwm at 802.11n speeds.",
    ),
    Adapter(
        "intel-be200", "Intel",
        "BE200 (8086:272B), BE202",
        ("be200", "be202", "272b"),
        "только сторонние форки (AirportItlwm-Tahoe, ForbiddenItlwm)",
        "штатно не поддерживается; Wi-Fi 7 (EHT/MLO/6 ГГц) нет",
        "Wi-Fi 7 в штатном itlwm/AirportItlwm нет: запросы закрыты без реализации. "
        "Работает лишь через сторонние сборки и без Wi-Fi 7.",
        "Wi-Fi 7 is absent from upstream itlwm/AirportItlwm (requests closed "
        "unimplemented). Only third-party builds, and without Wi-Fi 7.",
        supported=False,
    ),
    # --- Atheros ---
    Adapter(
        "ath9k-native", "Atheros",
        "AR9280, AR9285, AR9287, AR9380 (AR5BHB92/95/97, AR5BXB112)",
        ("9280", "9285", "9287", "9380", "ar5bhb", "ar5bxb"),
        "нативно (IO80211Family)",
        "до High Sierra; в Mojave+ нужен reinject IO80211Family",
        "Старые Atheros: нативно до High Sierra, дальше только с подменой "
        "IO80211Family из 10.13.6.",
        "Old Atheros: native up to High Sierra; later only by reinjecting "
        "IO80211Family from 10.13.6.",
    ),
    Adapter(
        "ath9k-fixup", "Atheros",
        "AR9462/AR9463, AR9485, AR9565 (AR5B22)",
        ("9462", "9463", "9485", "9565", "ar5b22"),
        "ATH9KFixup + ATH9KInjector + AirPortAtheros40",
        "до Mojave",
        "Нужен ATH9KFixup и boot-args -ath9485/-ath9565; на Big Sur+ "
        "подтверждений нет.",
        "Needs ATH9KFixup and -ath9485/-ath9565 boot-args; no confirmation "
        "beyond Mojave.",
    ),
    Adapter(
        "qca6174", "Qualcomm Atheros",
        "QCA6174 (168c:003e), QCA9377 (168c:0042)",
        ("qca6174", "qca9377", "003e", "0042"),
        "только экспериментальный Ath10kMac",
        "штатно не поддерживается",
        "Ath10k — тоже Wi-Fi-стек (IOEthernet), не нативный AirPort: нет "
        "AirDrop/AWDL/WPA3, проект экспериментальный.",
        "Ath10k is in the same boat: an Ethernet-style stack, not native AirPort. "
        "No AirDrop/AWDL/WPA3, experimental project.",
        supported=False,
    ),
    # --- MediaTek / Realtek ---
    Adapter(
        "mediatek", "MediaTek",
        "MT7921/7921K/7922, MT7920/7925/7927, MT7630, MT7663 (RZ608)",
        ("mediatek", "mt79", "mt76", "rz608"),
        "нет (SimpleMtkWlan — экспериментальный)",
        "не поддерживается",
        "Для MediaTek нет драйвера в macOS. Замена на Intel AX200/AX210 или "
        "BCM94360 — единственный рабочий путь; USB-адаптер тоже вариант.",
        "No macOS driver for MediaTek. Replacing it with Intel AX200/AX210 or "
        "BCM94360 is the only working path; a USB adapter also works.",
        supported=False,
    ),
    Adapter(
        "realtek-8822c", "Realtek",
        "RTL8822CE (10ec:c822)",
        ("8822ce", "c822"),
        "только экспериментальный RealtekRTL8822C",
        "штатно не поддерживается",
        "Экспериментальный RealtekRTL8822C: сеть как Ethernet, без AirDrop/AWDL/WPA3.",
        "Experimental RealtekRTL8822C: Ethernet-style networking, no "
        "AirDrop/AWDL/WPA3.",
        supported=False,
    ),
    Adapter(
        "realtek", "Realtek",
        "RTL8821CE, RTL8822BE, RTL8852AE/BE/CE, RTL8812AU/8814AU/8821AU, "
        "RTL8188/8192",
        ("realtek", "rtl88", "rtl81", "8852", "8821", "8822be", "8812", "8814",
         "8192", "8188"),
        "нет (только USB-пакет chris1111)",
        "не поддерживается",
        "Realtek Wi-Fi в macOS не поддерживается. PCIe-карты не заводятся, "
        "для USB есть сторонний пакет chris1111 (без AirDrop/Handoff).",
        "Realtek Wi-Fi is unsupported in macOS. PCIe cards do not work; USB "
        "sticks need the third-party chris1111 package (no AirDrop/Handoff).",
        supported=False,
    ),
    Adapter(
        "killer-1675", "Intel",
        "Killer 1675x (AX210-база)",
        ("1675",),
        "не подтверждено в таблице itlwm",
        "не подтверждено",
        "Killer 1675x отсутствует в таблице совместимости itlwm — считаем "
        "неподтверждённым. 1550i/1650i/1690i работают как обычные Intel.",
        "Killer 1675x is absent from the itlwm compatibility table, so it is "
        "treated as unconfirmed. 1550i/1650i/1690i work as regular Intel.",
        supported=False,
    ),
    Adapter(
        "bcm-legacy", "Broadcom",
        "BCM43142, BCM4313, BCM4312, BCM4356, BCM43228",
        ("43142", "4313", "4312", "4356", "43228"),
        "нет",
        "не поддерживается",
        "Старые Broadcom без драйвера macOS: Wi-Fi не заведётся. "
        "Bluetooth-часть BCM43142A0 при этом работает через BrcmPatchRAM.",
        "Old Broadcom chips without a macOS driver: Wi-Fi will not work. The "
        "BCM43142A0 Bluetooth part still works via BrcmPatchRAM.",
        supported=False,
    ),
    Adapter(
        "bcm-old", "Broadcom",
        "BCM4322, BCM43224/4353, BCM4321/4331",
        ("4322", "43224", "4353", "4321", "4331"),
        "нативно только на очень старых macOS",
        "до El Capitan / 10.14",
        "Работают только на древних системах; для современных macOS не годятся.",
        "Only ancient macOS releases; not usable on modern systems.",
        supported=False,
    ),
    Adapter(
        "marvell", "Marvell",
        "88W8xxx",
        ("marvell", "88w8"),
        "нет данных",
        "не подтверждено",
        "Нет подтверждённых драйверов и списков — считать неподдерживаемым.",
        "No confirmed drivers or lists — treat as unsupported.",
        supported=False,
    ),
    # --- Семейные fallback (в самом конце) ---
    Adapter(
        "family-broadcom", "Broadcom", "любой Broadcom (модель не распознана)",
        ("broadcom", "bcm"),
        "нативно/AirportBrcmFixup; Sonoma+ — OCLP",
        "зависит от модели",
        "Broadcom в целом заводится, но точный набор кекстов зависит от модели: "
        "BCM94360 — нативно, BCM94352/94350 — AirportBrcmFixup.",
        "Broadcom generally works, but the exact kext set depends on the model: "
        "BCM94360 native, BCM94352/94350 need AirportBrcmFixup.",
    ),
    Adapter(
        "family-intel", "Intel", "любой Intel (модель не распознана)",
        ("intel",),
        "itlwm + HeliPort (AirportItlwm ≤ Sonoma)",
        "itlwm — любая macOS",
        "Intel-карты поддерживаются через itlwm; AirportItlwm ограничен Sonoma 14.4.",
        "Intel cards work via itlwm; AirportItlwm stops at Sonoma 14.4.",
    ),
    Adapter(
        "family-atheros", "Atheros", "любой Atheros/Qualcomm",
        ("atheros", "qualcomm"),
        "нативно (старые) или ATH9KFixup",
        "зависит от модели",
        "Atheros: AR92xx нативно до High Sierra, AR9462/9485/9565 — ATH9KFixup "
        "до Mojave; QCA6174/9377 — только экспериментально.",
        "Atheros: AR92xx native up to High Sierra, AR9462/9485/9565 via "
        "ATH9KFixup up to Mojave; QCA6174/9377 experimental only.",
    ),
)


#: Семейства, у которых нет штатного драйвера ни для одной macOS.
UNSUPPORTED_CHIPSETS = frozenset({"mediatek", "realtek", "qualcomm"})


#: Семейство сканера -> семейство базы.
_FAMILY = {
    "broadcom": "Broadcom",
    "intel": "Intel",
    "atheros": "Atheros",
    "qualcomm": "Qualcomm Atheros",
    "mediatek": "MediaTek",
    "realtek": "Realtek",
}


def find_adapter(name: str) -> Adapter | None:
    """Адаптер по имени устройства Windows (первое совпадение шаблонов)."""
    low = (name or "").lower()
    if not low:
        return None
    for adapter in ADAPTERS:
        if any(pattern in low for pattern in adapter.patterns):
            return adapter
    return None


def family_adapter(chipset: str) -> Adapter | None:
    """Адаптер по семейству из сканера, если модель не распознана."""
    family = _FAMILY.get((chipset or "").strip().lower())
    if not family:
        return None
    for adapter in ADAPTERS:
        if adapter.key.startswith("family-") and adapter.family == family:
            return adapter
    return None


def adapter_for(name: str = "", chipset: str = "") -> Adapter | None:
    return find_adapter(name) or family_adapter(chipset)


def is_unsupported(chipset: str = "", name: str = "") -> bool:
    """Нет ли штатного драйвера: модель важнее семейства."""
    adapter = find_adapter(name)
    if adapter is not None:
        return not adapter.supported
    chip = (chipset or "").strip().lower()
    if chip in UNSUPPORTED_CHIPSETS:
        return True
    adapter = family_adapter(chip)
    return bool(adapter is not None and not adapter.supported)


def has_driver(chipset: str = "", name: str = "") -> bool:
    return not is_unsupported(chipset, name)


def support(name: str = "", chipset: str = "") -> dict:
    """Сводка для интерфейса: статус, как заводится, кексты, ограничение."""
    adapter = adapter_for(name, chipset)
    if adapter is None:
        return {"supported": True, "kexts": "", "macos": "", "ru": "", "en": ""}
    return {
        "supported": adapter.supported,
        "kexts": adapter.kexts,
        "macos": adapter.macos,
        "models": adapter.models,
        "key": adapter.key,
        "ru": adapter.ru,
        "en": adapter.en,
    }


def note_for(name: str) -> dict[str, str]:
    """Короткая заметка по названию адаптера: {'ru': ..., 'en': ...}."""
    adapter = find_adapter(name)
    if adapter is None:
        return {}
    return {"ru": adapter.ru, "en": adapter.en}


def all_chipsets() -> tuple[tuple[str, str, str], ...]:
    """Короткая таблица для отчётов: (ключ, Wi-Fi-драйвер, Bluetooth)."""
    return tuple((a.key.upper(), a.kexts, a.bt or "—") for a in ADAPTERS)


def supported_adapters() -> tuple[Adapter, ...]:
    return tuple(a for a in ADAPTERS if a.supported)


def unsupported_adapters() -> tuple[Adapter, ...]:
    return tuple(a for a in ADAPTERS if not a.supported)
