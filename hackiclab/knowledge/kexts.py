"""Кекст-база и логика подбора кекстсов под аппаратный профиль.

Источники логики: hackmate (kexts.py) + OpCore-Simplify (kext_maestro),
адаптировано и расширено.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

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
    "AppleIntelI210Ethernet": KextEntry("AppleIntelI210Ethernet", "donatengit/AppleIntelI210Ethernet", "AppleIntelI210-", "Intel I211/I210"),
    "RealtekRTL8111": KextEntry("RealtekRTL8111", "Mieze/RTL8111_driver_for_OS_X", "RealtekRTL8111-", "Realtek RTL8111/RTL8168"),
    "RealtekRTL8125": KextEntry("LucyRTL8125Ethernet", "Mieze/LucyRTL8125Ethernet", "LucyRTL8125Ethernet-", "Realtek RTL8125 2.5GbE"),
    "NullEthernet": KextEntry("NullEthernet", "jcreed69/NullEthernet", "NullEthernet", "Заглушка Ethernet для iMessage"),

    "itlwm": KextEntry("itlwm", "OpenIntelWireless/itlwm", "itlwm_", "Intel WiFi (нужен HeliPort)"),
    "AirportItlwm": KextEntry("AirportItlwm", "OpenIntelWireless/itlwm", "AirportItlwm_", "Intel WiFi как нативный Airport", os_min="sonoma"),
    "AirportBrcmFixup": KextEntry("AirportBrcmFixup", "acidanthera/AirportBrcmFixup", "AirportBrcmFixup-", "Broadcom WiFi патчи"),
    "ATH9KFixup": KextEntry("ATH9KFixup", "black-dragon74/ATH9KFixup", "release", "Atheros WiFi патчи"),

    "IntelBluetoothFirmware": KextEntry("IntelBluetoothFirmware", "OpenIntelWireless/IntelBluetoothFirmware", "IntelBluetooth", "Intel BT"),
    "IntelBTPatcher": KextEntry("IntelBTPatcher", "OpenIntelWireless/IntelBluetoothFirmware", "IntelBluetooth", "Intel BT патчи", internal=True),
    "BlueToolFixup": KextEntry("BlueToolFixup", "acidanthera/BrcmPatchRAM", "BrcmPatchRAM-", "BT stack fix 12+", internal=True),
    "BrcmPatchRAM3": KextEntry("BrcmPatchRAM3", "acidanthera/BrcmPatchRAM", "BrcmPatchRAM-", "Broadcom BT (12+)", internal=True),
    "BrcmFirmwareData": KextEntry("BrcmFirmwareData", "acidanthera/BrcmPatchRAM", "BrcmPatchRAM-", "Broadcom BT firmware", internal=True),

    "NootRX": KextEntry("NootRX", "ChefKissInc/NootRX", "NootRX-", "RX 6600/6700/6800/6900 (Navi 2x) на Ventura+"),
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


def smbios_model_for(profile: HardwareProfile) -> str:
    if profile.cpu.vendor == "amd":
        return "MacPro7,1" if profile.platform == "desktop" else "MacBookPro15,2"
    key = (profile.cpu.generation, profile.platform)
    return SMBIOS_MAP.get(key, "MacBookPro15,2")


def select_kexts(profile: HardwareProfile, wifi_kext_mode: str = "itlwm") -> list[KextEntry]:
    """Подбирает нужный набор кекстсов по профилю железа."""
    selected: list[KextEntry] = []
    seen: set[str] = set()

    def add(*names: str):
        for n in names:
            e = KEXT_DB.get(n)
            if e and n not in seen:
                seen.add(n)
                selected.append(e)
            elif not e and n not in seen:
                seen.add(n)  # отмечено, но неизвестно в БД

    # Ядро всегда
    add("Lilu", "VirtualSMC")

    # CPU/платформа
    if profile.cpu.vendor == "amd":
        add("SMCAMDProcessor", "CryptexFixup", "RestrictEvents")
    else:
        add("RestrictEvents", "CPUFriend", "NVMeFix")
        if profile.cpu.generation >= 12:
            add("CpuTopologyRebuild")

    # GPU
    g = profile.dgpu if profile.dgpu else (profile.igpu if profile.igpu else None)
    if g:
        if g.vendor == "intel" or (profile.igpu and profile.igpu.vendor == "intel"):
            add("WhateverGreen")
        if g.vendor == "amd":
            add("WhateverGreen", "RadeonSensor", "SMCRadeonGPU")
            if profile.cpu.vendor == "amd":
                add("NootRX")

    # Аудио
    if profile.audio.codec:
        add("AppleALC")

    # Сеть
    el = (profile.net.eth_chipset or "").lower()
    if "i219" in el or "i218" in el or "i217" in el:
        add("IntelMausiEthernet")
    elif "i211" in el or "i210" in el:
        add("AppleIntelI210Ethernet")
    elif "i225" in el or "i226" in el:
        add("AppleIGC")
    elif "rtl8125" in el:
        add("RealtekRTL8125")
    elif "rtl" in el:
        add("RealtekRTL8111")

    # WiFi
    w = (profile.net.wifi_chipset or "").lower()
    if w == "intel":
        add("itlwm" if wifi_kext_mode == "itlwm" else "AirportItlwm")
    elif w == "broadcom":
        add("AirportBrcmFixup")
    elif w == "atheros":
        add("ATH9KFixup")

    # Bluetooth
    if profile.net.has_bt:
        if w == "intel":
            add("IntelBluetoothFirmware", "IntelBTPatcher", "BlueToolFixup")
        elif w == "broadcom":
            add("BlueToolFixup", "BrcmPatchRAM3", "BrcmFirmwareData")

    # Тачпад
    if profile.has_touchpad:
        if profile.touchpad_type == "i2c":
            add("VoodooI2C", "VoodooI2CHID", "VoodooInput")
        elif profile.touchpad_type == "ps2":
            add("VoodooPS2Controller", "VoodooInput")

    # Батарея (ноутбук)
    if profile.platform == "laptop":
        add("SMCBatteryManager", "ECEnabler")

    return selected


def kext_sources_ok() -> dict[str, bool]:
    """Возвращает словарь репозиториев -> доступность (заглушка, будет проверяться сетью)."""
    return {e.repo for e in KEXT_DB.values()} if False else {}