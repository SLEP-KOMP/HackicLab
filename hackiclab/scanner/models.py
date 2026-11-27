"""Модели данных аппаратного профиля и вспомогательные структуры."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CPUInfo:
    name: str = ""
    vendor: str = ""            # intel / amd
    generation: int = 0         # Intel: 1..15 ; AMD: 8..12 (Zen family)
    codename: str = ""          # e.g. "Coffee Lake", "Zen 3"
    oc_platform: str = ""       # OpenCore platform, e.g. "Coffee Lake"
    family: str = ""            # desktop / laptop / hedt
    core_count: int = 0
    thread_count: int = 0
    brand: str = ""             # Core / Ryzen / Xeon / Core Ultra ...
    model_number: str = ""      # e.g. "i5-8350U"
    is_apple_silicon: bool = False

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "vendor": self.vendor,
            "generation": self.generation,
            "codename": self.codename,
            "oc_platform": self.oc_platform,
            "family": self.family,
            "core_count": self.core_count,
            "thread_count": self.thread_count,
            "brand": self.brand,
            "model_number": self.model_number,
            "is_apple_silicon": self.is_apple_silicon,
        }


@dataclass
class GPUInfo:
    name: str = ""
    vendor: str = ""            # intel / amd / nvidia
    device_id: str = ""         # hex PCI dev id, e.g. "5917"
    is_integrated: bool = False
    pci_device: int = -1
    pci_function: int = -1
    vram_mb: int = 0
    pci_path: str = ""          # UEFI-путь карты: PciRoot(0x0)/Pci(...)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "vendor": self.vendor,
            "device_id": self.device_id,
            "is_integrated": self.is_integrated,
            "pci_device": self.pci_device,
            "pci_function": self.pci_function,
            "vram_mb": self.vram_mb,
        }


@dataclass
class AudioInfo:
    name: str = ""
    codec: str = ""             # e.g. "ALC295"
    pci_device: int = -1
    pci_function: int = -1
    layout_id: int = 0
    layout_candidates: list = field(default_factory=list)
    pci_path: str = ""          # UEFI-путь контроллера: PciRoot(0x0)/Pci(...)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "codec": self.codec,
            "pci_device": self.pci_device,
            "pci_function": self.pci_function,
            "layout_id": self.layout_id,
            "layout_candidates": self.layout_candidates,
            "pci_path": self.pci_path,
        }


@dataclass
class NetInfo:
    # Ethernet
    eth_name: str = ""
    eth_chipset: str = ""       # i219 / i225 / rtl8111 ...
    eth_pci_device: int = -1
    eth_pci_function: int = -1
    eth_pci_path: str = ""
    # WiFi
    wifi_name: str = ""
    wifi_chipset: str = ""      # intel / broadcom / atheros / realtek / mediatek
    wifi_pci_device: int = -1
    wifi_pci_function: int = -1
    wifi_pci_path: str = ""
    # Bluetooth
    bt_chipset: str = ""
    has_bt: bool = False
    # True если найден нативный Apple Bluetooth-модуль (VID 05AC) — как у карт
    # BCM94360CD/BCM943602CS: ему не нужны BrcmPatchRAM/BrcmFirmwareData.
    bt_native_apple: bool = False
    # Неактивные Wi-Fi адаптеры: их видит Windows, но выбирать их нельзя.
    ignored_wifi: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "eth_name": self.eth_name,
            "eth_chipset": self.eth_chipset,
            "eth_pci_device": self.eth_pci_device,
            "eth_pci_function": self.eth_pci_function,
            "eth_pci_path": self.eth_pci_path,
            "wifi_name": self.wifi_name,
            "wifi_chipset": self.wifi_chipset,
            "wifi_pci_device": self.wifi_pci_device,
            "wifi_pci_function": self.wifi_pci_function,
            "wifi_pci_path": self.wifi_pci_path,
            "bt_chipset": self.bt_chipset,
            "has_bt": self.has_bt,
            "bt_native_apple": self.bt_native_apple,
            "ignored_wifi": self.ignored_wifi,
        }


@dataclass
class StorageInfo:
    nvme_present: bool = False
    sata_present: bool = True
    nvme_pci_device: int = -1
    nvme_pci_function: int = -1
    controllers: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "nvme_present": self.nvme_present,
            "sata_present": self.sata_present,
            "nvme_pci_device": self.nvme_pci_device,
            "nvme_pci_function": self.nvme_pci_function,
            "controllers": self.controllers,
        }


@dataclass
class DisplayProfile:
    """Агрегированная картина дисплейной системы."""
    igpu: Optional[GPUInfo] = None
    dgpu: Optional[GPUInfo] = None
    # true если iGPU является основным или единственным
    igpu_primary: bool = False

    def has_macos_accel(self, cpu_gen: int) -> bool:
        """Есть ли хоть одна поддерживаемая macOS GPU с аппаратным ускорением."""
        amd_dgpu = bool(self.dgpu and self.dgpu.vendor == "amd")
        intel_igpu = bool(self.igpu and self.igpu.vendor == "intel" and cpu_gen < 11)
        return amd_dgpu or intel_igpu


@dataclass
class HardwareProfile:
    host_os: str = "windows"
    platform: str = "desktop"    # laptop / desktop
    board_vendor: str = ""
    board_name: str = ""
    board_spoofed: bool = False   # SMBIOS подменён загрузчиком (OpenCore/Clover)
    chipset: str = ""
    bios_version: str = ""
    smbios_model: str = ""

    cpu: CPUInfo = field(default_factory=CPUInfo)
    igpu: Optional[GPUInfo] = None
    dgpu: Optional[GPUInfo] = None
    audio: AudioInfo = field(default_factory=AudioInfo)
    net: NetInfo = field(default_factory=NetInfo)
    storage: StorageInfo = field(default_factory=StorageInfo)

    has_touchpad: bool = False
    touchpad_type: str = "ps2"   # ps2 / i2c / none
    has_thunderbolt: bool = False
    resizable_bar: bool = False
    virtual_machine: str = ""    # непусто если обнаружена ВМ

    def display(self) -> DisplayProfile:
        return DisplayProfile(igpu=self.igpu, dgpu=self.dgpu,
                              igpu_primary=not bool(self.dgpu))

    def to_dict(self) -> dict:
        return {
            "host_os": self.host_os,
            "platform": self.platform,
            "board_vendor": self.board_vendor,
            "board_name": self.board_name,
            "board_spoofed": self.board_spoofed,
            "chipset": self.chipset,
            "bios_version": self.bios_version,
            "smbios_model": self.smbios_model,
            "cpu": self.cpu.as_dict(),
            "igpu": self.igpu.as_dict() if self.igpu else None,
            "dgpu": self.dgpu.as_dict() if self.dgpu else None,
            "audio": self.audio.as_dict(),
            "net": self.net.as_dict(),
            "storage": self.storage.as_dict(),
            "has_touchpad": self.has_touchpad,
            "touchpad_type": self.touchpad_type,
            "has_thunderbolt": self.has_thunderbolt,
            "resizable_bar": self.resizable_bar,
            "virtual_machine": self.virtual_machine,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HardwareProfile":
        p = cls()
        for k, v in data.items():
            if hasattr(p, k) and not isinstance(v, dict):
                setattr(p, k, v)
        if isinstance(data.get("cpu"), dict):
            p.cpu = CPUInfo(**{k: v for k, v in data["cpu"].items() if k in CPUInfo.__dataclass_fields__})
        for k in ("igpu", "dgpu"):
            if isinstance(data.get(k), dict):
                g = GPUInfo(**{kk: vv for kk, vv in data[k].items() if kk in GPUInfo.__dataclass_fields__})
                setattr(p, k, g)
        if isinstance(data.get("audio"), dict):
            p.audio = AudioInfo(**{k: v for k, v in data["audio"].items() if k in AudioInfo.__dataclass_fields__})
        if isinstance(data.get("net"), dict):
            p.net = NetInfo(**{k: v for k, v in data["net"].items() if k in NetInfo.__dataclass_fields__})
        if isinstance(data.get("storage"), dict):
            p.storage = StorageInfo(**{k: v for k, v in data["storage"].items() if k in StorageInfo.__dataclass_fields__})
        return p
