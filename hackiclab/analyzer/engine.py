"""Ядро анализа и рекомендаций.

Сопоставляет профиль железа с папкой EFI/kexts клиента и выдаёт
структурированный список проблем (AnalysisIssue): отсутствующие кексты,
несовместимости, устаревшие компоненты, предложения.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..scanner.models import HardwareProfile
from ..knowledge.kexts import (
    KEXT_DB, KextEntry, select_kexts, smbios_model_for,
)
from ..knowledge.oc_platforms import MAX_MACOS_BY_GEN
from .models import AnalysisIssue, Severity
from .efi_health import audit as audit_efi_root


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
        self._check_hardware_warnings()
        return self.issues

    def _discover_kexts(self, folder: Path) -> set[str]:
        """Ищет *.kext в папке (рекурсивно) и имена из config.plist."""
        names: set[str] = set()
        for p in folder.rglob("*.kext"):
            names.add(p.name)
            names.add(p.stem)
        # также ищем имена кекстов в config.plist
        cfg = folder / "EFI" / "OC" / "config.plist"
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
        required = select_kexts(self.profile)
        present = self._discover_kexts(folder)
        for e in required:
            nm = e.bundle_name or e.name
            if nm not in present and e.name not in present:
                self.issues.append(AnalysisIssue(
                    Severity.WARNING, "kext_missing",
                    f"Отсутствует kext: {e.name}",
                    e.note, kext=e.name,
                    suggestion=f"Добавьте {e.name}.kext ({e.repo})"))

        # Лишние/неожиданные кексты (информация)
        known = {e.bundle_name or e.name for e in required}
        for nm in present:
            known_bundle = {e.bundle_name or e.name for e in KEXT_DB.values()}
            if nm in known_bundle and nm not in known:
                self.issues.append(AnalysisIssue(
                    Severity.INFO, "kext_extra",
                    f"Необязательный kext: {nm}",
                    "Есть в папке, но не требуется вашим железом", kext=nm))

    def _check_open_core_present(self, folder: Path):
        oc = folder / "EFI" / "OC" / "OpenCore.efi"
        boot = folder / "EFI" / "BOOT" / "BOOTx64.efi"
        if not oc.exists() or not boot.exists():
            self.issues.append(AnalysisIssue(
                Severity.WARNING, "oc_missing",
                "OpenCore не найден",
                "В папке EFI нет OpenCore.efi и/или BOOTx64.efi",
                suggestion="Скачайте/укажите OpenCorePkg или разрешите автозагрузку"))

    def _check_hardware_warnings(self):
        """Добавляет architectural предупреждения, не зависящие от папки."""
        p = self.profile
        name = p.cpu.name.lower()
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