"""Ядро анализа и рекомендаций.

Сопоставляет профиль железа с папкой EFI/kexts клиента и выдаёт
структурированный список проблем (AnalysisIssue): отсутствующие кексты,
несовместимости, устаревшие компоненты, предложения.
"""

from __future__ import annotations

from pathlib import Path

from ..knowledge.kexts import (
    KEXT_DB,
    select_kexts,
)
from ..scanner.models import HardwareProfile
from .efi_health import audit as audit_efi_root
from .models import KEXT_CONFLICTS, AnalysisIssue, Severity


class Analyzer:
    """Проверяет папку с файлами клиента против профиля железа."""

    def __init__(self, profile: HardwareProfile):
        self.profile = profile
        self.issues: list[AnalysisIssue] = []

    # --- сравнение с папкой EFI / kexts ---
    def analyze_folder(self, folder: Path) -> list[AnalysisIssue]:
        self.issues = []
        self._check_required_kexts_present(folder)
        self._check_open_core_present(folder)
        self._check_amd_patches(folder)
        present = self._discover_kexts(folder)
        self._check_kext_conflicts(present)
        self._check_hardware_warnings(present)
        return self.issues

    def _check_kext_conflicts(self, present: set[str]):
        """Пары кекстов, которые не уживаются в одном EFI.

        Ловит в том числе чужие сборки: имена берём из Kernel/Add и файлов
        на диске, поэтому конфликт виден ещё до загрузки.
        """
        for first, second, note in KEXT_CONFLICTS:
            if first in present and second in present:
                self.issues.append(AnalysisIssue(
                    Severity.ERROR,
                    f"kext_conflict_{first.lower()}_{second.lower()}",
                    f"Конфликт кекстов: {first} и {second}",
                    note,
                    kext=second,
                    suggestion=f"Уберите {second}.kext из EFI/OC/Kexts и запись "
                               f"из Kernel/Add — иначе один из двух не загрузится."))


    @staticmethod
    def _oc_dir(folder: Path) -> Path:
        """Папка OC: принимаем и корень с EFI/, и саму папку EFI."""
        cand = folder / "EFI" / "OC"
        return cand if cand.exists() else folder / "OC"

    @staticmethod
    def _boot_dir(folder: Path) -> Path:
        cand = folder / "EFI" / "BOOT"
        return cand if cand.exists() else folder / "BOOT"

    def _discover_kexts(self, folder: Path) -> set[str]:
        """Ищет *.kext в папке (рекурсивно) и имена из config.plist."""
        names: set[str] = set()
        for p in folder.rglob("*.kext"):
            names.add(p.name)
            names.add(p.stem)
        # также ищем имена кекстов в config.plist
        cfg = self._oc_dir(folder) / "config.plist"
        if cfg.exists():
            try:
                import plistlib
                data = plistlib.loads(cfg.read_bytes())
                for add in data.get("Kernel", {}).get("Add", []):
                    n = add.get("BundlePath", "")
                    if n:
                        names.add(Path(n).stem)
                        names.add(Path(n).name)
            except Exception:
                pass
        return names

    def _check_required_kexts_present(self, folder: Path):
        if not folder.exists():
            self.issues.append(AnalysisIssue(
                Severity.ERROR, "folder_missing",
                "Папка не найдена", str(folder)))
            return
        # Собранный нами EFI содержит USB-карту и кексты под все режимы Wi-Fi,
        # поэтому сверяемся с объединением вариантов: иначе собственные файлы
        # выглядят как «необязательные кексты».
        required = list(select_kexts(self.profile, usb_toolbox=True))
        known_names = {e.name for e in required}
        for mode in ("itlwm", "airportitlwm", "native"):
            for e in select_kexts(self.profile, mode, usb_toolbox=True):
                if e.name not in known_names:
                    known_names.add(e.name)
                    required.append(e)
        present = self._discover_kexts(folder)
        for e in required:
            nm = e.bundle_name or e.name
            if nm not in present and e.name not in present:
                self.issues.append(AnalysisIssue(
                    Severity.WARNING, "kext_missing",
                    f"Отсутствует kext: {e.name}",
                    e.note, kext=e.name,
                    suggestion=f"Добавьте {e.name}.kext ({e.repo})"))

        # Лишние/неожиданные кексты (информация). Внутренние кексты пакетов
        # (SMCSuperIO, UTBMap и прочие из чужих архивов) не «лишние»: они
        # приезжают вместе с родительским кекстом.
        known = {e.bundle_name or e.name for e in required}
        for nm in present:
            entry = KEXT_DB.get(nm)
            if entry is not None and entry.internal:
                continue
            known_bundle = {e.bundle_name or e.name for e in KEXT_DB.values()}
            if nm in known_bundle and nm not in known:
                self.issues.append(AnalysisIssue(
                    Severity.INFO, "kext_extra",
                    f"Необязательный kext: {nm}",
                    "Есть в папке, но не требуется вашим железом", kext=nm))

    def _check_open_core_present(self, folder: Path):
        oc = self._oc_dir(folder) / "OpenCore.efi"
        boot = self._boot_dir(folder) / "BOOTx64.efi"
        if not oc.exists() or not boot.exists():
            self.issues.append(AnalysisIssue(
                Severity.WARNING, "oc_missing",
                "OpenCore не найден",
                "В папке EFI нет OpenCore.efi и/или BOOTx64.efi",
                suggestion="Скачайте/укажите OpenCorePkg или разрешите автозагрузку"))

    def _check_amd_patches(self, folder: Path):
        """На Ryzen без патчей ядра macOS не стартует — проверяем config.plist."""
        if self.profile.cpu.vendor != "amd":
            return
        cfg = self._oc_dir(folder) / "config.plist"
        if not cfg.exists():
            return
        try:
            import plistlib
            data = plistlib.loads(cfg.read_bytes())
        except Exception:
            return
        patches = [p for p in (data.get("Kernel", {}).get("Patch", []) or [])
                   if isinstance(p, dict) and p.get("Enabled", True)]
        if patches:
            return
        self.issues.append(AnalysisIssue(
            Severity.ERROR, "amd_patches_missing",
            "Нет патчей ядра AMD Vanilla",
            "В config.plist отсутствуют записи Kernel/Patch, а на Ryzen без них "
            "macOS не загрузится.",
            suggestion="Соберите EFI в HackicLab или добавьте патчи AMD Vanilla."))

    def _check_gpu(self):
        """Карты, которые macOS не заводит даже с подменой device-id."""
        g = self.profile.dgpu
        if not g or (g.vendor or "").lower() != "amd":
            return
        did = (g.device_id or "").lower().replace("0x", "")
        if did != "6fdf":
            return
        self.issues.append(AnalysisIssue(
            Severity.ERROR, "gpu_rx580_2048sp",
            "RX 580 2048SP не поддерживается macOS",
            "Dortania относит карты с device-id 6FDF к неподдерживаемым: "
            "подмена device-id на 67DF обычно не даёт аппаратного ускорения. "
            "Рабочий путь — прошивка VBIOS от RX 570.",
            suggestion="Прошейте VBIOS от RX 570 или возьмите карту из GPU Buyers Guide."))

    def _check_network_notes(self, present: set[str] | None = None):
        net = self.profile.net
        eth = (net.eth_name or "").lower()
        if "i211" in eth and not (present and "AppleIGB" in present):
            self.issues.append(AnalysisIssue(
                Severity.INFO, "eth_i211_appleigb",
                "Intel I211 требует AppleIGB",
                "IntelMausi не покрывает I211; на Monterey и новее нужен AppleIGB "
                "(I210/I211/I350).",
                kext="AppleIGB",
                suggestion="Добавьте AppleIGB.kext вместо IntelMausi."))
        if (net.wifi_chipset or "").lower() == "broadcom":
            self.issues.append(AnalysisIssue(
                Severity.INFO, "wifi_broadcom_oclp",
                "Broadcom Wi-Fi на Sonoma и новее",
                "BCM4360/BCM43602 потеряли поддержку в macOS 14; вернуть их можно "
                "только root patch-ем OpenCore Legacy Patcher.",
                suggestion="На Sonoma+ примените root patch OCLP (Modern Wireless)."))
        if (net.wifi_chipset or "").lower() == "mediatek" and net.has_bt:
            self.issues.append(AnalysisIssue(
                Severity.INFO, "bt_mediatek_unsupported",
                "Bluetooth MediaTek тоже не работает",
                "Драйвера под macOS нет ни для Wi-Fi, ни для Bluetooth этого модуля.",
                suggestion="Используйте USB-Bluetooth-донгл с поддержкой macOS."))

    def _check_hardware_warnings(self, present: set[str] | None = None):
        """Добавляет architectural предупреждения, не зависящие от папки."""
        p = self.profile
        self._check_gpu()
        self._check_network_notes(present)
        if p.cpu.vendor == "amd" and p.platform == "laptop":
            self.issues.append(AnalysisIssue(
                Severity.ERROR, "amd_laptop",
                "AMD ноутбучный CPU не поддерживается",
                "AMD Vanilla патчи не работают на мобильных APU"))
        if p.cpu.vendor == "intel" and p.cpu.generation >= 11 and self._has_intel_only_gpu():
            self.issues.append(AnalysisIssue(
                Severity.WARNING, "igpu_unsupported",
                "Перетекает: нет macOS-драйвера для этой iGPU",
                "Нужна поддерживаемая AMD dGPU"))
        if p.net.wifi_chipset == "intel" and p.net.wifi_chipset:
            self.issues.append(AnalysisIssue(
                Severity.INFO, "wifi_intel",
                "Intel WiFi",
                "Работает через itlwm+HeliPort или AirportItlwm"))
        if p.net.wifi_chipset == "realtek":
            self.issues.append(AnalysisIssue(
                Severity.ERROR, "wifi_realtek_unsupported",
                "Realtek WiFi не поддерживается",
                "Нет драйвера под macOS; замените адаптер"))
        if p.net.wifi_chipset == "mediatek":
            self.issues.append(AnalysisIssue(
                Severity.ERROR, "wifi_mediatek_unsupported",
                "MediaTek WiFi не поддерживается",
                "Под macOS нет драйвера; используйте Ethernet или замените адаптер"))

    def _has_intel_only_gpu(self) -> bool:
        if self.profile.igpu and self.profile.igpu.vendor == "intel":
            return not (self.profile.dgpu and self.profile.dgpu.vendor == "amd")
        return False

    # --- проверка только профиля (без папки) ---
    def analyze_profile(self) -> list[AnalysisIssue]:
        self.issues = []
        self._check_hardware_warnings()
        return self.issues

    # --- структурный аудит готового EFI ---
    def audit_efi(self, folder: Path) -> list[AnalysisIssue]:
        """Аудит EFI независимо от профиля железа (файлы, kexts, ACPI)."""
        extra = audit_efi_root(folder)
        self.issues.extend(extra)
        return extra


def analyze_folders(profile: HardwareProfile, folder: Path) -> list[AnalysisIssue]:
    return Analyzer(profile).analyze_folder(folder)


def analyze_profile(profile: HardwareProfile) -> list[AnalysisIssue]:
    return Analyzer(profile).analyze_profile()


def audit_efi(folder: Path) -> list[AnalysisIssue]:
    """Аудит EFI/OC без привязки к железу."""
    return audit_efi_root(folder)

