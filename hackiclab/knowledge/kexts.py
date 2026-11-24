"""Кекст-база и подбор кекстсов под профиль железа.

Данные о кекстах — публичные репозитории acidanthera, OpenIntelWireless,
VoodooI2C, Mieze, ChefKissInc и других проектов. Правила подбора собраны
из открытой документации Dortania и проверены на живом железе; порядок
в списке важен: Lilu и зависимости идут раньше потребителей.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..scanner.models import HardwareProfile


@dataclass
class KextEntry:
    name: str
    repo: str                                  # "owner/repo"
    asset_pattern: str = ""                    # подстрока имени asset в release
    note: str = ""
    bundle_name: str = ""                      # реальное имя .kext если отличается
    internal: bool = False                     # true = архив уже внутри другого (VirtualSMC и т.п.)
    home: str = "github"                       # github / dortania
    os_min: str = ""                           # минимальная macOS (для версии-специфичных)
    os_max: str = ""                           # максимальная macOS, где кекст ещё работает
    # Версии-специфичные сборки в одном релизе: (macOS, подстрока имени ассета).
    macos_assets: tuple = ()
    # Прямая ссылка на архив: для кекстов, которые публикуются не релизами
    # GitHub, а файлами в другом репозитории (payloads OCLP).
    url: str = ""


KEXT_DB: dict[str, KextEntry] = {}


def _reg(d):
    KEXT_DB.update(d)


_reg({
    "Lilu": KextEntry("Lilu", "acidanthera/Lilu", "Lilu-", "Базовый патчер, должен загружаться первым"),
    "VirtualSMC": KextEntry("VirtualSMC", "acidanthera/VirtualSMC", "VirtualSMC-", "Эмулятор SMC"),
    "FakeSMC": KextEntry("FakeSMC", "CloverHackyColor/FakeSMC3_with_plugins", "FakeSMC", "SMC для Sandy Bridge и старше (легаси)"),
    "RestrictEvents": KextEntry("RestrictEvents", "acidanthera/RestrictEvents", "RestrictEvents-", "Патчи системных событий"),
    "FeatureUnlock": KextEntry("FeatureUnlock", "acidanthera/FeatureUnlock", "FeatureUnlock-", "Sidecar/AirPlay/Universal Control"),
    "CPUFriend": KextEntry("CPUFriend", "acidanthera/CPUFriend", "CPUFriend-", "Управление мощностью/частотами CPU"),
    "NVMeFix": KextEntry("NVMeFix", "acidanthera/NVMeFix", "NVMeFix-", "Power management NVMe + APST"),
    "DebugEnhancer": KextEntry("DebugEnhancer", "acidanthera/DebugEnhancer", "DebugEnhancer-", "Отладочное логирование"),
    "CryptexFixup": KextEntry("CryptexFixup", "acidanthera/CryptexFixup", "CryptexFixup-", "Криптекс Ventura+ на старом/AMD железе"),
    "AppleMCEReporterDisabler": KextEntry(
        "AppleMCEReporterDisabler", "dortania/OpenCore-Legacy-Patcher",
        "AppleMCEReporterDisabler", "Отключает AppleMCEReporter — обязателен на AMD",
        url="https://github.com/dortania/OpenCore-Legacy-Patcher/raw/main/payloads/"
            "Kexts/Misc/AppleMCEReporterDisabler-v1.0.0.zip",
    ),

    "SMCBatteryManager": KextEntry("SMCBatteryManager", "acidanthera/VirtualSMC", "VirtualSMC-", "Батарея", internal=True),
    "SMCProcessor": KextEntry("SMCProcessor", "acidanthera/VirtualSMC", "VirtualSMC-", "Температуры CPU", internal=True),
    "SMCSuperIO": KextEntry("SMCSuperIO", "acidanthera/VirtualSMC", "VirtualSMC-", "Вентиляторы (desktop)", internal=True),
    "SMCLightSensor": KextEntry("SMCLightSensor", "acidanthera/VirtualSMC", "VirtualSMC-", "Датчик света", internal=True),
    "SMCAMDProcessor": KextEntry("SMCAMDProcessor", "trulyspinach/SMCAMDProcessor", "SMCAMDProcessor", "Датчики AMD CPU"),

    "AppleALC": KextEntry("AppleALC", "acidanthera/AppleALC", "AppleALC-", "Аудио-кодеки через Lilu"),
    "WhateverGreen": KextEntry("WhateverGreen", "acidanthera/WhateverGreen", "WhateverGreen-", "Framebuffer GPU + HDMI/DP audio"),

    "VoodooPS2Controller": KextEntry("VoodooPS2Controller", "acidanthera/VoodooPS2", "VoodooPS2Controller-", "PS/2 клавиатура+мышь+тачпад", internal=True),
    "VoodooI2C": KextEntry("VoodooI2C", "VoodooI2C/VoodooI2C", "VoodooI2C-", "I2C тачпад/тачскрин", internal=True),
    "VoodooI2CHID": KextEntry("VoodooI2CHID", "VoodooI2C/VoodooI2C", "VoodooI2C-", "I2C-HID сателлит", internal=True),
    "VoodooI2CSynaptics": KextEntry("VoodooI2CSynaptics", "VoodooI2C/VoodooI2C", "VoodooI2C-", "Synaptics I2C", internal=True),
    "VoodooI2CELAN": KextEntry("VoodooI2CELAN", "VoodooI2C/VoodooI2C", "VoodooI2C-", "ELAN I2C", internal=True),
    "VoodooGPIO": KextEntry("VoodooGPIO", "VoodooI2C/VoodooI2C", "VoodooI2C-", "GPIO pinning", internal=True),
    "VoodooInput": KextEntry("VoodooInput", "acidanthera/VoodooInput", "VoodooInput-", "Мультитач input"),

    "IntelMausiEthernet": KextEntry("IntelMausiEthernet", "acidanthera/IntelMausi", "IntelMausi-", "Intel I219/I218/I217", bundle_name="IntelMausi"),
    "AppleIGC": KextEntry("AppleIGC", "SongXiaoXi/AppleIGC", "AppleIGC", "Intel I225-V / I226-V 2.5GbE"),
    "AppleIntelE1000e": KextEntry("AppleIntelE1000e", "chris1111/AppleIntelE1000e", "AppleIntelE1000e-", "Intel 82578/82577/82574/82567"),
    "AppleIntelI210Ethernet": KextEntry(
        "AppleIntelI210Ethernet", "dortania/OpenCore-Legacy-Patcher",
        "AppleIntelI210-", "Intel I211/I210 (легаси, до Monterey)",
        url="https://github.com/dortania/OpenCore-Legacy-Patcher/raw/main/payloads/"
            "Kexts/Ethernet/CatalinaIntelI210Ethernet-v1.0.0.zip",
        bundle_name="CatalinaIntelI210Ethernet",
    ),
    "AppleIGB": KextEntry("AppleIGB", "ayushere/AppleIGB", "AppleIGB-",
                          "Intel I210/I211/I350 на Monterey+ (сборки форка — под Tahoe 26+)",
                          bundle_name="AppleIGB", os_min="monterey"),
    "RealtekRTL8111": KextEntry("RealtekRTL8111", "Mieze/RTL8111_driver_for_OS_X", "RealtekRTL8111-", "Realtek RTL8111/RTL8168"),
    "RealtekRTL8125": KextEntry("LucyRTL8125Ethernet", "Mieze/LucyRTL8125Ethernet", "LucyRTL8125Ethernet-", "Realtek RTL8125 2.5GbE"),
    "NullEthernet": KextEntry("NullEthernet", "jcreed69/NullEthernet", "NullEthernet", "Заглушка Ethernet для iMessage"),

    "itlwm": KextEntry("itlwm", "OpenIntelWireless/itlwm", "itlwm_", "Intel WiFi (нужен HeliPort)"),
    # AirportItlwm публикуется отдельной сборкой на каждую macOS. Последняя
    # официальная — Sonoma 14.4, на Sequoia/Tahoe кекста нет.
    "AirportItlwm": KextEntry(
        "AirportItlwm", "OpenIntelWireless/itlwm", "AirportItlwm_",
        "Intel WiFi как нативный Airport",
        os_min="big sur", os_max="sonoma",
        macos_assets=(
            ("high sierra", "HighSierra"), ("mojave", "Mojave"),
            ("catalina", "Catalina"), ("big sur", "BigSur"),
            ("monterey", "Monterey"), ("ventura", "Ventura"),
            ("sonoma", "Sonoma"),
        ),
    ),
    "AirportBrcmFixup": KextEntry("AirportBrcmFixup", "acidanthera/AirportBrcmFixup", "AirportBrcmFixup-", "Broadcom WiFi патчи"),
    # С macOS 13.3 Apple вырезала драйверы Broadcom: нативный модуль работает
    # только с этим набором — блокировкой штатного IOSkywalkFamily и AMFIPass.
    "AMFIPass": KextEntry(
        "AMFIPass", "dortania/OpenCore-Legacy-Patcher", "AMFIPass-",
        "Замена amfi=0x80 для патчей OCLP", os_min="big sur",
        url="https://github.com/dortania/OpenCore-Legacy-Patcher/raw/main/payloads/"
            "Kexts/Acidanthera/AMFIPass-v1.4.1-RELEASE.zip",
    ),
    "IOSkywalkFamily": KextEntry(
        "IOSkywalkFamily", "dortania/OpenCore-Legacy-Patcher", "IOSkywalkFamily-",
        "Legacy Wi-Fi: каркас IOSkywalk для Broadcom", os_min="ventura",
        url="https://github.com/dortania/OpenCore-Legacy-Patcher/raw/main/payloads/"
            "Kexts/Wifi/IOSkywalkFamily-v1.2.0.zip",
    ),
    "IO80211FamilyLegacy": KextEntry(
        "IO80211FamilyLegacy", "dortania/OpenCore-Legacy-Patcher", "IO80211FamilyLegacy",
        "Legacy Wi-Fi: AirPort для Broadcom на Ventura+", os_min="ventura",
        url="https://github.com/dortania/OpenCore-Legacy-Patcher/raw/main/payloads/Kexts/Wifi/"
            "IO80211FamilyLegacy-v1.0.0.zip",
    ),
    "ATH9KFixup": KextEntry("ATH9KFixup", "black-dragon74/ATH9KFixup", "release", "Atheros WiFi патчи"),

    "IntelBluetoothFirmware": KextEntry("IntelBluetoothFirmware", "OpenIntelWireless/IntelBluetoothFirmware", "IntelBluetooth", "Intel BT"),
    "IntelBTPatcher": KextEntry("IntelBTPatcher", "OpenIntelWireless/IntelBluetoothFirmware", "IntelBluetooth", "Intel BT патчи", internal=True),
    "BlueToolFixup": KextEntry("BlueToolFixup", "acidanthera/BrcmPatchRAM", "BrcmPatchRAM-", "BT stack fix 12+", internal=True),
    "BrcmPatchRAM3": KextEntry("BrcmPatchRAM3", "acidanthera/BrcmPatchRAM", "BrcmPatchRAM-", "Broadcom BT (12+)", internal=True),
    "BrcmFirmwareData": KextEntry("BrcmFirmwareData", "acidanthera/BrcmPatchRAM", "BrcmPatchRAM-", "Broadcom BT firmware", internal=True),

    "NootRX": KextEntry("NootRX", "ChefKissInc/NootRX", "NootRX-",
                        "RX 6600–6950 (Navi 2x) вместо WhateverGreen; "
                        "вместе с WhateverGreen не ставится"),
    "NootedRed": KextEntry(
        "NootedRed", "ChefKissInc/NootedRed", "NootedRed",
        "AMD APU iGPU (Raven/Vega на Ryzen) — вместо WhateverGreen", os_min="big sur"),
    "RealtekCardReader": KextEntry(
        "RealtekCardReader", "0xFireWolf/RealtekCardReader", "RealtekCardReader",
        "Кардридер Realtek RTS5227/5229/5249 и др."),
    "RadeonSensor": KextEntry("RadeonSensor", "aluveitie/RadeonSensor", "RadeonSensor-", "Температура AMD GPU"),
    "SMCRadeonGPU": KextEntry("SMCRadeonGPU", "aluveitie/RadeonSensor", "RadeonSensor-", "Темп GPU в HWMonitor", internal=True),

    "CpuTopologyRebuild": KextEntry("CpuTopologyRebuild", "b00t0x/CpuTopologyRebuild", "CpuTopologyRebuild-", "Alder/Raptor P+E topology"),
    "HibernationFixup": KextEntry("HibernationFixup", "acidanthera/HibernationFixup", "HibernationFixup-", "Стабильность sleep/wake"),
    "RTCMemoryFixup": KextEntry("RTCMemoryFixup", "acidanthera/RTCMemoryFixup", "RTCMemoryFixup-", "Фикс NVRAM reset loop"),
    "ECEnabler": KextEntry("ECEnabler", "1Revenger1/ECEnabler", "ECEnabler-", "Датчики батареи >8-bit"),
    "USBToolBox": KextEntry("USBToolBox", "USBToolBox/kext", "USBToolBox-", "USB порт-маппинг"),
    "YogaSMC": KextEntry("YogaSMC", "zhen-zen/YogaSMC", "YogaSMC", "ThinkPad/IdeaPad кнопки FN"),
    "BrightnessKeys": KextEntry("BrightnessKeys", "acidanthera/BrightnessKeys", "BrightnessKeys-", "Кнопки яркости F1/F2"),
    "NoTouchID": KextEntry("NoTouchID", "al3xtjames/NoTouchID", "NoTouchID-", "Скрыть Touch ID prompt"),
})

# SMBIOS-модель по (generation, platform)
SMBIOS_MAP: dict[tuple, str] = {
    (1, "laptop"): "MacBookPro8,1", (2, "laptop"): "MacBookPro8,1",
    (3, "laptop"): "MacBookPro9,2", (4, "laptop"): "MacBookPro11,1",
    (5, "laptop"): "MacBookPro12,1", (6, "laptop"): "MacBookPro13,1",
    (7, "laptop"): "MacBookPro14,1", (8, "laptop"): "MacBookPro15,2",
    (9, "laptop"): "MacBookPro16,1", (10, "laptop"): "MacBookPro16,2",
    (11, "laptop"): "MacBookPro16,1", (12, "laptop"): "MacBookPro16,1",
    (13, "laptop"): "MacBookPro16,1", (14, "laptop"): "MacBookPro16,1",
    (15, "laptop"): "MacBookPro16,1",
    (6, "desktop"): "iMac17,1", (7, "desktop"): "iMac18,3",
    (8, "desktop"): "iMac19,1", (9, "desktop"): "iMac19,1",
    (10, "desktop"): "iMac20,1", (11, "desktop"): "MacPro7,1",
    (12, "desktop"): "MacPro7,1", (13, "desktop"): "MacPro7,1",
    (14, "desktop"): "MacPro7,1", (15, "desktop"): "MacPro7,1",
}


# Порядок версий macOS (от старых к новым) для сравнения совместимости SMBIOS.
_MACOS_ORDER = [
    "High Sierra", "Mojave", "Catalina", "Big Sur", "Monterey",
    "Ventura", "Sonoma", "Sequoia", "Tahoe", "Golden Gate",
]

# Числовые версии macOS в том же порядке: индекс строки — это индекс версии.
_MACOS_NUMBERS = ("10.13", "10.14", "10.15", "11", "12", "13", "14", "15", "26", "27")


def _macos_idx(target: str) -> int:
    t = (target or "").lower()
    for i, name in enumerate(_MACOS_ORDER):
        if name.lower() in t:
            return i
    for i, num in enumerate(_MACOS_NUMBERS):
        if num in t:
            return i
    return len(_MACOS_ORDER) - 1  # неизвестно/авто — последняя (актуальная)


# SMBIOS-модели для AMD desktop с максимальной версией macOS, на которой
# они работают «чисто» (без хаков). MacPro7,1 поддерживается во всех версиях,
# поэтому для актуальных версий это выбор по умолчанию.
_AMD_DESKTOP_SMBIOS = [
    ("iMacPro1,1", 7),      # Sonoma — крайняя «из коробки» без патча
    ("MacPro7,1", 8),       # Sequoia/Tahoe — топовый выбор для AMD
]
# Intel desktop: привязаны к поколению, но если выбранная macOS новее, чем
# поддерживает ближайшая модель — берём более новую модель того же форм-фактора.
_INTEL_DESKTOP_BY_GEN = {
    0: "iMac13,1", 2: "iMac13,1", 3: "iMac14,2", 4: "iMac15,1",
    5: "iMac17,1", 6: "iMac17,1", 7: "iMac18,3",
    8: "iMac19,1", 9: "iMac19,1", 10: "iMac20,1",
    11: "MacPro7,1", 12: "MacPro7,1", 13: "MacPro7,1",
    14: "MacPro7,1", 15: "MacPro7,1",
}
# Для Intel: какой максимальной версии «чисто» хватает каждой модели.
_INTEL_DESKTOP_MAX = {
    "iMac13,1": 4, "iMac14,2": 4, "iMac15,1": 4,
    "iMac17,1": 6, "iMac18,3": 6, "iMac19,1": 7,
    "iMac20,1": 7, "MacPro7,1": 8,
}


def _amd_desktop_model(need: int) -> str:
    """Ближайшая AMD-модель, которая держит нужную версию macOS."""
    for model, maxv in _AMD_DESKTOP_SMBIOS:
        if maxv >= need:
            return model
    return _AMD_DESKTOP_SMBIOS[-1][0]


def _intel_desktop_model(generation: int, need: int) -> str:
    """Базовая модель поколения, поднятая вверх, если macOS слишком новая."""
    model = _INTEL_DESKTOP_BY_GEN.get(generation)
    if model is None:
        return "MacPro7,1"
    if _INTEL_DESKTOP_MAX.get(model, 0) >= need:
        return model
    for candidate, maxv in sorted(_INTEL_DESKTOP_MAX.items(), key=lambda x: x[1]):
        if maxv >= need:
            return candidate
    return "MacPro7,1"


def smbios_model_for(profile: HardwareProfile, macos_target: str = "") -> str:
    """Выбирает SMBIOS-модель по железу и (опционально) по версии macOS.

    Версия влияет на доступную модель: если выбранная macOS слишком новая для
    базовой модели поколения, подбирается более новая модель того же
    форм-фактора (ноутбук/десктоп), поддерживающая нужную версию.
    """
    need = _macos_idx(macos_target)
    if not macos_target:
        # Пустая цель — это ещё не выбранная macOS: показываем модель под
        # максимально доступную версию, иначе карточка обещает MacPro7,1,
        # а сборка ставит iMacPro1,1.
        from .oc_platforms import MAX_MACOS_BY_GEN
        need = _macos_idx(MAX_MACOS_BY_GEN.get(profile.cpu.generation, ""))

    if profile.cpu.vendor == "amd":
        if profile.platform == "laptop":
            return "MacBookPro15,2"
        return _amd_desktop_model(need)

    if profile.platform == "laptop":
        return SMBIOS_MAP.get((profile.cpu.generation, "laptop"), "MacBookPro15,2")
    return _intel_desktop_model(profile.cpu.generation, need)


_BRCM_LEGACY_FROM = _MACOS_ORDER.index("Ventura")


def _needs_brcm_legacy(target_macos: str = "") -> bool:
    """Нужен ли набор OCLP для Broadcom: с 13.3 Apple убрала драйверы.

    Пустая цель считается актуальной macOS — тогда набор тоже нужен.
    """
    if not target_macos:
        return True
    return _macos_idx(target_macos) >= _BRCM_LEGACY_FROM


def macos_in_range(entry: KextEntry, target_macos: str = "") -> bool:
    """Попадает ли целевая macOS в диапазон, где кекст реально работает."""
    if not target_macos:
        return True
    idx = _macos_idx(target_macos)
    if entry.os_min and idx < _macos_idx(entry.os_min):
        return False
    return not (entry.os_max and idx > _macos_idx(entry.os_max))


def asset_variant(entry: KextEntry, target_macos: str = "") -> str:
    """Подстрока имени ассета под целевую macOS (версии-специфичные сборки).

    AirportItlwm публикует в одном релизе отдельные архивы на каждую macOS
    (``AirportItlwm_v2.3.0_stable_Ventura.kext.zip`` и т. д.). Без этой
    подсказки загрузчик брал первый по длине/алфавиту файл и в EFI попадала
    сборка под другую систему — кекст не прелинковывался при загрузке.
    """
    if not entry.macos_assets or not target_macos:
        return ""
    limit = _macos_idx(target_macos)
    best = ""
    for name, fragment in entry.macos_assets:
        if _macos_idx(name) <= limit:
            best = fragment
    return best


def _is_navi2x(gpu) -> bool:
    """NootRX нужен только Navi 2x (RX 6600–6950), не Polaris/Navi 1x."""
    name = (getattr(gpu, "name", "") or "").lower()
    dev = (getattr(gpu, "device_id", "") or "").lower().replace("0x", "")
    if dev in {"73bf", "73e3", "73ef", "73ff", "7420", "73a5"}:
        return True
    return any(x in name for x in
               ("6600", "6650", "6700", "6750", "6800", "6900", "6950"))


#: Device-id Navi 10/14/21/22/23 — Dortania: agdpmod=pikera нужен всем Navi.
NAVI_DEVICE_IDS = frozenset({
    "731f", "7340", "7341", "734f",            # Navi 10/14 (RX 5700/5500)
    "73bf", "73a3", "73af", "73a5",            # Navi 21 (RX 6800/6900)
    "73df", "73ef",                            # Navi 22 (RX 6700/6750)
    "73ff", "73e3",                            # Navi 23 (RX 6600)
})


def is_navi_gpu(gpu) -> bool:
    """Navi любой серии: на них без agdpmod=pikera бывает чёрный экран."""
    if gpu is None or getattr(gpu, "vendor", "") != "amd":
        return False
    dev = (getattr(gpu, "device_id", "") or "").lower().replace("0x", "")
    if dev in NAVI_DEVICE_IDS:
        return True
    name = (getattr(gpu, "name", "") or "").lower()
    # только номера Navi-моделей: «rx 5» поймал бы Polaris RX 580
    return any(x in name for x in ("5500", "5600", "5700", "6600", "6650",
                                    "6700", "6750", "6800", "6900", "6950"))


class _KextList:
    """Накопитель подбора: держит порядок и не даёт дубликатов."""

    def __init__(self) -> None:
        self.items: list[KextEntry] = []
        self._seen: set[str] = set()

    def add(self, *names: str) -> None:
        for name in names:
            if name in self._seen:
                continue
            self._seen.add(name)
            entry = KEXT_DB.get(name)
            if entry is not None:
                self.items.append(entry)


def _cpu_kexts(chosen: _KextList, profile: HardwareProfile) -> None:
    if profile.cpu.vendor == "amd":
        # Без AppleMCEReporterDisabler ядро падает на AppleMCEReporter.
        chosen.add("SMCAMDProcessor", "CryptexFixup", "RestrictEvents",
                   "AppleMCEReporterDisabler")
        return
    chosen.add("RestrictEvents", "CPUFriend")
    if profile.cpu.generation >= 12:
        chosen.add("CpuTopologyRebuild")


def _storage_kexts(chosen: _KextList, profile: HardwareProfile, target_macos: str) -> None:
    # NVMe: Power management и APST нужны с Monterey на любом железе
    storage = getattr(profile, "storage", None)
    if storage is None or not getattr(storage, "nvme_present", False):
        return
    if macos_in_range(KEXT_DB["NVMeFix"], target_macos):
        chosen.add("NVMeFix")


def _gpu_kexts(chosen: _KextList, profile: HardwareProfile) -> None:
    gpu = profile.dgpu or profile.igpu or None
    if gpu is None:
        return
    if gpu.vendor == "intel" or (profile.igpu and profile.igpu.vendor == "intel"):
        chosen.add("WhateverGreen")
    # AMD APU (Raven/Vega в Ryzen) без дискретки: iGPU тянет только NootedRed
    apu = (profile.igpu is not None and profile.igpu.vendor == "amd"
           and not profile.dgpu)
    if gpu.vendor == "amd":
        if _is_navi2x(gpu):
            chosen.add("NootRX", "RadeonSensor", "SMCRadeonGPU")
        elif apu:
            # NootedRed заменяет WhateverGreen на APU: они конфликтуют
            chosen.add("NootedRed", "RadeonSensor", "SMCRadeonGPU")
        else:
            chosen.add("WhateverGreen", "RadeonSensor", "SMCRadeonGPU")
    if apu:
        chosen.add("NootedRed")


def _audio_kexts(chosen: _KextList, profile: HardwareProfile) -> None:
    # AppleALC нужен и при неопознанном кодеке — иначе звука нет вовсе
    audio = getattr(profile, "audio", None)
    if audio is None:
        return
    if audio.codec or (audio.name and getattr(audio, "pci_device", -1) >= 0):
        chosen.add("AppleALC")


#: Подстроки в имени Ethernet-устройства -> кекст. Проверяются по порядку.
_ETHERNET_RULES = (
    (("i219", "i218", "i217"), "IntelMausiEthernet"),
    (("i225", "i226"), "AppleIGC"),
    (("rtl8125",), "RealtekRTL8125"),
    (("rtl",), "RealtekRTL8111"),
)

#: I210/I211: до Monterey работает старый AppleIntelI210Ethernet, с Monterey —
#: AppleIGB. Выбор зависит от целевой macOS, поэтому вынесен из таблицы.
_LEGACY_ETHERNET_MARKERS = ("i211", "i210")


def _ethernet_kexts(chosen: _KextList, profile: HardwareProfile,
                    target_macos: str = "") -> None:
    # Чипсет приходит общим («intel»), модель уточняется по имени устройства
    text = f"{profile.net.eth_chipset or ''} {profile.net.eth_name or ''}".lower()
    if any(marker in text for marker in _LEGACY_ETHERNET_MARKERS):
        if macos_in_range(KEXT_DB["AppleIGB"], target_macos):
            chosen.add("AppleIGB")
        else:
            chosen.add("AppleIntelI210Ethernet")
        return
    for markers, name in _ETHERNET_RULES:
        if any(marker in text for marker in markers):
            chosen.add(name)
            return


def _wifi_kexts(chosen: _KextList, profile: HardwareProfile, mode: str,
                target_macos: str) -> None:
    chipset = (profile.net.wifi_chipset or "").lower()
    native = profile.net.bt_native_apple
    if chipset == "intel":
        airport = KEXT_DB["AirportItlwm"]
        if mode != "itlwm" and not macos_in_range(airport, target_macos):
            # AirportItlwm не публикуется для этой macOS — только itlwm+HeliPort
            chosen.add("itlwm")
        else:
            chosen.add("itlwm" if mode == "itlwm" else "AirportItlwm")
        return
    if chipset == "broadcom":
        if not native:
            chosen.add("AirportBrcmFixup")
        # BCM94360/BCM943602 (нативный Apple AirPort): до Ventura 13.2
        # работает из коробки, на 13.3+ нужен набор OCLP.
        if native and not _needs_brcm_legacy(target_macos):
            return
        chosen.add("AMFIPass", "IOSkywalkFamily", "IO80211FamilyLegacy")
        return
    if chipset == "atheros":
        chosen.add("ATH9KFixup")


def _bluetooth_kexts(chosen: _KextList, profile: HardwareProfile) -> None:
    wifi_chipset = (profile.net.wifi_chipset or "").lower()
    if not profile.net.has_bt or profile.net.bt_native_apple:
        # нативный Apple BT (VID 05AC) — драйвера не требуются
        return
    if wifi_chipset == "intel":
        chosen.add("IntelBluetoothFirmware", "IntelBTPatcher", "BlueToolFixup")
    elif wifi_chipset == "broadcom":
        chosen.add("BlueToolFixup", "BrcmPatchRAM3", "BrcmFirmwareData")


def _input_kexts(chosen: _KextList, profile: HardwareProfile) -> None:
    if not profile.has_touchpad:
        return
    if profile.touchpad_type == "i2c":
        chosen.add("VoodooI2C", "VoodooI2CHID", "VoodooInput")
    elif profile.touchpad_type == "ps2":
        chosen.add("VoodooPS2Controller", "VoodooInput")


def select_kexts(profile: HardwareProfile, wifi_kext_mode: str = "itlwm",
                 usb_toolbox: bool = False,
                 target_macos: str = "") -> list[KextEntry]:
    """Подбирает нужный набор кекстсов по профилю железа.

    ``target_macos`` учитывает версии-специфичные кексты: AirportItlwm есть
    только до Sonoma, поэтому на Sequoia/Tahoe выбирается itlwm.
    """
    chosen = _KextList()
    # Ядро всегда: Core 2 и Sandy Bridge используют FakeSMC, новый — VirtualSMC
    chosen.add("Lilu")
    if profile.cpu.vendor == "intel" and profile.cpu.generation <= 2:
        chosen.add("FakeSMC")
    else:
        chosen.add("VirtualSMC")
    # USB-маппинг: USBToolBox.kext — инжектор для UTBMap.kext
    if usb_toolbox:
        chosen.add("USBToolBox")

    _cpu_kexts(chosen, profile)
    _storage_kexts(chosen, profile, target_macos)
    _gpu_kexts(chosen, profile)
    _audio_kexts(chosen, profile)
    _ethernet_kexts(chosen, profile, target_macos)

    wifi_quiet = wifi_kext_mode == "none"
    if not wifi_quiet:
        _wifi_kexts(chosen, profile, wifi_kext_mode, target_macos)
        _bluetooth_kexts(chosen, profile)

    _input_kexts(chosen, profile)
    # Батарея (ноутбук)
    if profile.platform == "laptop":
        chosen.add("SMCBatteryManager", "ECEnabler")
    return chosen.items


def kext_sources_ok() -> dict[str, bool]:
    """Возвращает словарь репозиториев -> доступность (заглушка, будет проверяться сетью)."""
    return {e.repo for e in KEXT_DB.values()} if False else {}
