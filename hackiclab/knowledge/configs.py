"""Каталог типовых конфигураций для Hackintosh.

Здесь собраны не «чужие EFI», а описания связок «платформа + CPU + GPU + macOS»,
которые сообщество считает рабочими: настольные Intel и AMD, ноутбуки, мини-ПК
и рабочие станции. Для каждой связки указано, какие kext/SSDT нужны, какой это
тип поддержки (нативная / с патчами / с ограничениями) и где сверяться.

Данные не скачаны из чужого репозитория: это собранная вручную сводка по
публичным гайдам Dortania, AMD OS X, OpenCore Legacy Patcher и темам сообщества.
Ссылки на первоисточники лежат в поле ``sources`` и в ``knowledge.sources``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

# --- категории ---
CAT_DESKTOP_INTEL = "desktop_intel"
CAT_DESKTOP_AMD = "desktop_amd"
CAT_LAPTOP = "laptop"
CAT_MINI = "mini"
CAT_WORKSTATION = "workstation"

CATEGORIES: tuple[str, ...] = (
    CAT_DESKTOP_INTEL, CAT_DESKTOP_AMD, CAT_LAPTOP, CAT_MINI, CAT_WORKSTATION,
)

# --- тип поддержки ---
STATUS_NATIVE = "native"       # работает нативно, без патчей ядра
STATUS_PATCHED = "patched"     # нужны AMD-патчи, OCLP или USB-map
STATUS_LIMITED = "limited"     # работает частично (нет Wi-Fi, нет сна и т.п.)

STATUSES: tuple[str, ...] = (STATUS_NATIVE, STATUS_PATCHED, STATUS_LIMITED)


@dataclass(frozen=True)
class HwConfig:
    """Одна типовая связка железа."""

    key: str
    category: str
    title: str
    title_en: str
    cpu: str
    gpu: str
    macos: str                    # «Ventura – Sonoma»
    status: str
    kexts: tuple[str, ...] = ()
    ssdts: tuple[str, ...] = ()
    quirks: tuple[str, ...] = ()
    note: str = ""
    note_en: str = ""
    sources: tuple[str, ...] = ()
    url: str = ""
    # --- структурированные данные: нужны проверке поддержки и подбору ---
    vendor: str = "intel"          # intel / amd
    generation: int = 0            # поколение Intel или семейство Zen
    platform: str = "desktop"      # desktop / laptop / mini / workstation
    igpu: str = ""                 # device-id iGPU, hex
    dgpu: str = ""                 # device-id dGPU, hex
    macos_min: str = ""            # самая старая рабочая версия
    macos_max: str = ""            # потолок платформы

    def text(self, lang: str = "ru") -> str:
        return self.note_en if lang == "en" else self.note

    def heading(self, lang: str = "ru") -> str:
        return self.title_en if lang == "en" else self.title


CONFIGS: tuple[HwConfig, ...] = (
    # ---------------- настольные Intel ----------------
    HwConfig(
        "intel_coffee_lake",
        CAT_DESKTOP_INTEL,
        "Intel Coffee Lake · i5-9400 + UHD 630 + RX 580",
        "Intel Coffee Lake · i5-9400 + UHD 630 + RX 580",
        cpu="Intel Core i5-9400 / i5-9600K",
        gpu="UHD 630 (iGPU) + Radeon RX 580",
        macos="Ventura 13 – Sonoma 14",
        status=STATUS_NATIVE,
        kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "IntelMausi"),
        ssdts=("SSDT-PLUG", "SSDT-EC-USBX", "SSDT-PNLF не нужен"),
        quirks=("SATA: AhciPortHotPlug", "Booter: AvoidRuntimeDefrag, EnableSafeModeSlide"),
        note="Самый предсказуемый десктопный вариант: iGPU выводит картинку, RX 580 "
             "даёт аппаратное ускорение. SMBIOS — iMac19,1 или iMacPro1,1 при "
             "headless-режиме iGPU.",
        note_en="The most predictable desktop mix: iGPU drives the display, RX 580 "
                "provides acceleration. Use SMBIOS iMac19,1 or iMacPro1,1 with a "
                "headless iGPU.",
        sources=("oc_guide", "gpu_amd", "efi_subhead"),
        url="https://dortania.github.io/OpenCore-Install-Guide/config.plist/comet-lake.html",
    ),
    HwConfig(
        "intel_skylake",
        CAT_DESKTOP_INTEL,
        "Intel Skylake · i5-6600K + HD 530",
        "Intel Skylake · i5-6600K + HD 530",
        cpu="Intel Core i5-6600K / i7-6700K",
        gpu="HD Graphics 530",
        macos="Big Sur 11 – Monterey 12",
        status=STATUS_NATIVE,
        kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "IntelMausi"),
        ssdts=("SSDT-PLUG", "SSDT-EC-USBX"),
        quirks=("DeviceProperties: AAPL,ig-platform-id 0x19120000",),
        note="Новые macOS требуют OCLP: Skylake нет в списке поддерживаемых Intel-маков "
             "начиная с Ventura. На Monterey работает штатно.",
        note_en="Newer macOS needs OCLP: Skylake Macs are unsupported from Ventura on. "
                "Works natively on Monterey.",
        sources=("oc_guide", "gpu_guide"),
        url="https://dortania.github.io/OpenCore-Install-Guide/config.plist/skylake.html",
    ),
    HwConfig(
        "intel_comet_lake",
        CAT_DESKTOP_INTEL,
        "Intel Comet Lake · i5-10400 + UHD 630 + RX 6600",
        "Intel Comet Lake · i5-10400 + UHD 630 + RX 6600",
        cpu="Intel Core i5-10400 / i7-10700",
        gpu="UHD 630 + Radeon RX 6600 (Navi 23)",
        macos="Monterey 12 – Sonoma 14",
        status=STATUS_NATIVE,
        kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "IntelMausi"),
        ssdts=("SSDT-PLUG", "SSDT-EC-USBX"),
        quirks=("Booter: ResizeAppleGpuBars=0",),
        note="Navi 23 (RX 6600) требует macOS 12.1+ и SMBIOS MacPro7,1. iGPU лучше "
             "перевести в headless, иначе возможны артефакты при выводе через dGPU.",
        note_en="Navi 23 (RX 6600) needs macOS 12.1+ and MacPro7,1 SMBIOS. Keep the "
                "iGPU headless to avoid artefacts when driving displays from the dGPU.",
        sources=("oc_guide", "gpu_amd"),
        url="https://dortania.github.io/OpenCore-Install-Guide/config.plist/comet-lake.html",
    ),
    HwConfig(
        "intel_haswell",
        CAT_DESKTOP_INTEL,
        "Intel Haswell · i5-4690 + HD 4600",
        "Intel Haswell · i5-4690 + HD 4600",
        cpu="Intel Core i5-4690 / i7-4790K",
        gpu="HD Graphics 4600",
        macos="Catalina 10.15 – Monterey 12",
        status=STATUS_LIMITED,
        kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "IntelMausi"),
        ssdts=("SSDT-PLUG", "SSDT-EC"),
        quirks=("Kernel: AppleCpuPmCfgLock, AppleXcpmCfgLock",),
        note="Стабильная сборка для старых плат, но Ventura+ только через OCLP. "
             "Для ускорения лучше поставить Polaris-карту.",
        note_en="A stable build for older boards, but Ventura+ only via OCLP. Add a "
                "Polaris GPU for acceleration.",
        sources=("oc_guide", "gpu_guide"),
        url="https://dortania.github.io/OpenCore-Install-Guide/config.plist/haswell.html",
    ),

    # ---------------- настольные AMD ----------------
    HwConfig(
        "amd_ryzen_3600",
        CAT_DESKTOP_AMD,
        "AMD Ryzen 5 3600 · B450 + RX 6600",
        "AMD Ryzen 5 3600 · B450 + RX 6600",
        cpu="AMD Ryzen 5 3600 (Zen 2)",
        gpu="Radeon RX 6600",
        macos="Ventura 13 – Sonoma 14",
        status=STATUS_PATCHED,
        kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "AppleMCEReporterDisabler"),
        ssdts=("SSDT-EC-USBX",),
        quirks=("Kernel: AMD Vanilla patches", "Booter: RebuildAppleMemoryMap"),
        note="Обязательны патчи AMD Vanilla под конкретное число ядер. SMBIOS — "
             "MacPro7,1. USB-порты нужно картировать, иначе часть портов не работает.",
        note_en="AMD Vanilla patches are mandatory and must match the core count. Use "
                "MacPro7,1 SMBIOS and map USB ports, otherwise some ports stay dead.",
        sources=("oc_amd", "amd_osx", "efi_mikigal", "efi_maxritz"),
        url="https://dortania.github.io/OpenCore-Install-Guide/AMD/zen.html",
    ),
    HwConfig(
        "amd_ryzen_5800x",
        CAT_DESKTOP_AMD,
        "AMD Ryzen 7 5800X · B550 + RX 6800",
        "AMD Ryzen 7 5800X · B550 + RX 6800",
        cpu="AMD Ryzen 7 5800X (Zen 3)",
        gpu="Radeon RX 6800 (Navi 21)",
        macos="Monterey 12.1 – Sonoma 14",
        status=STATUS_PATCHED,
        kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "AppleMCEReporterDisabler"),
        ssdts=("SSDT-EC-USBX",),
        quirks=("Kernel: AMD Vanilla (Zen 3)", "Booter: ResizeAppleGpuBars=0"),
        note="Navi 21 требует macOS 12.1+; на 12.0 ускорения не будет. Патчи Zen 3 "
             "отличаются от Zen 2 — не смешивайте наборы.",
        note_en="Navi 21 needs macOS 12.1+; no acceleration on 12.0. Zen 3 patches "
                "differ from Zen 2 — do not mix the sets.",
        sources=("oc_amd", "amd_osx", "gpu_amd"),
        url="https://dortania.github.io/OpenCore-Install-Guide/AMD/zen.html",
    ),
    HwConfig(
        "amd_ryzen_2600",
        CAT_DESKTOP_AMD,
        "AMD Ryzen 5 2600 · B450 + RX 580",
        "AMD Ryzen 5 2600 · B450 + RX 580",
        cpu="AMD Ryzen 5 2600 (Zen+)",
        gpu="Radeon RX 580 (Polaris)",
        macos="Catalina 10.15 – Ventura 13",
        status=STATUS_PATCHED,
        kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "AppleMCEReporterDisabler"),
        ssdts=("SSDT-EC-USBX",),
        quirks=("Kernel: AMD Vanilla (Zen+)",),
        note="Дешёвая рабочая связка. Осторожно с китайскими RX 580 2048SP: у них "
             "другой device-id и ускорение не включается без прошивки VBIOS.",
        note_en="A cheap working combo. Beware of Chinese RX 580 2048SP cards: a "
                "different device-id means no acceleration without a VBIOS flash.",
        sources=("oc_amd", "rx580_2048sp", "efi_subhead"),
        url="https://dortania.github.io/OpenCore-Install-Guide/AMD/zen.html",
    ),

    # ---------------- ноутбуки ----------------
    HwConfig(
        "laptop_thinkpad_t480",
        CAT_LAPTOP,
        "Lenovo ThinkPad T480 · i5-8250U + UHD 620",
        "Lenovo ThinkPad T480 · i5-8250U + UHD 620",
        cpu="Intel Core i5-8250U (Kaby Lake-R)",
        gpu="UHD Graphics 620",
        macos="Catalina 10.15 – Sonoma 14",
        status=STATUS_PATCHED,
        kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "VoodooPS2Controller",
               "SMCBatteryManager", "USBToolBox/UTBMap"),
        ssdts=("SSDT-PLUG", "SSDT-EC-USBX", "SSDT-PNLF", "SSDT-GPRW", "SSDT-XOSI"),
        quirks=("Kernel: XhciPortLimit только для Catalina", "Booter: RebuildAppleMemoryMap"),
        note="Классика для хакintosh-ноутбуков: работают тачпад, яркость, батарея. "
             "Патч сна GPRW и USB-map обязательны, иначе ноутбук не просыпается.",
        note_en="The classic hackintosh laptop: touchpad, brightness and battery work. "
                "The GPRW sleep patch and a USB map are required for reliable wake.",
        sources=("oc_guide", "laptop_guide", "itlwm_compat"),
        url="https://dortania.github.io/OpenCore-Install-Guide/config-laptop.plist/kaby-lake.html",
    ),
    HwConfig(
        "laptop_xps_9360",
        CAT_LAPTOP,
        "Dell XPS 13 9360 · i7-7500U + HD 620",
        "Dell XPS 13 9360 · i7-7500U + HD 620",
        cpu="Intel Core i7-7500U (Kaby Lake)",
        gpu="HD Graphics 620",
        macos="Big Sur 11 – Ventura 13",
        status=STATUS_PATCHED,
        kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "VoodooPS2Controller",
               "SMCBatteryManager"),
        ssdts=("SSDT-PLUG", "SSDT-EC-USBX", "SSDT-PNLF"),
        quirks=("Kernel: AppleCpuPmCfgLock", "Booter: ProtectMemoryRegions"),
        note="Wi-Fi зависит от модуля: с Killer/Qualcomm нужен USB-адаптер, с "
             "заменённым BCM94360 — работает нативно, но на Sonoma нужен OCLP.",
        note_en="Wi-Fi depends on the module: Killer/Qualcomm needs a USB dongle, a "
                "swapped BCM94360 works natively but needs OCLP on Sonoma.",
        sources=("oc_guide", "laptop_guide", "wireless_guide"),
        url="https://dortania.github.io/OpenCore-Install-Guide/config-laptop.plist/kaby-lake.html",
    ),
    HwConfig(
        "laptop_thinkpad_x230",
        CAT_LAPTOP,
        "Lenovo ThinkPad X230 · i5-3320M + HD 4000",
        "Lenovo ThinkPad X230 · i5-3320M + HD 4000",
        cpu="Intel Core i5-3320M (Ivy Bridge)",
        gpu="HD Graphics 4000",
        macos="Catalina 10.15 – Big Sur 11",
        status=STATUS_LIMITED,
        kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "VoodooPS2Controller",
               "SMCBatteryManager"),
        ssdts=("SSDT-PLUG", "SSDT-EC", "SSDT-PNLF"),
        quirks=("Kernel: AppleCpuPmCfgLock",),
        note="Старый, но очень популярный ноутбук. Monterey+ только с OCLP: "
             "Ivy Bridge исключён из поддерживаемых моделей.",
        note_en="Old but very popular. Monterey+ only with OCLP: Ivy Bridge was dropped "
                "from the supported model list.",
        sources=("oc_guide", "laptop_guide", "oclp"),
        url="https://dortania.github.io/OpenCore-Install-Guide/config-laptop.plist/ivy-bridge.html",
    ),
    HwConfig(
        "laptop_ideapad_3",
        CAT_LAPTOP,
        "Lenovo IdeaPad 3 · Ryzen 5 3500U + Vega 8",
        "Lenovo IdeaPad 3 · Ryzen 5 3500U + Vega 8",
        cpu="AMD Ryzen 5 3500U (Zen+)",
        gpu="Radeon Vega 8 (интегрированная)",
        macos="не рекомендуется",
        status=STATUS_LIMITED,
        kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleMCEReporterDisabler"),
        ssdts=("SSDT-EC-USBX",),
        quirks=("Kernel: AMD Vanilla",),
        note="Мобильные AMD APU поддерживаются крайне ограниченно: нет ускорения "
             "графики, часто не работают сон и тачпад. Как учебный кейс — да, как "
             "рабочая машина — нет.",
        note_en="Mobile AMD APUs are barely supported: no GPU acceleration, sleep and "
                "touchpad often fail. Fine as a learning case, not as a daily driver.",
        sources=("oc_amd", "anti_hackintosh_net"),
        url="https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/",
    ),

    # ---------------- мини-ПК ----------------
    HwConfig(
        "mini_nuc8",
        CAT_MINI,
        "Intel NUC8i5BEH · i5-8259U + Iris Plus 655",
        "Intel NUC8i5BEH · i5-8259U + Iris Plus 655",
        cpu="Intel Core i5-8259U (Coffee Lake-U)",
        gpu="Iris Plus 655",
        macos="Catalina 10.15 – Sonoma 14",
        status=STATUS_PATCHED,
        kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "IntelMausi",
               "itlwm", "AirportItlwm"),
        ssdts=("SSDT-PLUG", "SSDT-EC-USBX", "SSDT-PNLF не нужен"),
        quirks=("DeviceProperties: ig-platform-id 0x3EA50009",),
        note="Популярный «маленький мак». Слот M.2 освобождается под второй диск с "
             "macOS; встроенный Wi-Fi Intel требует itlwm или замены на BCM.",
        note_en="A popular 'little Mac'. The M.2 slot is free for a second macOS disk; "
                "the onboard Intel Wi-Fi needs itlwm or a BCM swap.",
        sources=("oc_guide", "itlwm_compat", "efi_subhead"),
        url="https://dortania.github.io/OpenCore-Install-Guide/config.plist/coffee-lake.html",
    ),
    HwConfig(
        "mini_nuc10",
        CAT_MINI,
        "Intel NUC10i7FNH · i7-10710U + UHD 620",
        "Intel NUC10i7FNH · i7-10710U + UHD 620",
        cpu="Intel Core i7-10710U (Comet Lake-U)",
        gpu="UHD Graphics 620",
        macos="Big Sur 11 – Sonoma 14",
        status=STATUS_PATCHED,
        kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "IntelMausi"),
        ssdts=("SSDT-PLUG", "SSDT-EC-USBX"),
        quirks=("DeviceProperties: ig-platform-id 0x9BC80003",),
        note="Часть экземпляров требует USB-map из-за нестандартного контроллера. "
             "Проверьте, что у вас не Comet Lake-H с другим id.",
        note_en="Some units need a USB map because of a non-standard controller. Make "
                "sure you have Comet Lake-U and not the -H variant.",
        sources=("oc_guide", "itlwm_compat"),
        url="https://dortania.github.io/OpenCore-Install-Guide/config.plist/comet-lake.html",
    ),

    # ---------------- рабочие станции ----------------
    HwConfig(
        "ws_xeon_e5_v3",
        CAT_WORKSTATION,
        "Xeon E5-2670 v3 · X99 + RX 6600",
        "Xeon E5-2670 v3 · X99 + RX 6600",
        cpu="Intel Xeon E5-2670 v3 (Haswell-EP)",
        gpu="Radeon RX 6600",
        macos="Monterey 12 – Ventura 13",
        status=STATUS_PATCHED,
        kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "AppleIntelE1000e"),
        ssdts=("SSDT-PLUG", "SSDT-EC-USBX"),
        quirks=("Kernel: AppleXcpmCfgLock, X86PlatformPlugin", "Booter: AvoidRuntimeDefrag"),
        note="Нет iGPU и часто нет AVX2-зависимых путей: SMBIOS MacPro7,1, "
             "аппаратное ускорение только через dGPU. Патч PLUG обязателен.",
        note_en="No iGPU and often no AVX2 paths: use MacPro7,1 SMBIOS, acceleration "
                "only via the dGPU. The PLUG patch is mandatory.",
        sources=("oc_guide", "gpu_guide", "tonymacx86"),
        url="https://dortania.github.io/OpenCore-Install-Guide/config.plist/haswell.html",
    ),
    HwConfig(
        "ws_threadripper",
        CAT_WORKSTATION,
        "Threadripper 1950X · X399 + RX 580",
        "Threadripper 1950X · X399 + RX 580",
        cpu="AMD Ryzen Threadripper 1950X (Zen)",
        gpu="Radeon RX 580",
        macos="Catalina 10.15 – Big Sur 11",
        status=STATUS_LIMITED,
        kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "AppleMCEReporterDisabler"),
        ssdts=("SSDT-EC-USBX",),
        quirks=("Kernel: AMD Vanilla (Zen, 16 ядер)", "Booter: ResizeAppleGpuBars=0"),
        note="Многопоточность ограничена: патчи ядра рассчитаны на 8–16 потоков, "
             "на 32 потоках возможны зависания. Для работы нужен тщательный тюнинг.",
        note_en="Multithreading is limited: kernel patches target 8–16 threads and may "
                "hang on 32. Expect heavy tuning.",
        sources=("oc_amd", "amd_osx", "tonymacx86"),
        url="https://forum.amd-osx.com/",
    ),
)


# Структурированные поля для уже описанных связок: нужны проверке поддержки.
# Значения сверены с официальным списком Mac и потолками из oc_platforms.
_STRUCT: dict[str, dict] = {
    "intel_coffee_lake": {"vendor": "intel", "generation": 9, "platform": "desktop",
                              "igpu": "3E92", "dgpu": "67DF", "macos_min": "Ventura",
                              "macos_max": "Sequoia"},
    "intel_skylake": {"vendor": "intel", "generation": 6, "platform": "desktop",
                          "igpu": "1912", "macos_min": "Big Sur", "macos_max": "Monterey"},
    "intel_comet_lake": {"vendor": "intel", "generation": 10, "platform": "desktop",
                             "igpu": "9BC5", "dgpu": "73FF", "macos_min": "Monterey",
                             "macos_max": "Sequoia"},
    "intel_haswell": {"vendor": "intel", "generation": 4, "platform": "desktop",
                          "igpu": "0412", "macos_min": "Catalina", "macos_max": "Monterey"},
    "amd_ryzen_3600": {"vendor": "amd", "generation": 10, "platform": "desktop",
                           "dgpu": "73FF", "macos_min": "Ventura", "macos_max": "Sequoia"},
    "amd_ryzen_5800x": {"vendor": "amd", "generation": 12, "platform": "desktop",
                            "dgpu": "73BF", "macos_min": "Monterey", "macos_max": "Sequoia"},
    "amd_ryzen_2600": {"vendor": "amd", "generation": 9, "platform": "desktop",
                           "dgpu": "67DF", "macos_min": "Catalina", "macos_max": "Sequoia"},
    "laptop_thinkpad_t480": {"vendor": "intel", "generation": 8, "platform": "laptop",
                                 "igpu": "5916", "macos_min": "Catalina",
                                 "macos_max": "Sonoma"},
    "laptop_xps_9360": {"vendor": "intel", "generation": 7, "platform": "laptop",
                            "igpu": "5916", "macos_min": "Big Sur", "macos_max": "Ventura"},
    "laptop_thinkpad_x230": {"vendor": "intel", "generation": 3, "platform": "laptop",
                                 "igpu": "0166", "macos_min": "Catalina",
                                 "macos_max": "Catalina"},
    "laptop_ideapad_3": {"vendor": "amd", "generation": 9, "platform": "laptop",
                             "macos_min": "", "macos_max": ""},
    "mini_nuc8": {"vendor": "intel", "generation": 8, "platform": "mini",
                      "igpu": "3EA5", "macos_min": "Catalina", "macos_max": "Sonoma"},
    "mini_nuc10": {"vendor": "intel", "generation": 10, "platform": "mini",
                       "igpu": "9BC8", "macos_min": "Big Sur", "macos_max": "Sequoia"},
    "ws_xeon_e5_v3": {"vendor": "intel", "generation": 4, "platform": "workstation",
                          "dgpu": "73FF", "macos_min": "Monterey", "macos_max": "Monterey"},
    "ws_threadripper": {"vendor": "amd", "generation": 8, "platform": "workstation",
                            "dgpu": "67DF", "macos_min": "Catalina", "macos_max": "Ventura"},
}

CONFIGS = tuple(replace(c, **_STRUCT[c.key]) for c in CONFIGS if c.key in _STRUCT) + tuple(
    c for c in CONFIGS if c.key not in _STRUCT
)

# Новые записи каталога: старые платформы, свежие десктопы и ещё ноутбуки.
CONFIGS = (*CONFIGS, HwConfig("intel_sandy_desktop", CAT_DESKTOP_INTEL, "Intel Sandy Bridge · i5-2500K + HD 3000", "Intel Sandy Bridge · i5-2500K + HD 3000", cpu="Intel Core i5-2500K / i7-2600K", gpu="HD Graphics 3000", macos="High Sierra 10.13", status=STATUS_LIMITED, kexts=("FakeSMC", "WhateverGreen", "AppleALC", "IntelMausiEthernet"), ssdts=("SSDT-EC",), quirks=("Kernel: AppleCpuPmCfgLock, AppleXcpmCfgLock",), note="Только High Sierra: драйвер HD 3000 в более новых системах удалён. " "Для Sandy Bridge используется FakeSMC, а не VirtualSMC.", note_en="High Sierra only: the HD 3000 driver was removed later. Sandy Bridge " "uses FakeSMC instead of VirtualSMC.", sources=("oc_guide", "gpu_guide"), url="https://dortania.github.io/OpenCore-Install-Guide/config.plist/sandy-bridge.html", vendor="intel", generation=2, platform="desktop", igpu="0126", macos_min="High Sierra", macos_max="High Sierra"), HwConfig("intel_ivy_desktop", CAT_DESKTOP_INTEL, "Intel Ivy Bridge · i5-3570K + HD 4000", "Intel Ivy Bridge · i5-3570K + HD 4000", cpu="Intel Core i5-3570K / i7-3770K", gpu="HD Graphics 4000", macos="Mojave 10.14 – Catalina 10.15", status=STATUS_LIMITED, kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "IntelMausiEthernet"), ssdts=("SSDT-EC", "SSDT-PLUG"), quirks=("Kernel: AppleCpuPmCfgLock",), note="Catalina — последняя система с драйвером HD 4000. Big Sur и новее " "только через OCLP и без аппаратного ускорения графики.", note_en="Catalina is the last release with an HD 4000 driver. Big Sur and " "newer only via OCLP and without graphics acceleration.", sources=("oc_guide", "gpu_guide", "oclp"), url="https://dortania.github.io/OpenCore-Install-Guide/config.plist/ivy-bridge.html", vendor="intel", generation=3, platform="desktop", igpu="0162", macos_min="Mojave", macos_max="Catalina"), HwConfig("intel_kaby_desktop", CAT_DESKTOP_INTEL, "Intel Kaby Lake · i5-7600K + HD 630", "Intel Kaby Lake · i5-7600K + HD 630", cpu="Intel Core i5-7600K / i7-7700K", gpu="HD Graphics 630", macos="Big Sur 11 – Ventura 13", status=STATUS_NATIVE, kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "IntelMausi"), ssdts=("SSDT-PLUG", "SSDT-EC-USBX"), quirks=("DeviceProperties: AAPL,ig-platform-id 0x59120000",), note="Стабильный десктоп без дискретной карты: HD 630 тянет интерфейс, " "SMBIOS — iMac18,3. Sonoma требует OCLP из-за платформы 2017 года.", note_en="A stable desktop without a dGPU: HD 630 drives the UI, SMBIOS " "iMac18,3. Sonoma needs OCLP because the platform is 2017-era.", sources=("oc_guide", "gpu_guide", "oclp"), url="https://dortania.github.io/OpenCore-Install-Guide/config.plist/kaby-lake.html", vendor="intel", generation=7, platform="desktop", igpu="5912", macos_min="Big Sur", macos_max="Ventura"), HwConfig("intel_raptor_desktop", CAT_DESKTOP_INTEL, "Intel Raptor Lake · i5-13600K + RX 6600", "Intel Raptor Lake · i5-13600K + RX 6600", cpu="Intel Core i5-13600K / i7-13700K", gpu="Radeon RX 6600 (iGPU не поддерживается)", macos="Ventura 13 – Sonoma 14", status=STATUS_PATCHED, kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "IntelMausi", "CpuTopologyRebuild", "RestrictEvents"), ssdts=("SSDT-PLUG", "SSDT-EC-USBX"), quirks=("Kernel: ProvideCurrentCpuInfo", "Booter: ResizeAppleGpuBars=0"), note="Нужны патчи топологии P+E ядер (CpuTopologyRebuild) и dGPU: iGPU " "Alder/Raptor не имеет драйвера. SMBIOS — MacPro7,1.", note_en="P+E core topology patches (CpuTopologyRebuild) and a dGPU are " "required: Alder/Raptor iGPUs have no driver. Use MacPro7,1 SMBIOS.", sources=("oc_guide", "gpu_amd", "oclp"), url="https://dortania.github.io/OpenCore-Install-Guide/config.plist/comet-lake.html", vendor="intel", generation=13, platform="desktop", dgpu="73FF", macos_min="Ventura", macos_max="Sonoma"), HwConfig("amd_zen1_1600", CAT_DESKTOP_AMD, "AMD Ryzen 5 1600 · B350 + RX 570", "AMD Ryzen 5 1600 · B350 + RX 570", cpu="AMD Ryzen 5 1600 (Zen)", gpu="Radeon RX 570 (Polaris)", macos="Catalina 10.15 – Ventura 13", status=STATUS_PATCHED, kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "AppleMCEReporterDisabler"), ssdts=("SSDT-EC-USBX", "SSDT-PLUG"), quirks=("Kernel: AMD Vanilla (Zen)",), note="Zen первого поколения капризнее Zen 2/3: патчи подбираются под " "конкретное число ядер, а часть плат требует RebuildAppleMemoryMap.", note_en="First-gen Zen is pickier than Zen 2/3: patches depend on the core " "count and some boards need RebuildAppleMemoryMap.", sources=("oc_amd", "amd_osx", "efi_subhead"), url="https://dortania.github.io/OpenCore-Install-Guide/AMD/zen.html", vendor="amd", generation=8, platform="desktop", dgpu="67DF", macos_min="Catalina", macos_max="Ventura"), HwConfig("laptop_thinkpad_t440p", CAT_LAPTOP, "Lenovo ThinkPad T440p · i5-4300M + HD 4600", "Lenovo ThinkPad T440p · i5-4300M + HD 4600", cpu="Intel Core i5-4300M (Haswell)", gpu="HD Graphics 4600", macos="Catalina 10.15 – Monterey 12", status=STATUS_PATCHED, kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "VoodooPS2Controller", "SMCBatteryManager"), ssdts=("SSDT-PLUG", "SSDT-EC-USBX", "SSDT-PNLF"), quirks=("Kernel: AppleCpuPmCfgLock",), note="Классический Haswell-ноутбук: работает до Monterey, дальше нужен OCLP. " "Аккуратно с Wi-Fi: штатный Intel 7260 требует itlwm.", note_en="A classic Haswell laptop: works up to Monterey, then OCLP. Mind the " "Wi-Fi: the stock Intel 7260 needs itlwm.", sources=("oc_guide", "laptop_guide", "itlwm_compat"), url="https://dortania.github.io/OpenCore-Install-Guide/config-laptop.plist/haswell.html", vendor="intel", generation=4, platform="laptop", igpu="0416", macos_min="Catalina", macos_max="Monterey"), HwConfig("mini_nuc7", CAT_MINI, "Intel NUC7i5BNH · i5-7260U + Iris Plus 640", "Intel NUC7i5BNH · i5-7260U + Iris Plus 640", cpu="Intel Core i5-7260U (Kaby Lake-U)", gpu="Iris Plus 640", macos="Big Sur 11 – Ventura 13", status=STATUS_PATCHED, kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "IntelMausi", "itlwm"), ssdts=("SSDT-PLUG", "SSDT-EC-USBX"), quirks=("DeviceProperties: ig-platform-id 0x59260000",), note="Компактный вариант под macOS без дискретной карты. Wi-Fi Intel 8265 " "работает через itlwm + HeliPort, Bluetooth — через IntelBluetoothFirmware.", note_en="A compact macOS box without a dGPU. The Intel 8265 Wi-Fi works via " "itlwm + HeliPort, Bluetooth via IntelBluetoothFirmware.", sources=("oc_guide", "itlwm_compat"), url="https://dortania.github.io/OpenCore-Install-Guide/config.plist/kaby-lake.html", vendor="intel", generation=7, platform="mini", igpu="5926", macos_min="Big Sur", macos_max="Ventura"), HwConfig("ws_x299_skylake_x", CAT_WORKSTATION, "Intel Core i9-7900X · X299 + RX 580", "Intel Core i9-7900X · X299 + RX 580", cpu="Intel Core i9-7900X (Skylake-X)", gpu="Radeon RX 580", macos="Monterey 12 – Sonoma 14", status=STATUS_NATIVE, kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "IntelMausi"), ssdts=("SSDT-PLUG", "SSDT-EC-USBX"), quirks=("Kernel: AppleXcpmCfgLock",), note="Skylake-X поддерживается iMac Pro 2017 вплоть до Sonoma/Sequoia: " "SMBIOS iMacPro1,1, ускорение только через dGPU.", note_en="Skylake-X is covered by the 2017 iMac Pro up to Sonoma/Sequoia: use " "iMacPro1,1 SMBIOS, acceleration only via the dGPU.", sources=("oc_guide", "gpu_guide", "tonymacx86"), url="https://dortania.github.io/OpenCore-Install-Guide/config.plist/skylake.html", vendor="intel", generation=6, platform="workstation", dgpu="67DF", macos_min="Monterey", macos_max="Sequoia"))


# Pentium/Celeron и APU Cezanne: то, чего не хватало по итогам сообщество.
CONFIGS = (*CONFIGS,
    HwConfig(
        "intel_pentium_g5400",
        CAT_DESKTOP_INTEL,
        "Intel Pentium Gold G5400 / Celeron + RX 580",
        "Intel Pentium Gold G5400 / Celeron + RX 580",
        cpu="Intel Pentium Gold G5400 / Celeron G5905",
        gpu="iGPU отключена + Radeon RX 580",
        macos="Ventura 13 – Sonoma 14",
        status=STATUS_PATCHED,
        kexts=("Lilu", "VirtualSMC", "WhateverGreen", "AppleALC", "IntelMausi"),
        ssdts=("SSDT-PLUG", "SSDT-EC"),
        quirks=("Kernel: Emulate Cpuid1Data A0060300…, DummyPowerManagement",),
        note="Pentium/Celeron 7–12 поколений: встроенная графика не поддерживается, "
             "нужна дискретная карта. macOS запускается с подменой CPUID и "
             "DummyPowerManagement, иначе паника AppleIntelCPUPowerManagement.",
        note_en="Pentium/Celeron 7th–12th gen: the iGPU is unsupported, a discrete GPU "
                "is required. Boot needs CPUID spoofing and DummyPowerManagement, "
                "otherwise AppleIntelCPUPowerManagement panics.",
        sources=("oc_guide", "gpu_amd"),
        url="
        vendor="intel", generation=10, platform="desktop", igpu="9BC8", dgpu="67DF",
        macos_min="Ventura", macos_max="Sonoma",
    ),
    HwConfig(
        "amd_ryzen_5600g",
        CAT_DESKTOP_AMD,
        "AMD Ryzen 5 5600G (Cezanne) + Vega 7",
        "AMD Ryzen 5 5600G (Cezanne) + Vega 7",
        cpu="AMD Ryzen 5 5600G / 5700G (Zen 3)",
        gpu="Radeon Vega 7 (NootedRed)",
        macos="Big Sur 11 – Sonoma 14",
        status=STATUS_PATCHED,
        kexts=("Lilu", "VirtualSMC", "NootedRed", "AppleALC"),
        ssdts=("SSDT-EC-USBX",),
        quirks=("Kernel: AMD Vanilla",),
        note="APU Cezanne: графику поднимает NootedRed вместо WhateverGreen. "
             "Нужны AMD-патчи ядра и проверка сна/USB — как на других Ryzen.",
        note_en="Cezanne APU: NootedRed provides graphics instead of WhateverGreen. "
                "AMD kernel patches and sleep/USB checks are required as on other Ryzen.",
        sources=("oc_amd", "amd_osx"),
        url="https://github.com/ChefKissInc/NootedRed",
        vendor="amd", generation=11, platform="desktop",
        macos_min="Big Sur", macos_max="Sonoma",
    ),
    HwConfig(
        "intel_core2_duo",
        CAT_DESKTOP_INTEL,
        "Intel Core 2 Duo E8400 + Radeon HD 5770",
        "Intel Core 2 Duo E8400 + Radeon HD 5770",
        cpu="Intel Core 2 Duo E8400 / Core 2 Quad Q9400",
        gpu="Radeon HD 5770",
        macos="High Sierra 10.13",
        status=STATUS_LIMITED,
        kexts=("FakeSMC", "WhateverGreen", "AppleALC", "RealtekRTL8111"),
        ssdts=("SSDT-EC",),
        quirks=("Kernel: AppleCpuPmCfgLock",),
        note="Core 2 Duo/Quad (Penryn, SSE4.1): максимум High Sierra. "
             "Используется FakeSMC вместо VirtualSMC, встроенная графика не "
             "работает — нужна дискретная карта с поддержкой High Sierra.",
        note_en="Core 2 Duo/Quad (Penryn, SSE4.1): High Sierra is the ceiling. "
                "Uses FakeSMC instead of VirtualSMC; the iGPU is unsupported, so a "
                "discrete GPU with High Sierra support is required.",
        sources=("oc_guide", "gpu_guide"),
        vendor="intel", generation=0, platform="desktop", dgpu="68B8",
        macos_min="High Sierra", macos_max="High Sierra",
    ),
)


def all_configs() -> tuple[HwConfig, ...]:
    return CONFIGS


def by_category(category: str) -> list[HwConfig]:
    return [c for c in CONFIGS if c.category == category]


def categories_of(configs: list[HwConfig] | tuple[HwConfig, ...] = CONFIGS) -> list[str]:
    """Категории в фиксированном порядке, только те, где есть записи."""
    present = {c.category for c in configs}
    return [c for c in CATEGORIES if c in present]


def _haystack(cfg: HwConfig) -> str:
    parts = [cfg.title, cfg.title_en, cfg.cpu, cfg.gpu, cfg.macos, cfg.note, cfg.note_en]
    parts.extend(cfg.kexts)
    parts.extend(cfg.ssdts)
    parts.extend(cfg.quirks)
    return " ".join(parts).lower()


def search_configs(query: str = "", category: str = "") -> list[HwConfig]:
    """Фильтр по подстроке (без учёта регистра) и категории."""
    q = (query or "").strip().lower()
    out = [c for c in CONFIGS if not category or c.category == category]
    if q:
        out = [c for c in out if q in _haystack(c)]
    return out


def _profile_words(profile) -> set[str]:
    if profile is None:
        return set()
    words: set[str] = set()
    cpu = getattr(profile, "cpu", None)
    if cpu is not None:
        for attr in ("name", "codename", "oc_platform", "vendor", "brand"):
            value = str(getattr(cpu, attr, "") or "").lower()
            words.update(w for w in value.replace("-", " ").split() if len(w) > 2)
    gpu = getattr(profile, "dgpu", None) or getattr(profile, "igpu", None)
    if gpu is not None:
        name = str(getattr(gpu, "name", "") or "").lower()
        words.update(w for w in name.replace("-", " ").split() if len(w) > 2)
    platform = str(getattr(profile, "platform", "") or "").lower()
    if platform:
        words.add(platform)
    return words


def similar_configs(profile, limit: int = 3) -> list[HwConfig]:
    """Ближайшие записи каталога: поколение и платформа важнее совпадения слов.

    Раньше подбор шёл только по словам, поэтому «amd», «ryzen», «radeon» и
    «580» одинаково подходили и Zen 2, и Zen+, и вперёд выходила чужая сборка.
    """
    if profile is None:
        return []
    cpu = getattr(profile, "cpu", None)
    vendor = str(getattr(cpu, "vendor", "") or "").lower()
    generation = int(getattr(cpu, "generation", 0) or 0)
    platform = str(getattr(profile, "platform", "") or "").lower()
    dgpu = getattr(profile, "dgpu", None)
    dgpu_dev = str(getattr(dgpu, "device_id", "") or "").lower().replace("0x", "")

    words = _profile_words(profile)
    scored: list[tuple[int, HwConfig]] = []
    for cfg in CONFIGS:
        hay = _haystack(cfg)
        score = sum(1 for w in words if w in hay)
        if vendor and cfg.vendor == vendor:
            score += 3
        if generation and cfg.generation == generation:
            score += 5
        if platform and cfg.platform == platform:
            score += 2
        if dgpu_dev and str(cfg.dgpu or "").lower().replace("0x", "") == dgpu_dev:
            score += 3
        if score:
            scored.append((score, cfg))
    scored.sort(key=lambda pair: (-pair[0], pair[1].key))
    return [cfg for _, cfg in scored[:limit]]


