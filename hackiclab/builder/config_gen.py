"""Генерация config.plist OpenCore под аппаратный профиль.

plist собирается из dataclass-профиля: ACPI, Kernel, DeviceProperties,
PlatformInfo и квирки заполняются по правилам, а не копируются из шаблона.
Значения ig-platform-id и device-id — публичные идентификаторы Intel из
документации Apple и WhateverGreen.
"""

from __future__ import annotations

import plistlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ..knowledge.kexts import is_navi_gpu, smbios_model_for
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
    # Comet Lake: мобильный UHD 620 — 00009B3E, десктоп — как Coffee Lake
    "cml_mb": bytes([0x00, 0x00, 0x9B, 0x3E]),
    # Ice Lake
    "iris_ice": bytes([0x00, 0x00, 0x52, 0x8A]),
}


@dataclass
class BuildOptions:
    usb_toolbox: bool = True
    # Порты, выбранные в мастере: None — все (как видит macOS, до 15 на контроллер)
    usb_ports: Optional[set] = None
    wifi_kext_mode: str = "itlwm"       # itlwm / airport
    disable_sip: bool = True
    has_amd_vgpu: bool = False
    custom_smbios: Optional["SMBIOSData"] = None
    target_macos: str = ""              # e.g. "Sonoma"
    verbose: bool = False
    # Отключить дискретную видеокарту (WhateverGreen: -wegnoegpu)
    disable_dgpu: bool = False
    # Мультизагрузка: "" / windows / linux / both — для linux ставим OpenLinuxBoot
    dual_boot: str = ""
    # Графическое меню OpenCore (OpenCanopy + Resources) вместо текстового
    gui_picker: bool = False
    # Звук в загрузчике (AudioDxe + UEFI/Audio): звук и сигнал ошибки в меню
    audio_dxe: bool = False
    # Сетевая загрузка (OpenNetworkBoot + сетевой стек): PXE и HTTP(S)
    network_boot: bool = False
    # Загрузка legacy-ОС (OpenLegacyBoot, нужен CSM или OpenDuet)
    legacy_boot: bool = False
    # Патчи, которые клиент хочет искусственно пропустить (набор имён kext)
    skip_kexts: set = field(default_factory=set)
    # ACPI-патчи, посчитанные по DSDT (переименования под SSDT-HPET)
    extra_acpi_patches: list = field(default_factory=list)
    # Какие патчи применить: id из knowledge.patches. None — все нужные по железу.
    patches: Optional[set] = None


def _patch_on(options, patch_id: str) -> bool:
    """Включён ли патч: по умолчанию (None) — всё, что нужно железу."""
    sel = getattr(options, "patches", None)
    return True if sel is None else patch_id in sel


def _int(name: str) -> bytes:
    return bytes((int(name, 16) & 0xFF, (int(name, 16) >> 8) & 0xFF, 0, 0))


#: Поколение -> ключи IG_PLATFORM_IDS для ноутбука, десктопа и режима без вывода.
_IGPU_RULES = {
    2: {"laptop": "snb_mobile", "desktop": "snb_desktop", "headless": "snb_headless"},
    3: {"laptop": "ivb_mobile", "desktop": "ivb_desktop"},
    4: {"laptop": "hsw_mobile", "desktop": "hsw_desktop"},
    6: {"laptop": "skl_mobile", "desktop": "skl_desktop", "headless": "skl_headless"},
    7: {"laptop": "hd630_mb", "desktop": "hd630_dt", "headless": "hd630_headless"},
    8: {"laptop": "uhd630_mb", "desktop": "uhd630_dt", "headless": "uhd630_dt"},
    9: {"laptop": "uhd630_mb", "desktop": "uhd630_dt", "headless": "uhd630_dt"},
    10: {"laptop": "cml_mb", "desktop": "uhd630_dt", "headless": "uhd630_dt"},
}


def _is_pentium_celeron(profile: HardwareProfile) -> bool:
    """Pentium/Celeron без рабочей iGPU: macOS требует подмену CPUID."""
    name = (profile.cpu.name or "").lower()
    return profile.cpu.vendor == "intel" and ("pentium" in name or "celeron" in name)


def _igpu_config(profile: HardwareProfile, headless: bool = False):
    """(ig-platform-id, device-id или None) для Intel iGPU."""
    rule = _IGPU_RULES.get(profile.cpu.generation)
    if rule is None:
        # Слишком новые/неизвестные — без конфигурации iGPU
        return None, None
    if profile.platform == "laptop":
        key = rule["laptop"]
    elif headless:
        key = rule.get("headless", rule["desktop"])
    else:
        key = rule["desktop"]
    return IG_PLATFORM_IDS.get(key), None


def generate_config_plist(profile: HardwareProfile, options: BuildOptions) -> bytes:
    """Собирает полный config.plist (XML) для OpenCore под профиль."""
    cfg = _base_config()

    # --- ACPI ---
    # Все перечисленные таблицы реально кладутся в EFI/OC/ACPI и остаются
    # включёнными: выключенный SSDT рядом со своим .aml бесполезен.
    cfg["ACPI"]["Add"] = []
    if profile.platform == "laptop":
        cfg["ACPI"]["Add"].append(
            {"Enabled": True, "Path": "SSDT-EC-USBX.aml", "Comment": "Fake EC + USB power"})
        cfg["ACPI"]["Add"].append(
            {"Enabled": True, "Path": "SSDT-PNLF.aml", "Comment": "Backlight"})
    else:
        if profile.cpu.vendor == "intel" and profile.cpu.generation > 0:
            # SSDT-PLUG включает X86PlatformPlugin — только для Intel
            cfg["ACPI"]["Add"].append(
                {"Enabled": True, "Path": "SSDT-PLUG.aml", "Comment": "CPU power management"})
        cfg["ACPI"]["Add"].append(
            {"Enabled": True, "Path": "SSDT-EC.aml", "Comment": "Fake EC"})
        cfg["ACPI"]["Add"].append(
            {"Enabled": True, "Path": "SSDT-USBX.aml", "Comment": "USB power"})
    cfg["ACPI"]["Patch"] = []
    if profile.platform == "laptop":
        # SSDT-GPRW работает только вместе с переименованием _PRW в DSDT:
        # без этого macOS читает исходный _PRW и просыпается сразу после сна.
        cfg["ACPI"]["Patch"].append({
            "Base": "",
            "BaseSkip": 0,
            "Comment": "Rename _PRW to XPRW (sleep fix)",
            "Count": 0,
            "Enabled": True,
            "Find": b"_PRW",
            "Limit": 0,
            "Mask": b"",
            "OemTableId": b"",
            "Replace": b"XPRW",
            "ReplaceMask": b"",
            "Skip": 0,
            "TableLength": 0,
            "TableSignature": b"DSDT",
        })
    # Патчи по DSDT (переименование _CRS под SSDT-HPET) идут следом
    cfg["ACPI"]["Patch"].extend(getattr(options, "extra_acpi_patches", []) or [])

    # --- DeviceProperties ---
    dp = cfg["DeviceProperties"]
    dp["Add"] = {}
    igpu = profile.igpu if (profile.igpu and profile.igpu.vendor == "intel") else None
    if igpu and profile.cpu.vendor == "intel" and not _is_pentium_celeron(profile):
        headless = bool(profile.dgpu and profile.dgpu.vendor == "amd")
        pidi, devid = _igpu_config(profile, headless=headless)
        if pidi:
            # PciRoot(0x0)/Pci(0x2,0x0)
            props = {"AAPL,ig-platform-id": pidi}
            if devid:
                props["device-id"] = devid
            if profile.cpu.generation == 7 and profile.platform == "laptop" and not headless:
                # Kaby Lake ноутбуки с залоченным DVMT: без патчей framebuffer
                # macOS не поднимает ускорение (Dortania, Kaby Lake laptop).
                props["framebuffer-patch-enable"] = bytes([0x01, 0x00, 0x00, 0x00])
                props["framebuffer-stolenmem"] = bytes([0x00, 0x00, 0x30, 0x01])
                props["framebuffer-fbmem"] = bytes([0x00, 0x00, 0x90, 0x00])
            dp["Add"]["PciRoot(0x0)/Pci(0x2,0x0)"] = props

    # RX 580 2048SP (6FDF): инжект device-id заставляет macOS видеть RX 570.
    gpu = getattr(profile, "dgpu", None)
    dev = (getattr(gpu, "device_id", "") or "").lower().replace("0x", "") if gpu else ""
    gpu_name = (getattr(gpu, "name", "") or "").lower().replace(" ", "") if gpu else ""
    gpu_path = (getattr(gpu, "pci_path", "") or "") if gpu else ""
    is_2048sp = dev == "6fdf" or "2048sp" in gpu_name
    if _patch_on(options, "gpu_rx580_spoof") and is_2048sp and gpu_path:
        dp["Add"].setdefault(gpu_path, {})["device-id"] = bytes([0xDF, 0x67, 0x00, 0x00])

    # Аудио: layout-id по UEFI-пути контроллера (AppleALC читает его раньше,
    # чем boot-args, и работает без alcid в обоих режимах).
    audio = getattr(profile, "audio", None)
    if audio is not None and getattr(audio, "layout_id", 0) and audio.pci_path:
        dp["Add"].setdefault(audio.pci_path, {})["layout-id"] = int(audio.layout_id)

    # Сеть: built-in делает контроллер «встроенным» — иначе iMessage и App Store
    # не считают машину настоящим Mac. Путь известен только из PnP.
    net = getattr(profile, "net", None)
    if net is not None:
        if net.eth_pci_path:
            dp["Add"].setdefault(net.eth_pci_path, {})["built-in"] = b"\x01"
        if net.wifi_pci_path:
            dp["Add"].setdefault(net.wifi_pci_path, {})["built-in"] = b"\x01"

    # --- Kernel ---
    k = cfg["Kernel"]
    k["Add"] = []   # заполняется сборщиком по выбранным kext
    if profile.cpu.vendor == "amd":
        k["Quirks"]["ProvideCurrentCpuInfo"] = True
        k["Emulate"]["DummyPowerManagement"] = True
        k["Patch"] = []  # заполняется AMD_Vanilla в сборщике
    else:
        cfg["Kernel"]["Patch"] = []
        if _is_pentium_celeron(profile):
            # сообщество (Lux Darkus): Pentium/Celeron 7–12 gen запускаются только
            # с подменой CPUID и DummyPowerManagement, иначе паника
            # AppleIntelCPUPowerManagement на старте.
            k["Emulate"]["Cpuid1Data"] = bytes([0xA0, 0x06, 0x03, 0x00] + [0] * 12)
            k["Emulate"]["Cpuid1Mask"] = bytes([0xFF] * 4 + [0] * 12)
            k["Emulate"]["DummyPowerManagement"] = True

    # Broadcom Wi-Fi на Sonoma 14+: штатный IOSkywalkFamily не даёт
    # загрузиться legacy-драйверу из набора OCLP — исключаем его на 23.x+.
    if ((profile.net.wifi_chipset or "").lower() == "broadcom"
            and _patch_on(options, "wifi_broadcom_efi")
            and _macos_major(options.target_macos) >= 14):
        k["Block"] = [{
            "Arch": "x86_64",
            "Comment": "Broadcom legacy Wi-Fi: IOSkywalk downgrade",
            "Enabled": True,
            "Identifier": "com.apple.iokit.IOSkywalkFamily",
            "MaxKernel": "",
            "MinKernel": "23.0.0",
            "Strategy": "Exclude",
        }]

    # --- Booter: квирки под AMD (Ryzen) ---
    if profile.cpu.vendor == "amd":
        bq = cfg["Booter"]["Quirks"]
        bq["RebuildAppleMemoryMap"] = True
        bq["EnableWriteUnprotector"] = False
        bq["SyncRuntimePermissions"] = True

    # --- Misc → Boot ---
    cfg["Misc"]["Boot"] = cfg["Misc"]["Boot"]
    if getattr(options, "gui_picker", False):
        # Графическое меню: OpenCanopy читает иконки из EFI/OC/Resources
        boot = cfg["Misc"]["Boot"]
        boot["PickerMode"] = "External"
        boot["PickerVariant"] = "Acidanthera\\GoldenGate"
        boot["PickerAttributes"] = 17

    if getattr(options, "audio_dxe", False):
        # AudioDxe мало подключить драйвером: без AudioSupport звука нет.
        aud = cfg["UEFI"]["Audio"]
        aud["AudioSupport"] = True
        aud["PlayChime"] = "Auto"
        pci = getattr(getattr(profile, "audio", None), "pci_path", "") or ""
        if pci:
            aud["AudioDevice"] = pci

    # --- macOS-версия влияет на SecureBootModel и boot-args ---
    _apply_macos_model(cfg, options.target_macos, profile)

    # --- NVRAM ---
    nv = cfg["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]
    if options.disable_sip:
        # меняем только csr-active-config, не теряя boot-args и прочие ключи
        nv["csr-active-config"] = bytes([0x67, 0, 0, 0])
    if _patch_on(options, "security_root"):
        # root-патчи OCLP требуют частично отключённого SIP: 0x03080000
        nv["csr-active-config"] = bytes([0x00, 0x08, 0x03, 0x00])
    if (_patch_on(options, "oclp_amfi")
            and _macos_major(options.target_macos) >= 14):
        # OCLP/AMFIPass читают флаг из NVRAM; в Delete его нет, значит переживёт перезагрузку
        nv["OCLP-Settings"] = "-allow_amfi"
    # --- Аудио: без alcid AppleALC не знает layout, и звука нет.
    # В macOS 26 AppleHDA удалён, поэтому alcid бесполезен (Dortania Tahoe).
    layout_id = getattr(profile.audio, "layout_id", 0) if profile.audio else 0
    if (layout_id and _patch_on(options, "audio_alcid")
            and (profile.audio.codec or "").lower().startswith("alc")
            and _macos_major(options.target_macos) < 26):
        boot_args = str(nv.get("boot-args") or "")
        if "alcid=" not in boot_args:
            nv["boot-args"] = f"{boot_args} alcid={layout_id}".strip()
    # Navi: без agdpmod=pikera чёрный экран (Dortania: нужен всем Navi)
    if is_navi_gpu(profile.dgpu) and _patch_on(options, "gpu_navi_agdp"):
        boot_args = str(nv.get("boot-args") or "")
        if "agdpmod=pikera" not in boot_args:
            nv["boot-args"] = f"{boot_args} agdpmod=pikera".strip()
    if options.disable_dgpu and profile.dgpu:
        # WhateverGreen: не поднимать внешнюю видеокарту вовсе
        boot_args = str(nv.get("boot-args") or "")
        if "-wegnoegpu" not in boot_args:
            nv["boot-args"] = f"{boot_args} -wegnoegpu".strip()
    # macOS 26: Intel Bluetooth требует отдельного boot-arg (Dortania Tahoe)
    if _patch_on(options, "bt_intel_26") and _macos_major(options.target_macos) >= 26:
        boot_args = str(nv.get("boot-args") or "")
        if "-ibtcompatbeta" not in boot_args:
            nv["boot-args"] = f"{boot_args} -ibtcompatbeta".strip()
    # OTA с 14.4: RestrictEvents + revpatch=sbvmm при SecureBootModel Disabled
    if _patch_on(options, "ota_updates") and _macos_major(options.target_macos) >= 14:
        boot_args = str(nv.get("boot-args") or "")
        if "revpatch=sbvmm" not in boot_args:
            nv["boot-args"] = f"{boot_args} revpatch=sbvmm".strip()


    # --- SMBIOS: инжектим сгенерированные данные в PlatformInfo ---
    if options.custom_smbios:
        _apply_smbios(cfg, options.custom_smbios)
    else:
        # без полного SMBIOS конфиг не проходит ocvalidate («unknown model»),
        # поэтому всегда подставляем модель, поддерживающую целевую macOS
        model = smbios_model_for(profile, options.target_macos)
        if model:
            cfg["PlatformInfo"]["Generic"]["SystemProductName"] = model

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
            "Drivers": [
                {
                    "Path": "OpenRuntime.efi",
                    "Enabled": True,
                    "Comment": "Runtime services: NVRAM, slide, boot var routing",
                    "Arguments": "",
                    "HideVerbose": False,
                    "LoadEarly": False,
                },
                {
                    "Path": "OpenHfsPlus.efi",
                    "Enabled": True,
                    "Comment": "HFS+ driver for recovery and installers",
                    "Arguments": "",
                    "HideVerbose": False,
                    "LoadEarly": False,
                },
            ],
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

