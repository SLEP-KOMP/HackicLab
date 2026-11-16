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


# Возможные macOS-версии для каждого поколения (максимальная поддерживаемая)
MAX_MACOS_BY_GEN: dict[int, str] = {
    1: "High Sierra",
    2: "Catalina",
    3: "Big Sur",
    4: "Monterey",
    5: "Big Sur",
    6: "Big Sur",
    7: "Sonoma",
    8: "Sonoma",
    9: "Sonoma",
    10: "Ventura",
    11: "Unsupported (no iGPU driver)",
    12: "Sonoma",
    13: "Sonoma",
    14: "Sonoma",
    15: "Tahoe",
}

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
