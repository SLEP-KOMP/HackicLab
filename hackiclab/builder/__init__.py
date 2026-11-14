"""Модуль сборки EFI: загрузка компонентов, генерация config.plist, запись структуры."""

from .fetcher import GitHubFetcher, download_asset, download_bytes
from .config_gen import generate_config_plist, BuildOptions
from .smbios_gen import SMBIOSData, generate_smbios
from .efi_layout import EFILayout, EFIBuildResult, extract_zip_clean
from .builder import EFIBuilder, BuildPlan

__all__ = [
    "GitHubFetcher",
    "download_asset",
    "download_bytes",
    "generate_config_plist",
    "BuildOptions",
    "SMBIOSData",
    "generate_smbios",
    "EFILayout",
    "EFIBuildResult",
    "extract_zip_clean",
    "EFIBuilder",
    "BuildPlan",
]