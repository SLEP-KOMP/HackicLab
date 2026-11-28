"""Ручной ввод железа: варианты CPU/GPU/сети и проверка выбора по источникам.

Нужен для машин, которые нельзя просканировать (собираем EFI на другом ПК)
или когда автоопределение ошибается. Каждый вариант хранит только те данные,
которые реально влияют на config.plist и подбор кекстов, а проверка
(review) опирается на наши же базы: MAX_MACOS_BY_GEN, KEXT_DB, SSDT_DB,
таблицы ig-platform-id из config_gen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..scanner.models import AudioInfo, CPUInfo, GPUInfo, HardwareProfile, NetInfo, StorageInfo


@dataclass(frozen=True)
class CpuOption:
    key: str
    group: str          # intel_desktop / intel_laptop / amd_desktop / amd_hedt / amd_laptop
    vendor: str         # intel / amd
    generation: int
    codename: str
    title: str          # что видит пользователь
    platform: str = "desktop"
    family: str = "desktop"
    cores: int = 4
    note: str = ""


def _intel(key: str, group: str, gen: int, codename: str, title: str,
           platform: str, cores: int = 4, note: str = "") -> CpuOption:
    return CpuOption(key, group, "intel", gen, codename, title, platform,
                     "laptop" if platform == "laptop" else "desktop", cores, note)


def _amd(key: str, group: str, gen: int, codename: str, title: str,
         platform: str = "desktop", family: str = "desktop", cores: int = 6,
         note: str = "") -> CpuOption:
    return CpuOption(key, group, "amd", gen, codename, title, platform, family,
                     cores, note)


CPU_OPTIONS: tuple[CpuOption, ...] = (
    # Intel Desktop
    _intel("intel-2", "intel_desktop", 2, "Sandy Bridge",
           "Intel Core i3/i5/i7-2xxx — Sandy Bridge", "desktop", 4),
    _intel("intel-3", "intel_desktop", 3, "Ivy Bridge",
           "Intel Core i3/i5/i7-3xxx — Ivy Bridge", "desktop", 4),
    _intel("intel-4", "intel_desktop", 4, "Haswell",
           "Intel Core i3/i5/i7-4xxx — Haswell", "desktop", 4),
    _intel("intel-5d", "intel_desktop", 5, "Broadwell",
           "Intel Core i5/i7-5xxx — Broadwell", "desktop", 4),
    _intel("intel-6d", "intel_desktop", 6, "Skylake",
           "Intel Core i3/i5/i7-6xxx — Skylake", "desktop", 4),
    _intel("intel-7d", "intel_desktop", 7, "Kaby Lake",
           "Intel Core i3/i5/i7-7xxx — Kaby Lake", "desktop", 4),
    _intel("intel-8d", "intel_desktop", 8, "Coffee Lake",
           "Intel Core i3/i5/i7/i9-8xxx — Coffee Lake", "desktop", 6),
    _intel("intel-9d", "intel_desktop", 9, "Coffee Lake Refresh",
           "Intel Core i5/i7/i9-9xxx — Coffee Lake Refresh", "desktop", 8),
    _intel("intel-10d", "intel_desktop", 10, "Comet Lake",
           "Intel Core i3/i5/i7/i9-10xxx — Comet Lake", "desktop", 8),
    _intel("intel-11d", "intel_desktop", 11, "Rocket Lake",
           "Intel Core i5/i7/i9-11xxx — Rocket Lake (iGPU без драйвера)",
           "desktop", 8, note="UHD 750 не поддерживается macOS — нужна dGPU AMD"),
    _intel("intel-12d", "intel_desktop", 12, "Alder Lake",
           "Intel Core i3/i5/i7/i9-12xxx — Alder Lake (iGPU без драйвера)",
           "desktop", 8, note="UHD 770 не поддерживается — нужна dGPU AMD"),
    _intel("intel-13d", "intel_desktop", 13, "Raptor Lake",
           "Intel Core i5/i7/i9-13xxx — Raptor Lake (iGPU без драйвера)",
           "desktop", 8, note="UHD 770 не поддерживается — нужна dGPU AMD"),
    _intel("intel-14d", "intel_desktop", 14, "Raptor Lake Refresh",
           "Intel Core i5/i7/i9-14xxx — Raptor Lake Refresh (iGPU без драйвера)",
           "desktop", 8, note="UHD 770 не поддерживается — нужна dGPU AMD"),
    _intel("intel-15d", "intel_desktop", 15, "Arrow Lake",
           "Intel Core Ultra 200S — Arrow Lake (iGPU без драйвера)",
           "desktop", 8, note="Xe2 без драйвера — нужна dGPU AMD; macOS 26 требует патчей"),
    # Intel Laptop
    _intel("intel-2m", "intel_laptop", 2, "Sandy Bridge",
           "Intel Core i5/i7-2xxx — Sandy Bridge (ноутбук)", "laptop", 2),
    _intel("intel-3m", "intel_laptop", 3, "Ivy Bridge",
           "Intel Core i5/i7-3xxx — Ivy Bridge (ноутбук)", "laptop", 2),
    _intel("intel-4m", "intel_laptop", 4, "Haswell",
           "Intel Core i5/i7-4xxx — Haswell (ноутбук)", "laptop", 2),
    _intel("intel-5m", "intel_laptop", 5, "Broadwell",
           "Intel Core i5/i7-5xxx — Broadwell (ноутбук)", "laptop", 2),
    _intel("intel-6m", "intel_laptop", 6, "Skylake",
           "Intel Core i3/i5/i7-6xxx — Skylake (ноутбук)", "laptop", 2),
    _intel("intel-7m", "intel_laptop", 7, "Kaby Lake",
           "Intel Core i3/i5/i7-7xxx — Kaby Lake (ноутбук)", "laptop", 4),
    _intel("intel-8kr", "intel_laptop", 8, "Kaby Lake-R",
           "Intel Core i5/i7-8xxx U — Kaby Lake-R (ноутбук)", "laptop", 4),
    _intel("intel-8wl", "intel_laptop", 8, "Whiskey Lake",
           "Intel Core i5/i7-8xxx U — Whiskey Lake (ноутбук)", "laptop", 4),
    _intel("intel-8cl", "intel_laptop", 8, "Coffee Lake-H",
           "Intel Core i7/i9-8xxx H — Coffee Lake-H (ноутбук)", "laptop", 6),
    _intel("intel-9m", "intel_laptop", 9, "Coffee Lake Refresh",
           "Intel Core i5/i7/i9-9xxx H — Coffee Lake Refresh (ноутбук)", "laptop", 8),
    _intel("intel-10cm", "intel_laptop", 10, "Comet Lake-H",
           "Intel Core i3/i5/i7-10xxx H — Comet Lake-H (ноутбук)", "laptop", 8),
    _intel("intel-10il", "intel_laptop", 10, "Ice Lake",
           "Intel Core i3/i5/i7-10xxx U/Y — Ice Lake, Iris Plus (ноутбук)", "laptop", 4),
    _intel("intel-11tl", "intel_laptop", 11, "Tiger Lake",
           "Intel Core i5/i7-11xxx — Tiger Lake (iGPU без драйвера)", "laptop", 4,
           note="iGPU Xe не поддерживается macOS — нужен dGPU или OCLP"),
    _intel("intel-12m", "intel_laptop", 12, "Alder Lake",
           "Intel Core i5/i7-12xxx — Alder Lake (iGPU без драйвера)", "laptop", 6,
           note="iGPU Xe не поддерживается macOS — нужен dGPU или OCLP"),
    _intel("intel-13m", "intel_laptop", 13, "Raptor Lake",
           "Intel Core i5/i7/i9-13xxx — Raptor Lake (iGPU без драйвера)",
           "laptop", 8, note="iGPU Xe не поддерживается macOS — нужен dGPU или OCLP"),
    _intel("intel-14m", "intel_laptop", 14, "Raptor Lake Refresh",
           "Intel Core i5/i7/i9-14xxx — Raptor Lake Refresh (iGPU без драйвера)",
           "laptop", 8, note="iGPU Xe не поддерживается macOS — нужен dGPU или OCLP"),
    _intel("intel-15m", "intel_laptop", 15, "Arrow Lake",
           "Intel Core Ultra 200H — Arrow Lake (iGPU без драйвера)",
           "laptop", 8, note="Xe2 без драйвера — нужен dGPU или OCLP"),
    # AMD Desktop
    _amd("amd-zen1d", "amd_desktop", 8, "Zen",
         "AMD Ryzen 3/5/7 1xxx — Zen", cores=6),
    _amd("amd-zenpd", "amd_desktop", 8, "Zen+",
         "AMD Ryzen 3/5/7 2xxx — Zen+", cores=6),
    _amd("amd-zen2d", "amd_desktop", 10, "Zen 2",
         "AMD Ryzen 5/7/9 3xxx — Zen 2", cores=6),
    _amd("amd-zen3d", "amd_desktop", 11, "Zen 3",
         "AMD Ryzen 5/7/9 5xxx — Zen 3", cores=8),
    _amd("amd-zen4d", "amd_desktop", 12, "Zen 4",
         "AMD Ryzen 5/7/9 7xxx — Zen 4 (AM5)", cores=8),
    _amd("amd-zen5d", "amd_desktop", 12, "Zen 5",
         "AMD Ryzen 5/7/9 9xxx — Zen 5 (AM5)", cores=8),
    # AMD Threadripper
    _amd("amd-tr3", "amd_hedt", 10, "Zen 2",
         "AMD Threadripper 3xxx — Zen 2 (HEDT)", family="hedt", cores=16),
    _amd("amd-tr5", "amd_hedt", 11, "Zen 3",
         "AMD Threadripper 5xxx — Zen 3 (HEDT)", family="hedt", cores=16),
    # AMD Laptop / APU
    _amd("amd-zen1m", "amd_laptop", 8, "Zen",
         "AMD Ryzen 3/5/7 2xxx U — Zen (APU)", platform="laptop",
         family="laptop", cores=4),
    _amd("amd-zenpm", "amd_laptop", 8, "Zen+",
         "AMD Ryzen 3/5/7 3xxx U — Zen+ (APU)", platform="laptop",
         family="laptop", cores=4),
    _amd("amd-zen2m", "amd_laptop", 10, "Zen 2",
         "AMD Ryzen 4xxx/5xxx U — Zen 2 (APU)", platform="laptop",
         family="laptop", cores=6),
    _amd("amd-zen3m", "amd_laptop", 11, "Zen 3",
         "AMD Ryzen 5xxx / PRO 5xxx — Zen 3 (APU)", platform="laptop",
         family="laptop", cores=8),
    _amd("amd-zen3pm", "amd_laptop", 11, "Zen 3+",
         "AMD Ryzen 6xxx — Zen 3+ (APU)", platform="laptop",
         family="laptop", cores=8),
    _amd("amd-zen4m", "amd_laptop", 12, "Zen 4",
         "AMD Ryzen 7xxx / AI 3xx — Zen 4 (APU)", platform="laptop",
         family="laptop", cores=8),
    _amd("amd-zen5m", "amd_laptop", 12, "Zen 5",
         "AMD Ryzen AI 3xx / 9xxx — Zen 5 (APU)", platform="laptop",
         family="laptop", cores=8),
)

CPU_BY_KEY = {option.key: option for option in CPU_OPTIONS}

#: Поколение Intel -> ключ ручного профиля. Ключи не совпадают с шаблоном
#: ``intel-<gen>d`` (у 2/3/4 нет суффикса, у ноутбучных 8 — 8kr/8wl/8cl),
#: поэтому подбор идёт по таблице, а не склейкой строки.
_INTEL_DESKTOP_KEYS = {
    0: "intel-2", 1: "intel-2", 2: "intel-2", 3: "intel-3", 4: "intel-4",
    5: "intel-5d", 6: "intel-6d", 7: "intel-7d", 8: "intel-8d",
    9: "intel-9d", 10: "intel-10d", 11: "intel-11d", 12: "intel-12d",
    13: "intel-13d", 14: "intel-14d", 15: "intel-15d",
}
_INTEL_LAPTOP_KEYS = {
    0: "intel-2m", 1: "intel-2m", 2: "intel-2m", 3: "intel-3m", 4: "intel-4m",
    5: "intel-5m", 6: "intel-6m", 7: "intel-7m", 8: "intel-8kr",
    9: "intel-9m", 10: "intel-10cm", 11: "intel-11tl", 12: "intel-12m",
    13: "intel-13m", 14: "intel-14m", 15: "intel-15m",
}


def intel_option_key(generation: int, laptop: bool = False) -> str:
    """Ключ Intel-профиля для поколения из сканирования.

    Core 2/Nehalem (0/1) ближе всего к Sandy Bridge, а не к Coffee Lake:
    иначе ручная форма подставляла современные кексты и macOS.
    """
    try:
        gen = int(generation or 0)
    except (TypeError, ValueError):
        gen = 0
    table = _INTEL_LAPTOP_KEYS if laptop else _INTEL_DESKTOP_KEYS
    if gen in table:
        return table[gen]
    return "intel-15m" if laptop else "intel-15d"
CPU_GROUPS = (
    ("intel_desktop", "CPU — Intel, настольный"),
    ("intel_laptop", "CPU — Intel, ноутбук"),
    ("amd_desktop", "CPU — AMD, настольный"),
    ("amd_hedt", "CPU — AMD Threadripper"),
    ("amd_laptop", "CPU — AMD APU / ноутбук"),
)


@dataclass(frozen=True)
class GpuOption:
    key: str
    title: str
    vendor: str = ""
    device_id: str = ""
    integrated: bool = False
    note: str = ""


GPU_OPTIONS: tuple[GpuOption, ...] = (
    GpuOption("", "Авто / как iGPU процессора"),
    GpuOption("5916", "Intel HD 620 (Kaby Lake)", "intel", "5916", True),
    GpuOption("591b", "Intel HD 630 (Kaby Lake, ноутбук)", "intel", "591B", True),
    GpuOption("5917", "Intel HD 620 (Kaby Lake-R)", "intel", "5917", True),
    GpuOption("3ea0", "Intel UHD 620 (Whiskey Lake)", "intel", "3EA0", True),
    GpuOption("3e98", "Intel UHD 630 (Coffee Lake)", "intel", "3E98", True),
    GpuOption("9bca", "Intel UHD 620 (Comet Lake)", "intel", "9BCA", True),
    GpuOption("9bc4", "Intel UHD 630 (Comet Lake)", "intel", "9BC4", True),
    GpuOption("0166", "Intel HD 4000 (Ivy Bridge)", "intel", "0166", True),
    GpuOption("0416", "Intel HD 4600 (Haswell)", "intel", "0416", True),
    GpuOption("1916", "Intel HD 520 (Skylake)", "intel", "1916", True),
    GpuOption("amd", "AMD Radeon (iGPU или дискретная)", "amd", "", False),
    GpuOption("6fdf", "AMD Radeon RX 580 2048SP", "amd", "6FDF", False,
              "Нет драйвера: патч device-id или правка VBIOS на RX 570"),
    GpuOption("731f", "AMD Radeon RX 5700 XT (Navi 10)", "amd", "731F", False,
              "Navi 10: нужен agdpmod=pikera"),
    GpuOption("66af", "AMD Radeon VII (Vega 20)", "amd", "66AF", False,
              "Vega 20: нативно, SMBIOS iMacPro1,1"),
    GpuOption("7340", "AMD Radeon RX 5500 XT (Navi 14)", "amd", "7340", False,
              "Navi 14: macOS 10.15.4+"),
    GpuOption("73ff", "AMD Radeon RX 6400 / 6500 XT (Navi 24)", "amd", "73FF", False,
              "Драйвера нет: macOS не поддерживает Navi 24"),
    GpuOption("744c", "AMD Radeon RX 7900 XTX (Navi 31)", "amd", "744C", False,
              "Драйвера нет: macOS не поддерживает Navi 31"),
    GpuOption("7480", "AMD Radeon RX 7600 (Navi 33)", "amd", "7480", False,
              "Драйвера нет: macOS не поддерживает Navi 33"),
    GpuOption("nvidia", "NVIDIA (macOS не поддерживает)", "nvidia", "", False,
              "Отключите в BIOS или выберите «отключить dGPU» в мастере"),
)

GPU_BY_KEY = {option.key: option for option in GPU_OPTIONS}

ETHERNET_OPTIONS = (
    ("", "Нет / неизвестно"),
    ("rtl8111", "Realtek RTL8111 / RTL8168"),
    ("rtl8125", "Realtek RTL8125 (2.5G)"),
    ("i219", "Intel I219-V / I219-LM"),
    ("i225", "Intel I225-V (2.5G)"),
    ("i226", "Intel I226-V (2.5G)"),
    ("i211", "Intel I211-AT"),
)

WIFI_OPTIONS = (
    ("", "Нет"),
    ("intel", "Intel: AX210 / AX211 / AX200 / AX201, 9560 / 9260 / 8265 / 7260"),
    ("broadcom", "Broadcom: BCM94360 / 943602 (нативно), BCM94352 / 94350 (кесты)"),
    ("atheros", "Atheros: AR9280 / 9285 / 9287, AR9462 / 9485 / 9565"),
    ("mediatek", "MediaTek MT7921 / MT7922 / MT7925 — драйвера нет"),
    ("realtek", "Realtek RTL8821 / 8822 / 8852 — драйвера нет"),
    ("qualcomm", "Qualcomm Atheros QCA6174 / QCA9377 — драйвера нет"),
)

WIFI_NOTES = {
    "intel": "itlwm + HeliPort (AirportItlwm — до Sonoma 14.4); BT: IntelBluetoothFirmware",
    "broadcom": "BCM94360 нативно до Ventura, Sonoma+ — OCLP; BCM94352/94350 — AirportBrcmFixup",
    "atheros": "AR92xx нативно до High Sierra; AR9462/9485/9565 — ATH9KFixup до Mojave",
    "mediatek": "драйвера нет: замена на Intel/Broadcom или USB-адаптер",
    "realtek": "драйвера нет: PCIe-карты не заводятся, только USB-пакет chris1111",
    "qualcomm": "штатного драйвера нет: только экспериментальный Ath10kMac",
}

TOUCHPAD_OPTIONS = (("ps2", "PS/2"), ("i2c", "I2C (VoodooI2C)"), ("none", "Нет"))

# Подписи вариантов показываются в списках ручной сборки, поэтому в английском
# интерфейсе русские пометки нужно переводить. Большая часть названий — модели
# и кодовые имена, они одинаковы на обоих языках; здесь только отличия.
_EN_TITLES = {
    "Авто / как iGPU процессора": "Auto / as CPU iGPU",
    "AMD Radeon (iGPU или дискретная)": "AMD Radeon (iGPU or discrete)",
    "NVIDIA (macOS не поддерживает)": "NVIDIA (not supported by macOS)",
    "MediaTek (MT7925 и др.) — только USB-замена":
        "MediaTek (MT7925 etc.) — USB adapter only",
    "MediaTek MT7921 / MT7922 / MT7925 — драйвера нет":
        "MediaTek MT7921 / MT7922 / MT7925 — no driver",
    "Realtek — в macOS драйвера нет": "Realtek — no macOS driver",
    "Realtek RTL8821 / 8822 / 8852 — драйвера нет":
        "Realtek RTL8821 / 8822 / 8852 — no driver",
    "Qualcomm Atheros QCA6174 / QCA9377 — драйвера нет":
        "Qualcomm Atheros QCA6174 / QCA9377 — no driver",
    "Broadcom: BCM94360 / 943602 (нативно), BCM94352 / 94350 (кесты)":
        "Broadcom: BCM94360 / 943602 (native), BCM94352 / 94350 (kexts)",
    "Atheros: AR9280 / 9285 / 9287, AR9462 / 9485 / 9565":
        "Atheros: AR9280 / 9285 / 9287, AR9462 / 9485 / 9565",
    "Intel: AX210 / AX211 / AX200 / AX201, 9560 / 9260 / 8265 / 7260":
        "Intel: AX210 / AX211 / AX200 / AX201, 9560 / 9260 / 8265 / 7260",
    "Нет": "None",
    "Нет / неизвестно": "None / unknown",
    "itlwm + HeliPort (AirportItlwm — до Sonoma 14.4); BT: IntelBluetoothFirmware":
        "itlwm + HeliPort (AirportItlwm up to Sonoma 14.4); BT: IntelBluetoothFirmware",
    "BCM94360 нативно до Ventura, Sonoma+ — OCLP; BCM94352/94350 — AirportBrcmFixup":
        "BCM94360 native up to Ventura, Sonoma+ via OCLP; BCM94352/94350 need AirportBrcmFixup",
    "AR92xx нативно до High Sierra; AR9462/9485/9565 — ATH9KFixup до Mojave":
        "AR92xx native up to High Sierra; AR9462/9485/9565 via ATH9KFixup up to Mojave",
    "драйвера нет: замена на Intel/Broadcom или USB-адаптер":
        "no driver: replace with Intel/Broadcom or use a USB adapter",
    "драйвера нет: PCIe-карты не заводятся, только USB-пакет chris1111":
        "no driver: PCIe cards do not work, only the chris1111 USB package",
    "штатного драйвера нет: только экспериментальный Ath10kMac":
        "no stock driver: only the experimental Ath10kMac",
}

_EN_SNIPPETS = (
    ("(ноутбук)", "(laptop)"),    ("(Kaby Lake, ноутбук)", "(Kaby Lake, laptop)"),
    ("(iGPU без драйвера)", "(iGPU without driver)"),
    ("Драйвера нет: macOS не поддерживает ", "No driver: macOS does not support "),
    ("Нет драйвера: ", "No driver: "),
    ("нужна dGPU AMD", "an AMD dGPU is required"),
    ("нужен dGPU или OCLP", "a dGPU or OCLP is required"),
)

# Замечания обзора ручной сборки: те же тексты для английского интерфейса.
_EN_ISSUES = {
    "iGPU 11-го поколения и новее не имеет драйвера macOS":
        "11th-gen and newer iGPU has no macOS driver",
    "NVIDIA не поддерживается macOS — отключите dGPU":
        "NVIDIA is not supported by macOS — disable the dGPU",
    "Для этого Wi-Fi нет драйвера: USB-адаптер или замена модуля":
        "No driver for this Wi-Fi: use a USB adapter or replace the module",
    "Поддержка Atheros ограничена старыми картами":
        "Atheros support is limited to older cards",
    "AirportItlwm не существует для этой macOS — будет itlwm":
        "AirportItlwm does not exist for this macOS — itlwm will be used",
    "Тачпад отключён в выборе": "Touchpad is disabled in the selection",
    "Нужны VoodooI2C + сателлит по модели тачпада":
        "VoodooI2C plus a model-specific satellite kext is required",
    "Будут SSDT-PNLF (яркость) и SSDT-EC-USBX (батарея/питание)":
        "SSDT-PNLF (brightness) and SSDT-EC-USBX (battery/power) will be added",
    "NVMeFix добавлен": "NVMeFix added",
    "Thunderbolt: проверьте BIOS и IOMMU": "Thunderbolt: check BIOS and IOMMU",
    "Кодек не в таблице layout — подберите alcid вручную":
        "Codec is not in the layout table — pick alcid manually",
    "Dortania: iMacPro1,1/MacPro7,1 на не-Mac железе могут потребовать "
    "правки питания — при проблемах со сном смотрите Fixing Power Management":
        "Dortania: iMacPro1,1/MacPro7,1 on non-Mac hardware may need power "
        "management tweaks — see Fixing Power Management if sleep misbehaves",
}


def ui_issue(text: str, lang: str = "ru") -> str:
    """Замечание обзора для текущего языка интерфейса."""
    if lang != "en":
        return text
    exact = _EN_ISSUES.get(text)
    if exact is not None:
        return exact
    out = str(text)
    if out.startswith("Модель ") and " не поддерживает " in out:
        out = (out.replace("Модель ", "Model ", 1)
                  .replace(" не поддерживает ", " does not support ", 1)
                  .replace(" — она не появится в этой системе",
                           " — it will not appear in this macOS"))
        return out
    for ru, en in _EN_SNIPPETS:
        out = out.replace(ru, en)
    return out


def ui_title(text: str, lang: str = "ru") -> str:
    """Подпись варианта для текущего языка интерфейса."""
    if lang != "en":
        return text
    exact = _EN_TITLES.get(text)
    if exact is not None:
        return exact
    out = str(text)
    for ru, en in _EN_SNIPPETS:
        out = out.replace(ru, en)
    return out


@dataclass
class ManualSelection:
    cpu: str = "intel-8d"
    laptop: bool = False
    cores: int = 0
    gpu: str = ""
    audio_codec: str = ""
    ethernet: str = ""
    wifi: str = ""
    nvme: bool = True
    thunderbolt: bool = False
    touchpad: str = "ps2"
    extra: dict = field(default_factory=dict)


def _cpu_name(option: CpuOption) -> str:
    return f"{option.title.split(' — ')[0].strip()} ({option.codename})"


def build_profile(selection: ManualSelection) -> HardwareProfile:
    """Собирает профиль железа из ручного выбора."""
    option = CPU_BY_KEY.get(selection.cpu) or CPU_OPTIONS[0]
    platform = "laptop" if selection.laptop else option.platform
    profile = HardwareProfile(platform=platform)
    cores = selection.cores or option.cores
    profile.cpu = CPUInfo(
        name=_cpu_name(option), vendor=option.vendor, generation=option.generation,
        codename=option.codename, oc_platform=option.codename,
        family="laptop" if platform == "laptop" else option.family,
        core_count=cores, thread_count=cores * 2,
    )
    gpu = GPU_BY_KEY.get(selection.gpu) or GPU_OPTIONS[0]
    if gpu.vendor == "intel":
        profile.igpu = GPUInfo(name=gpu.title.split(" (")[0], vendor="intel",
                               device_id=gpu.device_id, is_integrated=True)
    elif gpu.vendor in ("amd", "nvidia"):
        profile.dgpu = GPUInfo(name=gpu.title.split(" (")[0], vendor=gpu.vendor,
                               device_id=gpu.device_id)
    elif option.vendor == "intel" and 2 <= option.generation <= 10:
        # «Авто» на Intel означает встроенную графику: без этого профиль
        # оставался без iGPU и config.plist не получал ig-platform-id.
        profile.igpu = GPUInfo(name=f"Intel iGPU ({option.codename})",
                               vendor="intel", is_integrated=True)
    audio_codec = (selection.audio_codec or "").strip().upper()
    profile.audio = AudioInfo(codec=audio_codec, name=audio_codec)
    if audio_codec:
        from .audio_layouts import layouts_for, recommended
        candidates = layouts_for(audio_codec)
        profile.audio.layout_candidates = list(candidates)
        profile.audio.layout_id = recommended(audio_codec)
    wifi = (selection.wifi or "").lower()
    has_bt = wifi in ("intel", "broadcom")
    profile.net = NetInfo(eth_chipset=selection.ethernet,
                          eth_name=selection.ethernet.upper(),
                          wifi_chipset=wifi,
                          bt_chipset=wifi if has_bt else "",
                          has_bt=has_bt)
    profile.storage = StorageInfo(nvme_present=bool(selection.nvme),
                                  sata_present=True)
    profile.has_thunderbolt = bool(selection.thunderbolt)
    profile.has_touchpad = platform == "laptop" and selection.touchpad != "none"
    profile.touchpad_type = selection.touchpad if profile.has_touchpad else "none"
    return profile


def smbios_options(profile: HardwareProfile) -> tuple[str, ...]:
    """Модели, которые имеет смысл предлагать вручную для этого железа."""
    if getattr(profile, "platform", "") == "laptop":
        return ("MacBookPro14,1", "MacBookPro15,2", "MacBookPro16,1")
    cpu = getattr(profile, "cpu", None)
    if str(getattr(cpu, "vendor", "")).lower() == "amd":
        # У AMD нет iGPU: годятся только модели, где всё рисует дискретка.
        return ("iMacPro1,1", "MacPro7,1")
    return ("iMac18,3", "iMac19,1", "iMac20,1", "MacPro7,1")


def supports_model(model: str, macos_target: str) -> bool:
    """Поддерживает ли принудительная модель выбранную macOS (неизвестная — да)."""
    from .smbios_support import supports
    return supports(model, macos_target or "")


def review(profile: HardwareProfile, macos_target: str = "",
           wifi_mode: str = "itlwm", smbios_override: str = "") -> dict:
    """Проверка выбора по нашим базам: что получится и где будут проблемы."""
    from .kexts import KEXT_DB, select_kexts, smbios_model_for
    from .oc_platforms import MAX_MACOS_BY_GEN
    from .ssdt_logics import required_ssdts

    gen = profile.cpu.generation
    max_macos = MAX_MACOS_BY_GEN.get(gen, "Sonoma")
    smbios = smbios_override or smbios_model_for(profile, macos_target)
    kexts = [entry.name for entry in select_kexts(profile, wifi_mode,
                                                  target_macos=macos_target)]
    ssdts = [entry.name for entry in required_ssdts(profile)]
    issues: list[dict] = []

    def add(level: str, key: str, text: str):
        issues.append({"level": level, "key": key, "text": text})

    if "unsupported" in max_macos.lower():
        add("err", "max_macos", max_macos)
    if gen >= 11 and profile.cpu.vendor == "intel" and profile.igpu:
        add("warn", "igpu_tiger", "iGPU 11-го поколения и новее не имеет драйвера macOS")
    if profile.dgpu and profile.dgpu.vendor == "nvidia":
        add("err", "nvidia", "NVIDIA не поддерживается macOS — отключите dGPU")
    if profile.net.wifi_chipset in ("mediatek", "realtek"):
        add("err", "wifi_unsupported",
            "Для этого Wi-Fi нет драйвера: USB-адаптер или замена модуля")
    if profile.net.wifi_chipset == "atheros":
        add("warn", "wifi_atheros", "Поддержка Atheros ограничена старыми картами")
    if profile.net.wifi_chipset == "intel" and wifi_mode == "airport" and macos_target:
        from .kexts import _macos_idx
        if _macos_idx(macos_target) > _macos_idx("sonoma"):
            add("warn", "airport_sequoia",
                "AirportItlwm не существует для этой macOS — будет itlwm")
    if profile.platform == "laptop":
        if not profile.has_touchpad:
            add("info", "touchpad_off", "Тачпад отключён в выборе")
        if profile.touchpad_type == "i2c":
            add("info", "touchpad_i2c", "Нужны VoodooI2C + сателлит по модели тачпада")
        add("info", "laptop_backlight",
            "Будут SSDT-PNLF (яркость) и SSDT-EC-USBX (батарея/питание)")
    if profile.storage.nvme_present and "NVMeFix" in kexts:
        add("ok", "nvme", "NVMeFix добавлен")
    if profile.has_thunderbolt:
        add("info", "thunderbolt", "Thunderbolt: проверьте BIOS и IOMMU")
    if profile.audio.codec and not profile.audio.layout_id:
        add("warn", "audio_layout", "Кодек не в таблице layout — подберите alcid вручную")
    if smbios_override and not supports_model(smbios_override, macos_target):
        add("err", "smbios_range",
            f"Модель {smbios_override} не поддерживает {macos_target or 'эту macOS'} — она не появится в этой системе")
    if profile.cpu.vendor == "amd" and smbios in ("iMacPro1,1", "MacPro7,1"):
        add("info", "smbios_pm",
            "Dortania: iMacPro1,1/MacPro7,1 на не-Mac железе могут потребовать "
            "правки питания — при проблемах со сном смотрите Fixing Power Management")
    return {
        "max_macos": max_macos,
        "smbios": smbios,
        "kexts": kexts,
        "kext_count": len(kexts),
        "ssdts": ssdts,
        "issues": issues,
        "generation": gen,
        "codename": profile.cpu.codename,
        "platform": profile.platform,
        "known_kexts": sum(1 for name in kexts if name in KEXT_DB),
    }


def check_macos(profile: HardwareProfile, target: str) -> tuple[bool, str]:
    """Поддерживает ли железо выбранную macOS (по потолку поколения)."""
    from .kexts import _macos_idx
    from .oc_platforms import MAX_MACOS_BY_GEN

    max_macos = MAX_MACOS_BY_GEN.get(profile.cpu.generation, "Sonoma")
    if "unsupported" in max_macos.lower():
        return False, max_macos
    return _macos_idx(target) <= _macos_idx(max_macos), max_macos
