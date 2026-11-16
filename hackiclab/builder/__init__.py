"""Модуль сборки EFI: загрузка компонентов, генерация config.plist, запись структуры."""

from .builder import BuildPlan, EFIBuilder
from .config_gen import BuildOptions, generate_config_plist
from .efi_layout import EFIBuildResult, EFILayout, extract_zip_clean
from .fetcher import GitHubFetcher, download_asset, download_bytes
from .smbios_gen import SMBIOSData, generate_smbios

__all__ = [
    "BuildOptions",
    "BuildPlan",
    "EFIBuildResult",
    "EFIBuilder",
    "EFILayout",
    "GitHubFetcher",
    "SMBIOSData",
    "download_asset",
    "download_bytes",
    "extract_zip_clean",
    "generate_config_plist",
    "generate_smbios",
]
