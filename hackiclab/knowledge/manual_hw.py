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
    ("intel", "Intel (AX200 / AX210 / AC-9260 / AC-8265)"),
    ("broadcom", "Broadcom (BCM94360 / BCM943602)"),
    ("atheros", "Atheros / Qualcomm"),
    ("mediatek", "MediaTek (MT7925 и др.) — только USB-замена"),
    ("realtek", "Realtek — в macOS драйвера нет"),
)

WIFI_NOTES = {
    "intel": "itlwm + HeliPort или AirportItlwm (до Sonoma)",
    "broadcom": "нативные BCM94360/602 работают без патчей, остальные — AirportBrcmFixup",
    "atheros": "ATH9KFixup, только старые карты",
    "mediatek": "драйвера нет: нужен USB-адаптер или замена модуля",
    "realtek": "драйвера нет: нужен USB-адаптер или замена модуля",
}

TOUCHPAD_OPTIONS = (("ps2", "PS/2"), ("i2c", "I2C (VoodooI2C)"), ("none", "Нет"))


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
        profile.dgpu = GPUInfo(name=gpu.title.split(" (")[0], vendor=gpu.vendor)
    audio_codec = (selection.audio_codec or "").strip().upper()
    profile.audio = AudioInfo(codec=audio_codec, name=audio_codec)
    if audio_codec:
        from .audio_layouts import layouts_for, recommended
        candidates = layouts_for(audio_codec)
        profile.audio.layout_candidates = list(candidates)
        profile.audio.layout_id = recommended(audio_codec)
    profile.net = NetInfo(eth_chipset=selection.ethernet,
                          eth_name=selection.ethernet.upper(),
                          wifi_chipset=selection.wifi)
    profile.storage = StorageInfo(nvme_present=bool(selection.nvme),
                                  sata_present=True)
    profile.has_thunderbolt = bool(selection.thunderbolt)
    profile.has_touchpad = platform == "laptop" and selection.touchpad != "none"
    profile.touchpad_type = selection.touchpad if profile.has_touchpad else "none"
    return profile


def review(profile: HardwareProfile, macos_target: str = "",
           wifi_mode: str = "itlwm") -> dict:
    """Проверка выбора по нашим базам: что получится и где будут проблемы."""
    from .kexts import KEXT_DB, select_kexts, smbios_model_for
    from .oc_platforms import MAX_MACOS_BY_GEN
    from .ssdt_logics import required_ssdts

    gen = profile.cpu.generation
    max_macos = MAX_MACOS_BY_GEN.get(gen, "Sonoma")
    smbios = smbios_model_for(profile, macos_target)
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
