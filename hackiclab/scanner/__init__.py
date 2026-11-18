"""Модуль сканирования и модели аппаратного профиля.

Сканер выбирается по платформе: на Windows — WMI/PnP, на macOS — system_profiler.
Остальной код работает с общим ``HardwareProfile`` и не знает о разнице.
"""

from __future__ import annotations

import sys

from .models import (
    AudioInfo,
    CPUInfo,
    DisplayProfile,
    GPUInfo,
    HardwareProfile,
    NetInfo,
    StorageInfo,
)

if sys.platform == "darwin":
    from .macos_scanner import MacOSScanner as Scanner
    from .macos_scanner import scan_hardware
else:
    from .windows_scanner import WindowsScanner as Scanner
    from .windows_scanner import scan_hardware

__all__ = [
    "AudioInfo",
    "CPUInfo",
    "DisplayProfile",
    "GPUInfo",
    "HardwareProfile",
    "NetInfo",
    "Scanner",
    "StorageInfo",
    "scan_hardware",
]
