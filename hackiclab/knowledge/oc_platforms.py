"""OpenCore-платформы и карта поколений CPU -> платформа OpenCore."""

from __future__ import annotations

from ..scanner.models import HardwareProfile

# (generation) -> codename для OC platform
OC_PLATFORMS: dict[int, str] = {
    15: "Arrow Lake",
    14: "Raptor Lake",
    13: "Raptor Lake",
    12: "Alder Lake",
    11: "Tiger Lake",
    10: "Ice Lake",
    9: "Coffee Lake",
    8: "Coffee Lake",
    7: "Kaby Lake",
    6: "Skylake",
    5: "Broadwell",
    4: "Haswell",
    3: "Ivy Bridge",
    2: "Sandy Bridge",
    1: "Nehalem/Westmere",
}


def oc_platform_for(profile: HardwareProfile) -> str:
    """Возвращает OpenCore-платформу для профиля CPU."""
    if profile.cpu.vendor == "amd":
        return "Ryzen"
    if profile.cpu.oc_platform:
        return profile.cpu.oc_platform
    return OC_PLATFORMS.get(profile.cpu.generation, "Unknown")


# Максимальная macOS, до которой поколение доживает нативно.
# Сверено с официальным списком поддерживаемых Mac:
#   Sequoia 15 — iMac 2019+, MacBook Pro 2018+, Mac mini 2018+, iMac Pro 2017;
#   Sonoma 14 — модели 2018+; Ventura 13 — модели 2017+ (Kaby Lake);
#   Monterey 12 — модели 2015+ (Broadwell/Skylake); Big Sur 11 — 2013+.
# Драйверы iGPU Haswell/Broadwell/Skylake удалены в Ventura, поэтому для них
# потолок — Monterey, даже если SMBIOS можно подставить новее.
MAX_MACOS_BY_GEN: dict[int, str] = {
    1: "High Sierra",   # Nehalem/Westmere: 2010–2011 Mac Pro
    2: "High Sierra",   # Sandy Bridge: 2011 Mac, Catalina уже без них
    3: "Catalina",      # Ivy Bridge: 2012 Mac, Big Sur уже без них
    4: "Monterey",      # Haswell: iGPU-драйвер живёт до Monterey
    5: "Monterey",      # Broadwell
    6: "Monterey",      # Skylake (кроме Skylake-X в iMac Pro)
    7: "Ventura",       # Kaby Lake: 2017 Mac, Sonoma их уже не поддерживает
    8: "Sequoia",       # Coffee Lake: MacBook Pro 2018 / mini 2018
    9: "Sequoia",       # Coffee Lake Refresh: iMac 2019
    10: "Sequoia",      # Comet Lake: iMac 2020
    11: "Sonoma",       # Tiger Lake: iGPU без драйвера, нужен dGPU
    12: "Sonoma",       # Alder Lake: только с dGPU и патчами ядра
    13: "Sonoma",       # Raptor Lake
    14: "Sonoma",       # Raptor Lake Refresh
    15: "Sequoia",      # Arrow Lake: Tahoe 26 уже только Apple Silicon
}

# AMD не имеет Apple-платформы: потолок задаётся патчами AMD Vanilla и GPU.
MAX_MACOS_AMD = "Sequoia"


def max_macos_for(profile: HardwareProfile) -> str:
    """Потолок macOS для профиля: отдельная логика для AMD и Skylake-X."""
    cpu = getattr(profile, "cpu", None)
    if cpu is None:
        return "Sequoia"
    if (getattr(cpu, "vendor", "") or "").lower() == "amd":
        return MAX_MACOS_AMD
    name = str(getattr(cpu, "name", "") or "").lower()
    if "skylake-x" in name or "skylake x" in name or "i9-79" in name or "i9-98" in name:
        # Skylake-X/W живут в iMac Pro 2017 и поддерживаются вплоть до Sequoia
        return "Sequoia"
    if "xeon" in name and ("w-" in name or "skylake" in name):
        return "Sequoia"
    return MAX_MACOS_BY_GEN.get(getattr(cpu, "generation", 0) or 0, "Sonoma")

# Версии macOS с их кодовыми именами
MACOS_VERSIONS: list[dict] = [
    {"name": "macOS Tahoe", "version": "26", "release": 2025},
    {"name": "macOS Sequoia", "version": "15", "release": 2024},
    {"name": "macOS Sonoma", "version": "14", "release": 2023},
    {"name": "macOS Ventura", "version": "13", "release": 2022},
    {"name": "macOS Monterey", "version": "12", "release": 2021},
    {"name": "macOS Big Sur", "version": "11", "release": 2020},
    {"name": "macOS Catalina", "version": "10.15", "release": 2019},
    {"name": "macOS Mojave", "version": "10.14", "release": 2018},
    {"name": "macOS High Sierra", "version": "10.13", "release": 2017},
]
