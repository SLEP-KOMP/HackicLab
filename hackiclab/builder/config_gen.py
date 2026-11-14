"""Генерация config.plist OpenCore под аппаратный профиль.

Логика ключей / ig-platform-id адаптирована из hackmate (config_gen.py)
и OpCore-Simplify (config_prodigy.py) под чистую структуру данных.
"""

from __future__ import annotations

import plistlib
from dataclasses import dataclass, field
from typing import Optional

from ..scanner.models import HardwareProfile, GPUInfo
from ..knowledge.kexts import smbios_model_for
from ..knowledge.oc_platforms import oc_platform_for

# ig-platform-id по поколению/форм-фактору
IG_PLATFORM_IDS = {
    # Sandy Bridge
    "snb_mobile": bytes([0x00, 0x00, 0x01, 0x00]),
    "snb_desktop": bytes([0x10, 0x00, 0x03, 0x00]),
    "snb_headless": bytes([0x00, 0x00, 0x05, 0x00]),
    # Ivy Bridge
    "ivb_mobile": bytes([0x03, 0x00, 0x66, 0x01]),
    "ivb_desktop": bytes([0x0A, 0x00, 0x66, 0x01]),
    # Haswell
    "hsw_mobile": bytes([0x06, 0x00, 0x26, 0x0A]),
    "hsw_desktop": bytes([0x03, 0x00, 0x22, 0x0D]),
    # Skylake
    "skl_mobile": bytes([0x00, 0x00, 0x16, 0x19]),
    "skl_desktop": bytes([0x00, 0x00, 0x12, 0x19]),
    # Kaby Lake
    "hd620": bytes([0x00, 0x00, 0x16, 0x59]),
    "hd630_dt": bytes([0x00, 0x00, 0x12, 0x59]),
    "hd630_mb": bytes([0x00, 0x00, 0x1B, 0x59]),
    # Coffee Lake
    "uhd630_dt": bytes([0x07, 0x00, 0x9B, 0x3E]),
    "uhd630_mb": bytes([0x09, 0x00, 0xA5, 0x3E]),
    # Ice Lake
    "iris_ice": bytes([0x00, 0x00, 0x52, 0x8A]),
}


@dataclass
class BuildOptions:
    usb_toolbox: bool = True
    wifi_kext_mode: str = "itlwm"       # itlwm / airport
    disable_sip: bool = False
    has_amd_vgpu: bool = False
    custom_smbios: Optional["SMBIOSData"] = None
    target_macos: str = ""              # e.g. "Sonoma"
    verbose: bool = False
    # Патчи, которые клиент хочет искусственно пропустить (набор имён kext)
    skip_kexts: set = field(default_factory=set)


def _int(name: str) -> bytes:
    return bytes((int(name, 16) & 0xFF, (int(name, 16) >> 8) & 0xFF, 0, 0))


def _igpu_config(profile: HardwareProfile, headless: bool = False):
    """(ig-platform-id, device-id или None) для Intel iGPU."""
    gen = profile.cpu.generation
    if gen == 2:
        if profile.platform == "laptop": return IG_PLATFORM_IDS["snb_mobile"], None
        if headless: return IG_PLATFORM_IDS["snb_headless"], None
        return IG_PLATFORM_IDS["snb_desktop"], None
    if gen == 3:
        if profile.platform == "laptop": return IG_PLATFORM_IDS["ivb_mobile"], None
        return IG_PLATFORM_IDS["ivb_desktop"], None
    if gen == 4:
        if profile.platform == "laptop": return IG_PLATFORM_IDS["hsw_mobile"], None
        return IG_PLATFORM_IDS["hsw_desktop"], None
    if gen == 6:
        if profile.platform == "laptop": return IG_PLATFORM_IDS["skl_mobile"], None
        if headless: return IG_PLATFORM_IDS["skl_headless"] if "skl_headless" in IG_PLATFORM_IDS else (IG_PLATFORM_IDS["skl_desktop"], None)
        return IG_PLATFORM_IDS["skl_desktop"], None
    if gen == 7:
        if profile.platform == "laptop": return IG_PLATFORM_IDS["hd620"], None
        if headless: return IG_PLATFORM_IDS["hd630_headless"] if "hd630_headless" in IG_PLATFORM_IDS else (IG_PLATFORM_IDS["hd630_dt"], None)
        return IG_PLATFORM_IDS["hd630_dt"], None
    if gen in (8, 9):
        if profile.platform == "laptop": return IG_PLATFORM_IDS["uhd630_mb"], None
        if headless: return IG_PLATFORM_IDS["uhd630_dt"], None
        return IG_PLATFORM_IDS["uhd630_dt"], None
    if gen == 10:
        if profile.platform == "laptop": return IG_PLATFORM_IDS["hd620"], None
        return IG_PLATFORM_IDS["hd630_dt"], None
    # Слишком новые/неизвестные — без конфигурации iGPU
    return None, None


def generate_config_plist(profile: HardwareProfile, options: BuildOptions) -> bytes:
    """Собирает полный config.plist (XML) для OpenCore под профиль."""
    cfg = _base_config()

    # --- ACPI ---
    cfg["ACPI"]["Add"] = [
        {"Enabled": True, "Path": "SSDT-PLUG.aml", "Comment": "CPU power management"},
        {"Enabled": True, "Path": "SSDT-EC.aml", "Comment": "Fake EC"},
        {"Enabled": False, "Path": "SSDT-USBX.aml", "Comment": "USB power"},
    ]
    if profile.platform == "laptop":
        cfg["ACPI"]["Add"].append({"Enabled": True, "Path": "SSDT-PNLF.aml", "Comment": "Backlight"})
        cfg["ACPI"]["Add"].append({"Enabled": True, "Path": "SSDT-EC-USBX.aml", "Comment": "Fake EC + USB"})
        cfg["ACPI"]["Add"] = [x for x in cfg["ACPI"]["Add"] if x["Path"] != "SSDT-EC.aml"]
    cfg["ACPI"]["Patch"] = []

    # --- DeviceProperties ---
    dp = cfg["DeviceProperties"]
    dp["Add"] = {}
    igpu = profile.igpu if (profile.igpu and profile.igpu.vendor == "intel") else None
    if igpu and profile.cpu.vendor == "intel":
        headless = bool(profile.dgpu and profile.dgpu.vendor == "amd")
        pidi, devid = _igpu_config(profile, headless=headless)
        if pidi:
            # PciRoot(0x0)/Pci(0x2,0x0)
            props = {"AAPL,ig-platform-id": pidi}
            if devid:
                props["device-id"] = devid
            dp["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"] = props

    # --- Kernel ---
    k = cfg["Kernel"]
    k["Add"] = []   # заполняется сборщиком по выбранным kext
    if profile.cpu.vendor == "amd":
        k["Quirks"]["ProvideCurrentCpuInfo"] = True
        cfg["Kernel"]["Patch"] = []  # сюда позже AMD_Vanilla
    else:
        cfg["Kernel"]["Patch"] = []

    # --- Misc → Boot ---
    cfg["Misc"]["Boot"] = cfg["Misc"]["Boot"]

    # --- macOS-версия влияет на SecureBootModel и boot-args ---
    _apply_macos_model(cfg, options.target_macos, profile)

    # --- NVRAM ---
    if options.disable_sip:
        cfg["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"] = {
            "csr-active-config": bytes([0x67, 0, 0, 0])
        }

    return plistlib.dumps(cfg, fmt=plistlib.FMT_XML, sort_keys=False)


def _macos_major(target: str) -> int:
    """Из имени 'macOS Sequoia / 15' возвращает мажорную версию, или 20 (неизвестно)."""
    t = (target or "").lower()
    if "tahoe" in t or "26" in t: return 26
    if "sequoia" in t or "15" in t: return 15
    if "sonoma" in t or "14" in t: return 14
    if "ventura" in t or "13" in t: return 13
    if "monterey" in t or "12" in t: return 12
    if "big sur" in t or "11" in t: return 11
    if "catalina" in t or "10.15" in t: return 15
    if "mojave" in t or "10.14" in t: return 14
    return 26  # по умолчанию актуальная


def _apply_macos_model(cfg: dict, target: str, profile: HardwareProfile):
    """Проставляет SecureBootModel и ряд версионных квирков под macOS-версию."""
    major = _macos_major(target)
    sb = cfg["Misc"]["Security"]
    if major < 12:
        sb["SecureBootModel"] = "j160"   # Big Sur и старше
    elif major < 13:
        sb["SecureBootModel"] = "j185"   # Monterey
    elif major < 14:
        sb["SecureBootModel"] = "j223"   # Ventura
    elif major < 15:
        sb["SecureBootModel"] = "j274"   # Sonoma (выбран по умолчанию)
    else:
        sb["SecureBootModel"] = "DEFAULT"

    # XhciPortLimit нужен только на macOS < 11.3 / Big Sur и старше
    # CryptexFixup квирк для новых macOS на старом железе добавляется профилем.
    if "SMCAMDProcessor" if hasattr(profile, "cpu") and profile.cpu.vendor == "amd" else False:
        pass


def _base_config() -> dict:
    """Минимально валидный config.plist-каркас OpenCore."""
    return {
        "ACPI": {
            "Add": [], "Delete": [], "Patch": [],
            "Quirks": {
                "FadtEnableReset": False,
                "NormalizeHeaders": False,
                "RebaseRegions": False,
                "ResetHwSig": False,
                "ResetLogoStatus": False,
            },
        },
        "Booter": {
            "MmioWhitelist": [],
            "Patch": [],
            "Quirks": {
                "AvoidRuntimeDefrag": True,
                "DevirtualiseMmio": False,
                "DisableSingleUser": False,
                "DiscardHibernateMap": False,
                "EnableSafeModeSlide": True,
                "EnableWriteUnprotector": True,
                "ForceExitBootServices": False,
                "ProtectMemoryRegions": False,
                "ProtectSecureBoot": False,
                "ProvideCustomSlide": True,
                "ProvideMaxSlide": 0,
                "RebuildAppleMemoryMap": True,
                "SetupVirtualMap": True,
                "SignalAppleOS": False,
                "SyncRuntimePermissions": True,
            },
        },
        "DeviceProperties": {
            "Add": {}, "Delete": {},
        },
        "Kernel": {
            "Add": [], "Block": [],
            "Patch": [],
            "Quirks": {
                "AppleCpuPmCfgLock": False,
                "AppleXcpmCfgLock": False,
                "CustomSMBIOSGuid": False,
                "DisableIoMapper": True,
                "ExternalDiskIcons": False,
                "LapicKernelPanic": False,
                "PanicNoKextDump": False,
                "PowerTimeoutKernelPanic": True,
                "ProvideCurrentCpuInfo": False,
                "SetExternalGpu": False,
                "ThirdPartyDrives": True,
                "XhciPortLimit": False,
            },
        },
        "Misc": {
            "BlessOverride": [],
            "Boot": {
                "Arguments": "-v -debug=0x100 keepsyms=1 debug=0x100",
                "ConsoleAttributes": 0,
                "HibernateMode": "None",
                "Hidesensitivelog": False,
                "PollAppleHotKeys": True,
                "ShowPicker": True,
                "Timeout": 5,
                "PickerMode": "Builtin",
                "Tools": [],
            },
            "Debug": {
                "AppleDebug": True, "ApplePanic": True,
                "DisableWatchDog": True, "Target": 3,
            },
            "Security": {
                "AllowNvramReset": True, "AllowSetDefault": True,
                "ApECID": 0, "BlacklistAppleUpdate": True,
                "BootProtect": "None", "DmgLoading": "Signed",
                "ExposeSensitiveData": 3, "HaltLevel": 0x80000000,
                "ScanPolicy": 0, "SecureBootModel": "j137",
                "Vault": "Optional",
            },
            "Tools": [],
            "Entries": [],
        },
        "NVRAM": {
            "Add": {
                "4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38C14": {
                    "UIScale": bytes([1]),
                },
                "7C436110-AB2A-4BBB-A880-FE41995C9F82": {
                    "boot-args": "-v debug=0x100 keepsyms=1",
                    "csr-active-config": bytes([0, 0, 0, 0]),
                    "prev-lang:kbd": bytes("en:0", "utf-8"),
                },
                "PlatformNVRAM": {},
            },
            "Delete": {
                "4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38C14": ["UIScale"],
                "7C436110-AB2A-4BBB-A880-FE41995C9F82": ["boot-args", "csr-active-config"],
            },
            "LegacyEnable": False,
            "LegacyOverwrite": False,
            "LegacySchema": {},
            "WriteFlash": True,
        },
        "PlatformInfo": {
            "Automatic": True,
            "CustomMemory": False,
            "Generic": {
                "AdviseWindows": False,
                "MLB": "",
                "ROM": bytes(),
                "SpoofVendor": True,
                "SystemProductName": "",
                "SystemSerialNumber": "",
                "SystemUUID": "",
            },
            "SMBIOS": {},
            "UpdateDataHub": True,
            "UpdateNVRAM": True,
            "UpdateSMBIOS": True,
            "UpdateSMBIOSMode": "Create",
        },
        "UEFI": {
            "APFS": {"EnableJumpdrive": True, "GlobalConnect": True, "HideVerbose": True},
            "AppleInput": {
                "AutoBoot": False, "KeyInitialisation": "Auto",
                "KeySupport": False, "PointerDither": False,
                "PointerSupport": False, "PointerSupportMode": "",
            },
            "Audio": {"AudioCodec": 0, "AudioDevice": "", "AudioSupport": False},
            "ConnectDrivers": True,
            "Drivers": [],
            "Input": {"KeyboardFilter": 0, "KeyForgetThreshold": 5, "KeySupport": False, "KeySupportMode": "Auto", "PointerSupport": False},
            "Output": {"DirectGopRendering": False, "ForceResolution": False, "ProvideConsoleGop": True, "ReconnectOnResChange": False},
            "ProtocolOverrides": {},
            "Quirks": {
                "AppleSmcIo": True, "DisableSecurityPolicy": False,
                "EnableVectorAcceleration": False, "EnableVmx": False,
                "ExitBootServicesDelay": 0, "ForceBooterSignature": False,
                "ForceOcWriteFlash": True, "IgnoreInvalidFlexRatio": False,
                "ReleaseUsbOwnership": True, "RequestBootVarRouting": True,
                "ResizeGpuBars": -1, "UnblockFsConnect": False,
            },
        },
    }