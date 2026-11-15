"""Оркестратор сборки EFI: связывает загрузку, генерацию конфига и раскладку.

Основной класс EFIBuilder — высокоуровневый конвейер сборки целевой папки EFI.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..scanner.models import HardwareProfile
from ..knowledge.kexts import select_kexts, smbios_model_for
from ..knowledge.ssdt_logics import required_ssdts
from .config_gen import generate_config_plist, BuildOptions
from .smbios_gen import SMBIOSData, generate_smbios
from .ssdt_factory import SSDTFactory, find_iasl
from .efi_layout import EFILayout, EFIBuildResult
from .fetcher import GitHubFetcher, download_asset


@dataclass
class BuildPlan:
    profile: HardwareProfile
    options: BuildOptions = None              # type: ignore[assignment]
    smbios: Optional[SMBIOSData] = None
    kext_names: list = field(default_factory=list)
    ssdt_names: list = field(default_factory=list)
    target_dir: Path = None                   # type: ignore[assignment]

    def __post_init__(self):
        if self.options is None:
            self.options = BuildOptions()
        if self.smbios is None:
            model = smbios_model_for(self.profile, self.options.target_macos)
            self.smbios = generate_smbios(model)
        if not self.kext_names:
            for e in select_kexts(self.profile, self.options.wifi_kext_mode):
                self.kext_names.append(e.name)


class EFIBuilder:
    """Выполняет сборку EFI по плану."""

    OPEN_CORE_REPO = "acidanthera/OpenCorePkg"

    def __init__(self, plan: BuildPlan):
        self.plan = plan
        self.log: list[str] = []

    def _log(self, msg: str):
        self.log.append(msg)

    def fetch_open_core(self, dest: Path) -> Optional[Path]:
        """Скачивает и распаковывает релиз OpenCorePkg. Возвращает путь к OpenCore.efi."""
        release = GitHubFetcher.latest_release(self.OPEN_CORE_REPO)
        if not release:
            self._log("OpenCore: не удалось получить релиз")
            return None
        zip_asset = GitHubFetcher.find_asset(release, ".zip")
        if not zip_asset:
            self._log("OpenCore: не найден zip")
            return None
        name = zip_asset.get("name")
        zip_path = download_asset(release, name, dest, cache_name="opencore")
        if not zip_path:
            return None
        extract = dest / "opencore_extracted"
        if extract.exists():
            shutil.rmtree(str(extract), ignore_errors=True)
        # извлечение zip
        import zipfile
        try:
            with zipfile.ZipFile(str(zip_path)) as z:
                z.extractall(str(extract))
        except Exception as e:
            self._log(f"OpenCore: распаковка не удалась: {e}")
            return None
        return extract

    def build(self, target_dir: Optional[Path] = None) -> EFIBuildResult:
        """Главный метод сборки: структура + реальное скачивание OpenCore/kext."""
        target = target_dir or self.plan.target_dir
        if target is None:
            return EFIBuildResult(root=Path(), ok=False, errors=["нет целевой папки"])
        target = Path(target)
        target.mkdir(parents=True, exist_ok=True)

        layout = EFILayout(target)
        layout.create()
        res = EFIBuildResult(root=target, ok=True)
        self._log(f"Целевая папка: {target}")

        # --- Реальное скачивание компонентов ---
        from .downloader import Downloader
        dl = Downloader()
        tmp = target / ".downloads"
        tmp.mkdir(parents=True, exist_ok=True)

        # 1) OpenCore
        oc_zip = dl.download_open_core(tmp)
        if oc_zip:
            self._log("Распаковываю OpenCore…")
            try:
                import zipfile, shutil
                extract = tmp / "oc_extracted"
                if extract.exists():
                    shutil.rmtree(str(extract), ignore_errors=True)
                with zipfile.ZipFile(str(oc_zip)) as z:
                    z.extractall(str(extract))
                # 64-битная ветка релиза: X64/EFI (IA32 не подходит)
                x64_efi = None
                for cand in extract.rglob("EFI"):
                    if (cand.is_dir() and "IA32" not in str(cand).upper()
                            and (cand / "OC" / "OpenCore.efi").exists()
                            and (cand / "BOOT" / "BOOTx64.efi").exists()):
                        x64_efi = cand
                        break
                if x64_efi:
                    layout.place_opencore(x64_efi / "OC" / "OpenCore.efi")
                    layout.place_bootx64(x64_efi / "BOOT" / "BOOTx64.efi")
                    self._log("  OpenCore.efi → EFI/OC, BOOTx64.efi → EFI/BOOT")
                    res.stats["opencore"] = "OK"
                else:
                    self._log("  OpenCore.efi/BOOTx64.efi не найдены в архиве")
                # обязательные UEFI-драйверы: OpenRuntime + OpenHfsPlus
                placed_drivers = []
                drivers_dir = (x64_efi / "OC" / "Drivers") if x64_efi else (extract / "Drivers")
                for drv in ("OpenRuntime.efi", "OpenHfsPlus.efi"):
                    src = drivers_dir / drv
                    if not src.exists():
                        src = next(extract.rglob(drv), None)
                    if src is not None and src.exists():
                        layout.place_driver(src)
                        placed_drivers.append(drv)
                        self._log(f"  {drv} → Drivers")
                res.stats["drivers_placed"] = placed_drivers
                if not any(d.lower() in ("openhfsplus.efi", "hfsplus.efi")
                           for d in placed_drivers):
                    layout.warnings.append(
                        "HFS+ driver (OpenHfsPlus.efi) не найден в архиве OpenCore")
            except Exception as e:
                self._log(f"OpenCore: распаковка не удалась: {e}")
        else:
            self._log("OpenCore: не удалось скачать")

        # 2) Кексты по профилю
        from ..knowledge.kexts import select_kexts
        selected = select_kexts(self.plan.profile, self.plan.options.wifi_kext_mode)
        kexts_dir = layout.oc / "Kexts"
        kexts_dir.mkdir(parents=True, exist_ok=True)
        downloaded = []
        for e in selected:
            if e.internal:
                continue  # входят в состав родительского архива
            self._log(f"Скачиваю {e.name}…")
            try:
                dl.download_kext(e, kexts_dir)
                downloaded.append(e.name)
            except Exception as ex:
                self._log(f"  {e.name}: ошибка ({ex})")
        res.stats["kexts_downloaded"] = downloaded

        # оставляем только выбранные кексты и нужные им внутренние модули
        allowed = {(e.bundle_name or e.name) for e in selected}
        allowed.add("SMCSuperIO")
        if self.plan.profile.cpu.vendor == "intel":
            allowed.add("SMCProcessor")
        if any(e.name == "RadeonSensor" for e in selected):
            allowed.add("SMCRadeonGPU")
        for child in list(kexts_dir.iterdir()):
            if child.is_dir() and child.name.endswith(".kext") and child.name[:-5] not in allowed:
                shutil.rmtree(str(child), ignore_errors=True)
            elif child.is_file():
                child.unlink(missing_ok=True)

        # 3) SSDT генерация (via SSDTFactory + iasl)
        try:
            ssdt_out = target / ".ssdt"
            ssdt_out.mkdir(parents=True, exist_ok=True)
            factory = SSDTFactory(self.plan.profile)
            ssdt_results = factory.generate_all(ssdt_out)
            # попытка подтянуть iasl и перекомпилировать, если не собралось
            if not find_iasl(ensure=True):
                self._log("SSDT: iasl не найден/не скачан — .dsl остаются шаблонами")
            else:
                for r in ssdt_results:
                    if r["status"] == "template-only":
                        from .ssdt_factory import generate_ssdt
                        aml = generate_ssdt(r["name"], self.plan.profile, ssdt_out)
                        if aml:
                            r["status"] = "compiled"
                            r["path"] = str(aml)
            # раскладываем .aml в EFI/OC/ACPI
            acpi_dir = layout.oc / "ACPI"
            acpi_dir.mkdir(parents=True, exist_ok=True)
            placed = []
            for r in ssdt_results:
                if r["path"] and Path(r["path"]).exists():
                    shutil.copy2(r["path"], str(acpi_dir / Path(r["path"]).name))
                    placed.append(r["name"])
            self._log(f"SSDT в ACPI: {placed if placed else 'нет готовых .aml'}")
            res.stats["ssdt_placed"] = placed
        except Exception as e:
            self._log(f"SSDT: ошибка генерации ({e})")
            res.stats["ssdt_placed"] = []

        # 4) config.plist с SMBIOS
        opts = self.plan.options
        opts = BuildOptions(**{**opts.__dict__, "custom_smbios": self.plan.smbios})
        data = generate_config_plist(self.plan.profile, opts)
        # впишем реально скачанные kext в Kernel/Add (пути BundlePath относительно OC/)
        kexts_placed = [x.name for x in kexts_dir.iterdir() if x.is_dir() and x.name.endswith('.kext')]
        amd_patches = None
        if self.plan.profile.cpu.vendor == "amd":
            from .amd_patches import fetch_amd_patches
            amd_patches = fetch_amd_patches(log=self._log)
            self._log(f"AMD kernel patches: {len(amd_patches) if amd_patches else 0}")
            if not amd_patches:
                res.errors.append(
                    "AMD kernel patches недоступны: EFI не загрузится на Ryzen")
                res.ok = False
        layout.write_plist_with_kexts(data, kexts_placed,
                                      driver_names=res.stats.get("drivers_placed", []),
                                      kernel_patches=amd_patches)

        # 5) ocvalidate финального config.plist
        cfg_path = layout.oc / "config.plist"
        from ..builder.ocvalidate import find_ocvalidate, run_ocvalidate
        ocv_tool = find_ocvalidate(in_open_core_root=extract) if oc_zip and 'extract' in dir() else find_ocvalidate()
        ocv = run_ocvalidate(cfg_path, ocvalidate=ocv_tool)
        res.stats["ocvalidate_ok"] = ocv.ok
        res.stats["ocvalidate_errors"] = ocv.errors
        res.stats["ocvalidate_warnings"] = ocv.warnings
        self._log(f"ocvalidate: {'OK' if ocv.ok else 'НАЙДЕНЫ ПРОБЛЕМЫ'} ({len(ocv.warnings)} warn, {len(ocv.errors)} err)")
        for e in ocv.errors[:20]:
            self._log(f"  [err] {e}")
        for w in ocv.warnings[:20]:
            self._log(f"  [warn] {w}")
        if not ocv.ok and ocv.errors:
            res.ok = False

        if layout.errors:
            res.errors.extend(layout.errors)
            res.ok = False
        res.warnings = list(layout.warnings) + list(dl.log)

        # чистим временные папки, чтобы не мусорить в выбранной директории
        shutil.rmtree(str(tmp), ignore_errors=True)
        shutil.rmtree(str(target / ".ssdt"), ignore_errors=True)

        res.stats = {
            "kexts": self.plan.kext_names,
            "kexts_downloaded": downloaded,
            "kexts_placed": kexts_placed,
            "ssdts": self.plan.ssdt_names or [s.name for s in required_ssdts(self.plan.profile)],
            "ssdt_placed": res.stats.get("ssdt_placed", []),
            "smbios": self.plan.smbios.model if self.plan.smbios else "",
            "opencore": res.stats.get("opencore", "skip"),
            "drivers_placed": res.stats.get("drivers_placed", []),
            "ocvalidate_ok": ocv.ok,
            "ocvalidate_errors": ocv.errors,
            "ocvalidate_warnings": ocv.warnings,
            "dir": str(target),
        }
        res.warnings = list(layout.warnings) + list(dl.log)
        try:
            from .history import record_build
            record_build(self.plan, res)
        except Exception:
            pass
        return res