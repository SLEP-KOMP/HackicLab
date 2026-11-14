"""Модуль сканирования и модели аппаратного профиля."""

from .models import (
    HardwareProfile,
    CPUInfo,
    GPUInfo,
    AudioInfo,
    NetInfo,
    StorageInfo,
    DisplayProfile,
)
from .windows_scanner import WindowsScanner, scan_hardware

__all__ = [
    "HardwareProfile",
    "CPUInfo",
    "GPUInfo",
    "AudioInfo",
    "NetInfo",
    "StorageInfo",
    "DisplayProfile",
    "WindowsScanner",
    "scan_hardware",
]