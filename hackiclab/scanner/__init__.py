"""Модуль сканирования и модели аппаратного профиля."""

from .models import (
    AudioInfo,
    CPUInfo,
    DisplayProfile,
    GPUInfo,
    HardwareProfile,
    NetInfo,
    StorageInfo,
)
from .windows_scanner import WindowsScanner, scan_hardware

__all__ = [
    "AudioInfo",
    "CPUInfo",
    "DisplayProfile",
    "GPUInfo",
    "HardwareProfile",
    "NetInfo",
    "StorageInfo",
    "WindowsScanner",
    "scan_hardware",
]
