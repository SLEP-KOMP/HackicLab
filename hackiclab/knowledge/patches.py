"""Каталог патчей: что и зачем нужно применять под конкретное железо.

Патчи двух уровней:

- ``efi`` — правки ``config.plist``/набор кекстов, попадают в EFI при сборке;
- ``system`` — root-патчи внутри установленной macOS (kext в /S/L/E, кэш,
  amfi): применить их можно только с самой macOS, поэтому для них
  печатается пошаговая инструкция (OCLP), а не меняется EFI.

Каждый патч знает, для кого он нужен (``applies``) и можно ли включить его
автоматически (``auto``). Опасные/негарантированные патчи автоматически не
включаются — пользователь выбирает их сам.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..builder.config_gen import _macos_major
from .kexts import is_navi_gpu

#: Порядок для сравнения версий macOS (как в kexts.py, только мажоры).
_MAJOR = {"Catalina": 10, "Big Sur": 11, "Monterey": 12, "Ventura": 13,
          "Sonoma": 14, "Sequoia": 15, "Tahoe": 26, "Golden Gate": 27}


@dataclass(frozen=True)
class Patch:
    """Один патч: что делает, кому нужен и применяется ли сам."""

    id: str
    kind: str            # cpu / gpu / wifi / audio / boot
    scope: str           # efi / system
    title_ru: str
    title_en: str
    detail_ru: str
    detail_en: str
    auto: bool = True    # включать без явного выбора пользователя
    source: str = ""     # откуда правило (для отчёта)

    def title(self, lang: str = "ru") -> str:
        return self.title_en if lang.startswith("en") else self.title_ru

    def detail(self, lang: str = "ru") -> str:
        return self.detail_en if lang.startswith("en") else self.detail_ru


#: Патч нужен любому Ryzen: без него ядро macOS не стартует (CPUID/MSR).
P_AMD_KERNEL = Patch(
    "cpu_amd", "cpu", "efi",
    "Патчи ядра AMD Vanilla",
    "AMD Vanilla kernel patches",
    "Ryzen требует патчей AMD_Vanilla (Kernel → Patch): ядро macOS рассчитано "
    "на Intel CPUID/MSR. Сборщик подставляет их из репозитория AMD-OSX.",
    "Ryzen needs AMD_Vanilla patches (Kernel → Patch): the macOS kernel expects "
    "Intel CPUID/MSR. The builder injects them from the AMD-OSX repo.",
    source="AMD-OSX/AMD_Vanilla",
)

#: Подмена device-id для китайских RX 580 2048SP (6FDF → 67DF).
P_GPU_RX580_SPOOF = Patch(
    "gpu_rx580_spoof", "gpu", "efi",
    "RX 580 2048SP: подмена device-id на 67DF",
    "RX 580 2048SP: spoof device-id to 67DF",
    "Карта 6FDF не имеет драйвера, но это Polaris 20. Инжект device-id=0x67DF "
    "заставляет macOS видеть RX 570. Ускорение появляется не всегда: по "
    "сообществу надёжный путь — правка VBIOS (отдельный патч).",
    "6FDF has no driver, but it is Polaris 20. Injecting device-id=0x67DF makes "
    "macOS see an RX 570. Acceleration is not guaranteed: the reliable route "
    "reported by the community is a VBIOS edit (separate patch).",
    auto=False,
    source="Dortania GPU Buyers Guide (Polaris: verified spoof)",
)

#: Правка VBIOS: четыре байта device-id + имя карты.
P_GPU_RX580_VBIOS = Patch(
    "gpu_rx580_vbios", "gpu", "system",
    "RX 580 2048SP: правка VBIOS (0210DF6F → 0210DF67)",
    "RX 580 2048SP: VBIOS edit (0210DF6F → 0210DF67)",
    "Прошивка VBIOS карты: байты 02 10 DF 6F заменить на 02 10 DF 67, а имя "
    "F0 FD E6 0F — на F0 7D E6 07. Делается AMDVBFlash из DOS/Windows, "
    "с резервной копией исходного VBIOS. Риск кирпича — только со страховкой.",
    "Flash the card VBIOS: replace bytes 02 10 DF 6F with 02 10 DF 67 and the "
    "name F0 FD E6 0F with F0 7D E6 07 using AMDVBFlash from DOS/Windows, "
    "keeping a backup of the stock VBIOS. Brick risk — do it with a backup.",
    auto=False,
    source="Kemerd/rx580-2048sp-mac-egpu, Olarila guide",
)

#: Набор кекстов OCLP для Broadcom: без него Wi-Fi не поднимется на 14+.
P_WIFI_BCM_EFI = Patch(
    "wifi_broadcom_efi", "wifi", "efi",
    "Broadcom Wi-Fi: набор OCLP в EFI",
    "Broadcom Wi-Fi: OCLP kext set in EFI",
    "IOSkywalkFamily + IO80211FamilyLegacy + AMFIPass и блок штатного "
    "com.apple.iokit.IOSkywalkFamily. Apple вырезала драйверы Broadcom в "
    "macOS 14 (Sonoma), до Ventura карта работает нативно.",
    "IOSkywalkFamily + IO80211FamilyLegacy + AMFIPass plus a block of the stock "
    "com.apple.iokit.IOSkywalkFamily. Apple removed Broadcom drivers in macOS 14 "
    "(Sonoma); the card is native up to Ventura.",
    source="OpenCore-Legacy-Patcher payloads, Dortania",
)

#: Root-патч OCLP: возвращает драйвер Wi-Fi в систему.
P_WIFI_BCM_ROOT = Patch(
    "wifi_broadcom_root", "wifi", "system",
    "Broadcom Wi-Fi: root-патч OCLP",
    "Broadcom Wi-Fi: OCLP root patch",
    "После установки запустить OpenCore Legacy Patcher → Post-Install Root "
    "Patch, иначе набор кекстов не заработает. Нужны SIP 03080000 и "
    "SecureBootModel Disabled; root-патч повторять после каждого обновления.",
    "After installation run OpenCore Legacy Patcher → Post-Install Root Patch, "
    "otherwise the kext set does nothing. Requires SIP 03080000 and "
    "SecureBootModel Disabled; re-apply the root patch after every update.",
    source="5T33Z0 WiFi_Sonoma, chriswayg Broadcom guide",
)

#: Звук: AppleALC требует layout-id, иначе звука нет.
P_AUDIO_ALCID = Patch(
    "audio_alcid", "audio", "efi",
    "Звук: layout-id (alcid)",
    "Audio: layout-id (alcid)",
    "Для кодека подбирается layout-id из базы AppleALC и пишется в "
    "DeviceProperties и boot-args. Без него AppleALC не знает раскладку.",
    "A layout-id is picked from the AppleALC database and written to "
    "DeviceProperties and boot-args. Without it AppleALC has no layout.",
    source="AppleALC",
)

#: Navi: без agdpmod=pikera чёрный экран.
P_GPU_NAVI_AGDP = Patch(
    "gpu_navi_agdp", "gpu", "efi",
    "Navi: agdpmod=pikera",
    "Navi: agdpmod=pikera",
    "Всем картам Navi нужен boot-arg agdpmod=pikera, иначе чёрный экран.",
    "All Navi cards need the agdpmod=pikera boot-arg, otherwise a black screen.",
    source="Dortania GPU Buyers Guide",
)

#: Всё, что требует root-патча, требует и ослабленной защиты.
P_SECURITY_FOR_ROOT = Patch(
    "security_root", "boot", "efi",
    "Ослабить защиту под root-патчи",
    "Relax security for root patches",
    "csr-active-config=03080000 (частично отключённый SIP) и SecureBootModel "
    "Disabled — без этого OCLP не сможет пропатчить системный том.",
    "csr-active-config=03080000 (partially disabled SIP) and SecureBootModel "
    "Disabled — without them OCLP cannot patch the system volume.",
    source="5T33Z0 WiFi_Sonoma",
)

CATALOG: tuple[Patch, ...] = (
    P_AMD_KERNEL, P_GPU_RX580_SPOOF, P_GPU_RX580_VBIOS,
    P_WIFI_BCM_EFI, P_WIFI_BCM_ROOT, P_AUDIO_ALCID,
    P_GPU_NAVI_AGDP, P_SECURITY_FOR_ROOT,
)


def _dev(profile) -> str:
    gpu = getattr(profile, "dgpu", None)
    if gpu is None or (gpu.vendor or "").lower() != "amd":
        return ""
    return (gpu.device_id or "").lower().replace("0x", "")


def _is_rx580_2048sp(profile) -> bool:
    """2048SP узнаём по device-id, а без него — по имени (ручной профиль)."""
    gpu = getattr(profile, "dgpu", None)
    if gpu is None:
        return False
    dev = _dev(profile)
    if dev:
        return dev == "6fdf"
    name = (gpu.name or "").lower().replace(" ", "")
    return "2048sp" in name


def _is_broadcom(profile) -> bool:
    net = getattr(profile, "net", None)
    return bool(net and (net.wifi_chipset or "").lower() == "broadcom")


def _has_audio(profile) -> bool:
    audio = getattr(profile, "audio", None)
    codec = (getattr(audio, "codec", "") or "").lower() if audio else ""
    return bool(audio and getattr(audio, "layout_id", 0) and codec.startswith("alc"))


def merge_scan_paths(profile, scan):
    """Дополняет ручной профиль UEFI-путями из сканирования.

    Ручная форма не знает PCI-путей, поэтому device-id аудио и видеокарты
    прописать некуда. Пути и отсутствующий device-id берём у реального скана,
    если вендор/кодек совпадают.
    """
    if profile is None or scan is None:
        return profile
    for attr in ("dgpu", "igpu"):
        mine, real = getattr(profile, attr, None), getattr(scan, attr, None)
        if not mine or not real:
            continue
        if (mine.vendor or "").lower() != (real.vendor or "").lower():
            continue
        if not getattr(mine, "pci_path", "") and getattr(real, "pci_path", ""):
            mine.pci_path = real.pci_path
        if not getattr(mine, "device_id", "") and getattr(real, "device_id", ""):
            mine.device_id = real.device_id
    mine_a, real_a = getattr(profile, "audio", None), getattr(scan, "audio", None)
    if (mine_a and real_a and not getattr(mine_a, "pci_path", "")
            and (mine_a.codec or "").upper() == (real_a.codec or "").upper()):
        mine_a.pci_path = real_a.pci_path
    mine_n, real_n = getattr(profile, "net", None), getattr(scan, "net", None)
    if mine_n and real_n:
        for field in ("eth_pci_path", "wifi_pci_path"):
            if not getattr(mine_n, field, "") and getattr(real_n, field, ""):
                setattr(mine_n, field, getattr(real_n, field))
    return profile


def plan(profile, target_macos: str = "") -> list[Patch]:
    """Патчи, которые относятся к этому железу и целевой macOS."""
    major = _macos_major(target_macos)
    cpu = getattr(profile, "cpu", None)
    out: list[Patch] = []

    if cpu is not None and (getattr(cpu, "vendor", "") or "").lower() == "amd":
        out.append(P_AMD_KERNEL)
    if _is_rx580_2048sp(profile):
        out += [P_GPU_RX580_SPOOF, P_GPU_RX580_VBIOS]
    if _is_broadcom(profile) and major >= 14:
        out += [P_WIFI_BCM_EFI, P_WIFI_BCM_ROOT]
    if _has_audio(profile):
        out.append(P_AUDIO_ALCID)
    if is_navi_gpu(getattr(profile, "dgpu", None)):
        out.append(P_GPU_NAVI_AGDP)
    if any(p.scope == "system" for p in out):
        out.append(P_SECURITY_FOR_ROOT)
    return out


def auto_ids(plan_items: list[Patch]) -> set[str]:
    """Патчи, которые включаются без явного выбора пользователя."""
    return {p.id for p in plan_items if p.auto}


def report(profile, target_macos: str = "", enabled: set[str] | None = None,
           lang: str = "ru") -> str:
    """Текст отчёта: что применяется в EFI и что делать на macOS."""
    items = plan(profile, target_macos)
    on = auto_ids(items) if enabled is None else set(enabled)
    target = target_macos or "по умолчанию (актуальная macOS)"
    head = ("Патчи для target macOS: " if not lang.startswith("en")
            else "Patches for target macOS: ") + target
    efi = [p for p in items if p.scope == "efi"]
    sys_ = [p for p in items if p.scope == "system"]
    lines = [head, ""]
    lines.append("В EFI (применяются при сборке):" if not lang.startswith("en")
                 else "In EFI (applied during the build):")
    if not efi:
        lines.append("  — нет" if not lang.startswith("en") else "  — none")
    for p in efi:
        mark = "[x]" if p.id in on else "[ ]"
        lines.append(f"  {mark} {p.title(lang)}")
    if ("gpu_rx580_spoof" in on and not getattr(
            getattr(profile, "dgpu", None), "pci_path", "")):
        lines.append("      ! " + ("Путь карты неизвестен: device-id прописывается "
                                   "только в сборке по сканированию железа."
                                   if not lang.startswith("en") else
                                   "Card PCI path is unknown: device-id is injected "
                                   "only in builds based on a hardware scan."))
    if sys_:
        lines.append("")
        lines.append("На macOS (root-патчи, вручную после установки):"
                     if not lang.startswith("en")
                     else "On macOS (root patches, manually after install):")
        for p in sys_:
            mark = "[x]" if p.id in on else "[ ]"
            lines.append(f"  {mark} {p.title(lang)}")
            lines.append(f"      {p.detail(lang)}")
        lines.append("")
        lines.append(_steps(lang))
    return "\n".join(lines)


def _steps(lang: str) -> str:
    if lang.startswith("en"):
        return (
            "Steps on the Mac:\n"
            "  1. Boot the installed macOS with this EFI.\n"
            "  2. Reset NVRAM once in the OpenCore picker (Space → Reset NVRAM).\n"
            "  3. Run OpenCore Legacy Patcher → Post-Install Root Patch, reboot.\n"
            "  4. After every macOS update repeat step 3.")
    return (
        "Шаги на Mac:\n"
        "  1. Загрузить установленную macOS с этим EFI.\n"
        "  2. Один раз сбросить NVRAM в меню OpenCore (Space → Reset NVRAM).\n"
        "  3. Запустить OpenCore Legacy Patcher → Post-Install Root Patch, "
        "перезагрузиться.\n"
        "  4. После каждого обновления macOS повторять шаг 3.")
