"""Генерация config.plist OpenCore под аппаратный профиль.

Логика ключей / ig-platform-id адаптирована из hackmate (config_gen.py)
и OpCore-Simplify (config_prodigy.py) под чистую структуру данных.
"""

from __future__ import annotations

import plistlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ..scanner.models import HardwareProfile

if TYPE_CHECKING:
    from .smbios_gen import SMBIOSData

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
    disable_sip: bool = True
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
        {"Enabled": True, "Path": "SSDT-EC.aml", "Comment": "Fake EC"},
        {"Enabled": False, "Path": "SSDT-USBX.aml", "Comment": "USB power"},
    ]
    if profile.cpu.vendor == "intel":
        # SSDT-PLUG включает X86PlatformPlugin — только для Intel
        cfg["ACPI"]["Add"].insert(
            0, {"Enabled": True, "Path": "SSDT-PLUG.aml", "Comment": "CPU power management"})
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
        k["Emulate"]["DummyPowerManagement"] = True
        k["Patch"] = []  # заполняется AMD_Vanilla в сборщике
    else:
        cfg["Kernel"]["Patch"] = []

    # --- Booter: квирки под AMD (Ryzen) ---
    if profile.cpu.vendor == "amd":
        bq = cfg["Booter"]["Quirks"]
        bq["RebuildAppleMemoryMap"] = True
        bq["EnableWriteUnprotector"] = False
        bq["SyncRuntimePermissions"] = True

    # --- Misc → Boot ---
    cfg["Misc"]["Boot"] = cfg["Misc"]["Boot"]

    # --- macOS-версия влияет на SecureBootModel и boot-args ---
    _apply_macos_model(cfg, options.target_macos, profile)

    # --- NVRAM ---
    if options.disable_sip:
        # меняем только csr-active-config, не теряя boot-args и прочие ключи
        nv = cfg["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]
        nv["csr-active-config"] = bytes([0x67, 0, 0, 0])

    # --- SMBIOS: инжектим сгенерированные данные в PlatformInfo ---
    if options.custom_smbios:
        _apply_smbios(cfg, options.custom_smbios)

    return plistlib.dumps(cfg, fmt=plistlib.FMT_XML, sort_keys=False)


def _apply_smbios(cfg: dict, data: "SMBIOSData"):
    """Инжектит сгенерированные SMBIOS-данные в PlatformInfo → Generic."""
    gen = cfg["PlatformInfo"]["Generic"]
    gen["SystemProductName"] = data.model
    if data.serial:
        gen["SystemSerialNumber"] = data.serial
    if data.mlb:
        gen["MLB"] = data.mlb
    if data.system_uuid:
        gen["SystemUUID"] = data.system_uuid
    if data.rom:
        gen["ROM"] = bytes.fromhex(data.rom)


def _macos_major(target: str) -> int:
    """Из имени 'macOS Sequoia / 15' возвращает мажорную версию."""
    t = (target or "").lower()
    # старые 10.x проверяем ДО числовых подстрок, иначе 10.15 → 15
    if "catalina" in t or "10.15" in t: return 10
    if "mojave" in t or "10.14" in t: return 10
    if "high sierra" in t or "10.13" in t: return 10
    if "tahoe" in t or "26" in t: return 26
    if "sequoia" in t or "15" in t: return 15
    if "sonoma" in t or "14" in t: return 14
    if "ventura" in t or "13" in t: return 13
    if "monterey" in t or "12" in t: return 12
    if "big sur" in t or "11" in t: return 11
    return 26  # по умолчанию актуальная


def _apply_macos_model(cfg: dict, target: str, profile: HardwareProfile):
    """Проставляет SecureBootModel и версионные квирки под macOS-версию.

    На не-Apple железе (в т.ч. Ryzen) SecureBootModel=Default ломает загрузку
    recovery/подписанных образов, поэтому всегда Disabled.
    """
    major = _macos_major(target)
    sb = cfg["Misc"]["Security"]
    sb["SecureBootModel"] = "Disabled"
    # XhciPortLimit нужен только на macOS < 11.3; на новых — USB map.
    if major < 11:
        cfg["Kernel"]["Quirks"]["XhciPortLimit"] = True


def _base_config() -> dict:
    """Полный валидный config.plist-каркас OpenCore (схема 1.0.8/1.0.9).

    Включает все ключи секций из Sample.plist OpenCorePkg, чтобы ocvalidate
    не выдавал ошибок «Missing key …» и проходил валидацию начисто. Значения
    выставлены как практичные дефолты; сборка дальше их точечно переопределяет.
    """
    return {
        "ACPI": {
            "Add": [], "Delete": [], "Patch": [],
            "Quirks": {
                "FadtEnableReset": False,
                "NormalizeHeaders": False,
                "RebaseRegions": False,
                "ResetHwSig": False,
                "ResetLogoStatus": True,
                "SyncTableIds": False,
            },
        },
        "Booter": {
            "MmioWhitelist": [],
            "Patch": [],
            "Quirks": {
                "AllowRelocationBlock": False,
                "AvoidRuntimeDefrag": True,
                "ClearTaskSwitchBit": False,
                "DevirtualiseMmio": False,
                "DisableSingleUser": False,
                "DisableVariableWrite": False,
                "DiscardHibernateMap": False,
                "EnableSafeModeSlide": True,
                "EnableWriteUnprotector": True,
                "FixupAppleEfiImages": True,
                "ForceBooterSignature": False,
                "ForceExitBootServices": False,
                "ProtectMemoryRegions": False,
                "ProtectSecureBoot": False,
                "ProtectUefiServices": False,
                "ProvideCustomSlide": True,
                "ProvideMaxSlide": 0,
                "RebuildAppleMemoryMap": False,
                "ResizeAppleGpuBars": -1,
                "SetupVirtualMap": True,
                "SignalAppleOS": False,
                "SyncRuntimePermissions": False,
            },
        },
        "DeviceProperties": {
            "Add": {}, "Delete": {},
        },
        "Kernel": {
            "Add": [], "Block": [], "Patch": [],
            "Emulate": {
                "Cpuid1Data": bytes(),
                "Cpuid1Mask": bytes(),
                "DummyPowerManagement": False,
                "MaxKernel": "",
                "MinKernel": "",
            },
            "Force": [],
            "Scheme": {
                "CustomKernel": False,
                "FuzzyMatch": True,
                "KernelArch": "Auto",
                "KernelCache": "Auto",
            },
            "Quirks": {
                "AppleCpuPmCfgLock": False,
                "AppleXcpmCfgLock": False,
                "AppleXcpmExtraMsrs": False,
                "AppleXcpmForceBoost": False,
                "CustomPciSerialDevice": False,
                "CustomSMBIOSGuid": False,
                "DisableIoMapper": True,
                "DisableIoMapperMapping": False,
                "DisableLinkeditJettison": True,
                "DisableRtcChecksum": False,
                "ExtendBTFeatureFlags": False,
                "ExternalDiskIcons": False,
                "ForceAquantiaEthernet": False,
                "ForceSecureBootScheme": False,
                "IncreasePciBarSize": False,
                "LapicKernelPanic": False,
                "LegacyCommpage": False,
                "PanicNoKextDump": False,
                "PowerTimeoutKernelPanic": True,
                "ProvideCurrentCpuInfo": False,
                "SetApfsTrimTimeout": -1,
                "ThirdPartyDrives": True,
                "XhciPortLimit": False,
            },
        },
        "Misc": {
            "BlessOverride": [],
            "Boot": {
                "ConsoleAttributes": 0,
                "HibernateMode": "None",
                "HibernateSkipsPicker": False,
                "HideAuxiliary": False,
                "InstanceIdentifier": "",
                "LauncherOption": "Disabled",
                "LauncherPath": "Default",
                "PickerAttributes": 17,
                "PickerAudioAssist": False,
                "PickerMode": "Builtin",
                "PickerVariant": "Auto",
                "PollAppleHotKeys": True,
                "ShowPicker": True,
                "TakeoffDelay": 0,
                "Timeout": 5,
            },
            "Debug": {
                "AppleDebug": True, "ApplePanic": True,
                "DisableWatchDog": True, "DisplayDelay": 0,
                "DisplayLevel": 0x80000002, "LogModules": "*",
                "SysReport": False, "Target": 3,
            },
            "Entries": [],
            "Security": {
                "AllowSetDefault": True,
                "ApECID": 0, "AuthRestart": False,
                "BlacklistAppleUpdate": True,
                "DmgLoading": "Signed",
                "EnablePassword": False,
                "ExposeSensitiveData": 3, "HaltLevel": 0x80000000,
                "PasswordHash": bytes(), "PasswordSalt": bytes(),
                "ScanPolicy": 0, "SecureBootModel": "Disabled",
                "Vault": "Optional",
            },
            "Serial": {"Init": False, "Override": False},
            "Tools": [],
        },
        "NVRAM": {
            "Add": {
                "7C436110-AB2A-4BBB-A880-FE41995C9F82": {
                    "boot-args": "-v debug=0x100 keepsyms=1",
                    "csr-active-config": bytes([0, 0, 0, 0]),
                    "prev-lang:kbd": bytes("en:0", "utf-8"),
                    "run-efi-updater": "No",
                },
            },
            "Delete": {
                "7C436110-AB2A-4BBB-A880-FE41995C9F82": ["boot-args", "csr-active-config"],
            },
            "LegacyOverwrite": False,
            "LegacySchema": {
                "7C436110-AB2A-4BBB-A880-FE41995C9F82": [
                    "EFILoginHiDPI", "EFIBluetoothDelay", "LocationServicesEnabled",
                    "SystemAudioVolume", "SystemAudioVolumeDB",
                    "SystemAudioVolumeSaved", "bluetoothActiveControllerInfo",
                    "bluetoothInternalControllerInfo", "flagstate",
                    "fmm-computer-name", "fmm-mobileme-token-FMM",
                    "nvda_drv", "prev-lang:kbd", "backlight-level", "BootCampHD",
                ],
                "8BE4DF61-93CA-11D2-AA0D-00E098032B8C": [
                    "Boot0080", "Boot0081", "Boot0082", "BootNext", "BootOrder",
                ],
            },
            "WriteFlash": True,
        },
        "PlatformInfo": {
            "Automatic": True,
            "CustomMemory": False,
            "Generic": {
                "AdviseFeatures": False,
                "MLB": "",
                "MaxBIOSVersion": False,
                "ProcessorType": 0,
                "ROM": bytes(),
                "SpoofVendor": True,
                "SystemMemoryStatus": "Auto",
                "SystemProductName": "",
                "SystemSerialNumber": "",
                "SystemUUID": "",
            },
            "UpdateDataHub": True,
            "UpdateNVRAM": True,
            "UpdateSMBIOS": True,
            "UpdateSMBIOSMode": "Create",
            "UseRawUuidEncoding": False,
        },
        "UEFI": {
            "APFS": {
                "EnableJumpstart": True, "GlobalConnect": False,
                "HideVerbose": True, "JumpstartHotPlug": False,
                "MinDate": 0, "MinVersion": 0,
            },
            "AppleInput": {
                "AppleEvent": "Builtin", "CustomDelays": False,
                "GraphicsInputMirroring": True, "KeyInitialDelay": 50,
                "KeySubsequentDelay": 5, "PointerDwellClickTimeout": 0,
                "PointerDwellDoubleClickTimeout": 0, "PointerDwellRadius": 0,
                "PointerPollMask": -1, "PointerPollMax": 80,
                "PointerPollMin": 10, "PointerSpeedDiv": 1, "PointerSpeedMul": 1,
            },
            "Audio": {
                "AudioCodec": 0, "AudioDevice": "", "AudioOutMask": 1,
                "AudioSupport": False, "DisconnectHda": False,
                "MaximumGain": -15, "MinimumAssistGain": -30,
                "MinimumAudibleGain": -55, "PlayChime": "Disabled",
                "ResetTrafficClass": False, "SetupDelay": 0,
            },
            "ConnectDrivers": True,
            "Drivers": [],
            "Input": {
                "KeyFiltering": False, "KeyForgetThreshold": 5,
                "KeySupport": False, "KeySupportMode": "Auto",
                "KeySwap": False, "PointerSupport": False,
                "PointerSupportMode": "ASUS", "TimerResolution": 50000,
            },
            "Output": {
                "ClearScreenOnModeSwitch": False, "ConsoleFont": "",
                "ConsoleMode": "", "DirectGopRendering": False,
                "ForceResolution": False, "GopBurstMode": False,
                "GopPassThrough": "Disabled", "IgnoreTextInGraphics": False,
                "InitialMode": "Auto", "ProvideConsoleGop": True,
                "ReconnectGraphicsOnConnect": False, "ReconnectOnResChange": False,
                "ReplaceTabWithSpace": False, "Resolution": "Max",
                "SanitiseClearScreen": False, "TextRenderer": "BuiltinGraphics",
                "UIScale": 0, "UgaPassThrough": False,
            },
            "ProtocolOverrides": {
                "AppleAudio": False, "AppleBootPolicy": False,
                "AppleDebugLog": False, "AppleEg2Info": False,
                "AppleFramebufferInfo": False, "AppleImageConversion": False,
                "AppleImg4Verification": False, "AppleKeyMap": False,
                "AppleRtcRam": False, "AppleSecureBoot": False,
                "AppleSmcIo": False, "AppleUserInterfaceTheme": False,
                "DataHub": False, "DeviceProperties": False,
                "FirmwareVolume": True, "HashServices": False,
                "OSInfo": False, "PciIo": False, "UnicodeCollation": False,
            },
            "Quirks": {
                "ActivateHpetSupport": False, "DisableSecurityPolicy": False,
                "EnableVectorAcceleration": True, "EnableVmx": False,
                "ExitBootServicesDelay": 0, "ForceOcWriteFlash": False,
                "ForgeUefiSupport": False, "IgnoreInvalidFlexRatio": False,
                "ReleaseUsbOwnership": False, "ReloadOptionRoms": False,
                "RequestBootVarRouting": True, "ResizeGpuBars": -1,
                "ResizeUsePciRbIo": False, "ShimRetainProtocol": False,
                "TscSyncTimeout": 0, "UnblockFsConnect": False,
            },
            "ReservedMemory": [],
            "Unload": [],
        },
    }
