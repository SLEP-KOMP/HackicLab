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

from dataclasses import dataclass

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
        ssdts=("SSDT-EC-USBX", "SSDT-PLUG-AMD"),
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
        ssdts=("SSDT-EC-USBX", "SSDT-PLUG-AMD"),
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
        ssdts=("SSDT-EC-USBX", "SSDT-PLUG-AMD"),
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
        ssdts=("SSDT-EC-USBX", "SSDT-PLUG-AMD"),
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
               "itlwm + HeliPort или AirportItlwm"),
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
        ssdts=("SSDT-EC-USBX", "SSDT-PLUG-AMD"),
        quirks=("Kernel: AMD Vanilla (Zen, 16 ядер)", "Booter: ResizeAppleGpuBars=0"),
        note="Многопоточность ограничена: патчи ядра рассчитаны на 8–16 потоков, "
             "на 32 потоках возможны зависания. Для работы нужен тщательный тюнинг.",
        note_en="Multithreading is limited: kernel patches target 8–16 threads and may "
                "hang on 32. Expect heavy tuning.",
        sources=("oc_amd", "amd_osx", "tonymacx86"),
        url="https://forum.amd-osx.com/",
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
    """Ближайшие записи каталога под профиль: по совпадению слов в описании."""
    words = _profile_words(profile)
    if not words:
        return []
    scored: list[tuple[int, HwConfig]] = []
    for cfg in CONFIGS:
        hay = _haystack(cfg)
        score = sum(1 for w in words if w in hay)
        if cfg.category in ("laptop",) and "laptop" in words:
            score += 2
        if cfg.category in ("desktop_intel", "desktop_amd") and "desktop" in words:
            score += 1
        if score:
            scored.append((score, cfg))
    scored.sort(key=lambda pair: (-pair[0], pair[1].key))
    return [cfg for _, cfg in scored[:limit]]
