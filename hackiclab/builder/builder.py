"""Оркестратор сборки EFI: связывает загрузку, генерацию конфига и раскладку.

Основной класс EFIBuilder — высокоуровневый конвейер сборки целевой папки EFI.
"""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..knowledge.kexts import select_kexts, smbios_model_for
from ..knowledge.ssdt_logics import required_ssdts
from ..scanner.models import HardwareProfile
from .config_gen import BuildOptions, generate_config_plist, _patch_on
from .efi_layout import EFIBuildResult, EFILayout
from .fetcher import GitHubFetcher, download_asset
from .smbios_gen import SMBIOSData, generate_smbios
from .ssdt_factory import SSDTFactory, compile_dsl, find_iasl, irq_conflict_devices


#: Сетевой стек для OpenNetworkBoot. Порядок важен: протоколы (SNP/MNP/IP/
#: UDP/TCP/DNS/HTTP/TLS) регистрируются раньше самого плагина загрузки.
_NETWORK_BOOT_DRIVERS = [
    "SnpDxe.efi", "MnpDxe.efi", "ArpDxe.efi", "Dhcp4Dxe.efi", "Ip4Dxe.efi",
    "Udp4Dxe.efi", "Mtftp4Dxe.efi", "Dhcp6Dxe.efi", "Ip6Dxe.efi", "Udp6Dxe.efi",
    "Mtftp6Dxe.efi", "TcpDxe.efi", "UefiPxeBcDxe.efi", "DnsDxe.efi",
    "HttpDxe.efi", "HttpUtilitiesDxe.efi", "HttpBootDxe.efi", "TlsDxe.efi",
    "OpenNetworkBoot.efi",
]


def want_drivers(options) -> list:
    """UEFI-драйверы, которые кладём в EFI/OC/Drivers.

    ResetNvram/ToggleSip — штатные точки меню OpenCore: сброс NVRAM и
    переключение SIP без правки config.plist вручную. OpenCanopy (графическое
    меню) подключается отдельно, потому что требует EFI/OC/Resources.
    """
    names = ["OpenRuntime.efi", "OpenHfsPlus.efi",
             "ResetNvramEntry.efi", "ToggleSipEntry.efi"]
    if getattr(options, "dual_boot", "") in ("linux", "both"):
        names.append("OpenLinuxBoot.efi")
    if getattr(options, "gui_picker", False):
        names.append("OpenCanopy.efi")
    if getattr(options, "audio_dxe", False):
        names.append("AudioDxe.efi")
    if getattr(options, "legacy_boot", False):
        names.append("OpenLegacyBoot.efi")
    if getattr(options, "network_boot", False):
        names.extend(_NETWORK_BOOT_DRIVERS)
    return names

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
            for e in select_kexts(self.profile, self.options.wifi_kext_mode,
                                  target_macos=self.options.target_macos):
                self.kext_names.append(e.name)


class EFIBuilder:
    """Выполняет сборку EFI по плану."""

    OPEN_CORE_REPO = "acidanthera/OpenCorePkg"

    def __init__(self, plan: BuildPlan, on_progress=None):
        self.plan = plan
        self.log: list[str] = []
        self.on_progress = on_progress
        self._last_percent = 0

    def _log(self, msg: str):
        self.log.append(msg)

    def _step(self, percent: int, msg: str):
        """Пишет шаг в журнал и сразу отдаёт его с процентом в интерфейс."""
        self._log(msg)
        # прогресс не должен идти назад: карточка с яблоком показывает проценты
        value = max(0, min(100, int(percent)))
        if value < self._last_percent:
            value = self._last_percent
        self._last_percent = value
        if self.on_progress is not None:
            try:
                self.on_progress(value, msg)
            except Exception:
                pass

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
        if not name:
            self._log("OpenCore: у zip-ассета нет имени")
            return None
        zip_path = download_asset(release, name, dest, cache_name="opencore")
        if not zip_path:
            return None
        extract = dest / "opencore_extracted"
        if extract.exists():
            shutil.rmtree(str(extract), ignore_errors=True)
        # извлечение zip
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
        self._step(2, f"Целевая папка: {target}")

        # --- Реальное скачивание компонентов ---
        from .downloader import Downloader
        dl = Downloader()
        tmp = target / ".downloads"
        tmp.mkdir(parents=True, exist_ok=True)

        # 1) OpenCore
        oc_zip = dl.download_open_core(tmp)
        extract: Path | None = None
        if oc_zip:
            self._step(16, "Распаковываю OpenCore…")
            try:
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
                    self._step(26, "  OpenCore.efi → EFI/OC, BOOTx64.efi → EFI/BOOT")
                    res.stats["opencore"] = "OK"
                else:
                    self._log("  OpenCore.efi/BOOTx64.efi не найдены в архиве")
                # обязательные UEFI-драйверы: OpenRuntime + OpenHfsPlus;
                # для Linux в мультизагрузке добавляем OpenLinuxBoot
                placed_drivers = []
                drivers_dir = (x64_efi / "OC" / "Drivers") if x64_efi else (extract / "Drivers")
                gui_picker = bool(getattr(self.plan.options, "gui_picker", False))
                wanted = want_drivers(self.plan.options)
                for drv in wanted:
                    src = drivers_dir / drv
                    if not src.exists():
                        src = next(extract.rglob(drv), None)
                    if src is not None and src.exists():
                        # битый/обрезанный драйвер (0–4 КБ) в EFI не кладём:
                        # OpenCore не загрузит такой драйвер и не скажет почему
                        if src.stat().st_size < 4096:
                            layout.warnings.append(
                                f"{drv}: файл подозрительно мал "
                                f"({src.stat().st_size} байт) — пропущен")
                            continue
                        layout.place_driver(src)
                        placed_drivers.append(drv)
                        self._log(f"  {drv} → Drivers")
                res.stats["drivers_placed"] = placed_drivers
                if gui_picker:
                    # OpenCanopy без Resources показывает пустое меню, а архив
                    # OpenCore приходит с пустыми папками — иконки и шрифты
                    # докачиваются из официального OcBinaryData.
                    from .canopy import ensure_resources, has_real_files
                    dst_res = layout.oc / "Resources"
                    res_src = (x64_efi / "OC" / "Resources") if x64_efi else None
                    if has_real_files(res_src):
                        shutil.rmtree(str(dst_res), ignore_errors=True)
                        shutil.copytree(str(res_src), str(dst_res))
                        self._log("  Resources → EFI/OC/Resources (из архива OpenCore)")
                    else:
                        written = ensure_resources(dst_res, log=self._log)
                        if written:
                            self._log("  Resources → EFI/OC/Resources (OcBinaryData)")
                        else:
                            layout.warnings.append(
                                "OpenCanopy: иконки не скачаны — меню будет без "
                                "графики, положите Resources в EFI/OC вручную")
                if not any(d.lower() in ("openhfsplus.efi", "hfsplus.efi")
                           for d in placed_drivers):
                    layout.warnings.append(
                        "HFS+ driver (OpenHfsPlus.efi) не найден в архиве OpenCore")
                # сохраняем ocvalidate в кэш, иначе после очистки .downloads
                # валидация не сможет найти утилиту
                ocv_exe = next((p for p in extract.rglob("ocvalidate.exe")
                                if p.is_file()), None)
                if ocv_exe:
                    from .cache_manager import cache_dir
                    tools = cache_dir() / "tools"
                    tools.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(ocv_exe), str(tools / "ocvalidate.exe"))
                    self._log("  ocvalidate → кэш инструментов")
            except Exception as e:
                self._log(f"OpenCore: распаковка не удалась: {e}")
        else:
            self._step(26, "OpenCore: не удалось скачать")

        # 2) Кексты по профилю
        from ..knowledge.kexts import select_kexts
        selected = select_kexts(self.plan.profile, self.plan.options.wifi_kext_mode,
                                self.plan.options.usb_toolbox,
                                self.plan.options.target_macos)
        kexts_dir = layout.oc / "Kexts"
        kexts_dir.mkdir(parents=True, exist_ok=True)
        downloaded = []
        missing = []
        total_kexts = max(1, len(selected))
        for index, e in enumerate(selected, 1):
            if e.internal:
                continue  # входят в состав родительского архива
            self._step(30 + int(34 * index / total_kexts), f"Скачиваю {e.name}…")
            seen = len(dl.log)
            try:
                path = dl.download_kext(e, kexts_dir, self.plan.options.target_macos)
            except Exception as ex:
                path = None
                self._log(f"  {e.name}: ошибка ({ex})")
            for line in dl.log[seen:]:
                self._log(f"  {line}")
            if path:
                downloaded.append(e.name)
            else:
                missing.append(e.name)
        res.stats["kexts_downloaded"] = downloaded
        if missing:
            # Молча потерянный кекст — это неполный EFI, о котором пользователь
            # узнает только при загрузке. Говорим сразу и в журнале, и в итоге.
            res.warnings.append("kexts_missing: " + ", ".join(missing))
            self._log("Kexts: не скачались — " + ", ".join(missing))
        res.stats["kexts_missing"] = missing

        # оставляем только выбранные кексты и нужные им внутренние модули
        from .downloader import canonical_kext_name
        allowed = {canonical_kext_name(e.bundle_name or e.name) for e in selected}
        allowed.add("SMCSuperIO.kext")
        if self.plan.profile.cpu.vendor == "intel":
            allowed.add("SMCProcessor.kext")
        if any(e.name == "RadeonSensor" for e in selected):
            allowed.add("SMCRadeonGPU.kext")
        for child in list(kexts_dir.iterdir()):
            if child.is_dir() and child.name.endswith(".kext") and child.name not in allowed:
                shutil.rmtree(str(child), ignore_errors=True)
            elif child.is_file():
                child.unlink(missing_ok=True)

        # USBToolBox без карты портов бесполезен: либо строим UTBMap, либо убираем
        if any(e.name == "USBToolBox" for e in selected):
            self._step(66, "Строю карту USB-портов…")
            map_kext = None
            try:
                from .usb_map import generate_auto_map, write_map_kext
                map_plist = generate_auto_map(tmp, log=self._log)
                if map_plist:
                    map_kext = write_map_kext(map_plist, kexts_dir)
            except Exception as ex:
                self._log(f"USB-карта: ошибка ({ex})")
            if map_kext:
                self._step(68, "USB: карта UTBMap.kext собрана")
            else:
                self._log("USB: карту построить не удалось — USBToolBox убран, "
                          "порты macOS определит сама")
                shutil.rmtree(str(kexts_dir / "USBToolBox.kext"), ignore_errors=True)

        # 3) SSDT генерация (via SSDTFactory + iasl)
        self._step(72, "Готовлю SSDT…")
        dsdt_text = ""
        try:
            from .usb_map import decompile_dsdt, dump_dsdt
            dsdt_dir = tmp / "dsdt"
            dsdt_dir.mkdir(parents=True, exist_ok=True)
            dsdt_aml = dump_dsdt(dsdt_dir)
            if dsdt_aml:
                dsdt_text = decompile_dsdt(dsdt_aml, dsdt_dir, log=self._log) or ""
                if dsdt_text:
                    self._log("DSDT: прочитан для таблиц по железу")
                else:
                    self._log("DSDT: декомпилировать не удалось — SSDT по DSDT пропущены")
            else:
                self._log("DSDT: дамп недоступен — SSDT по DSDT пропущены")
        except Exception as exc:
            self._log(f"DSDT: ошибка ({exc})")
        if dsdt_text:
            conflicts = irq_conflict_devices(dsdt_text)
            if conflicts:
                self._log("SSDT-HPET: занятые IRQ у " + ", ".join(conflicts)
                          + " — без их снятия macOS не стартует")
        try:
            ssdt_out = target / ".ssdt"
            ssdt_out.mkdir(parents=True, exist_ok=True)
            factory = SSDTFactory(self.plan.profile, dsdt_text=dsdt_text)
            ssdt_results = factory.generate_all(ssdt_out)
            # SSDT-HPET строится по DSDT: снимаем IRQNoFlags у HPET/RTC/TIMR
            if dsdt_text and irq_conflict_devices(dsdt_text):
                from .ssdt_factory import build_hpet_fix
                dsl, irq_patches = build_hpet_fix(dsdt_text)
                aml = compile_dsl(dsl, ssdt_out, "SSDT-HPET") if dsl else None
                if aml:
                    ssdt_results.append({"name": "SSDT-HPET", "path": str(aml),
                                         "status": "compiled"})
                    if self.plan.options is not None:
                        self.plan.options.extra_acpi_patches = list(irq_patches)
                    self._log("SSDT-HPET: собран по DSDT, IRQ сняты у "
                              + ", ".join(p["Comment"].split("(")[-1].rstrip(")")
                                          for p in irq_patches))
                else:
                    self._log("SSDT-HPET: собрать не удалось — нужен готовый .aml "
                              "из SSDTTime")
            # попытка подтянуть iasl и перекомпилировать, если не собралось
            if not find_iasl(ensure=True):
                self._log("SSDT: iasl не найден/не скачан — .dsl остаются шаблонами")
            else:
                for r in ssdt_results:
                    if r["status"] == "template-only":
                        from .ssdt_factory import generate_ssdt
                        aml = generate_ssdt(r["name"], self.plan.profile, ssdt_out,
                                            dsdt_text=dsdt_text)
                        if aml:
                            r["status"] = "compiled"
                            r["path"] = str(aml)
            # раскладываем .aml в EFI/OC/ACPI
            acpi_dir = layout.oc / "ACPI"
            acpi_dir.mkdir(parents=True, exist_ok=True)
            placed = []
            missing = []
            for r in ssdt_results:
                if r["path"] and Path(r["path"]).exists():
                    shutil.copy2(str(r["path"]), str(acpi_dir / Path(r["path"]).name))
                    placed.append(r["name"])
                else:
                    missing.append(r["name"])
            self._step(80, f"SSDT в ACPI: {placed if placed else 'нет готовых .aml'}")
            if missing:
                self._log("SSDT: не собрались — " + ", ".join(missing))
                if "SSDT-USB-Reset" in missing:
                    self._log("SSDT: USB-Reset строится по DSDT и нужен только "
                              "при наличии RHUB — его отсутствие нормально")
                others = [n for n in missing if n != "SSDT-USB-Reset"]
                if others:
                    self._log("SSDT: этим таблицам нужен готовый .aml "
                              "(соберите в SSDTTime и положите в assets/acpi)")
            res.stats["ssdt_placed"] = placed
            res.stats["ssdt_missing"] = missing
        except Exception as e:
            self._log(f"SSDT: ошибка генерации ({e})")
            res.stats["ssdt_placed"] = []

        # 4) config.plist с SMBIOS
        opts = self.plan.options or BuildOptions()
        opts = BuildOptions(**{**opts.__dict__, "custom_smbios": self.plan.smbios})
        self._step(86, "Формирую config.plist…")
        data = generate_config_plist(self.plan.profile, opts)
        # впишем реально скачанные kext в Kernel/Add (пути BundlePath относительно OC/)
        kexts_placed = [x.name for x in kexts_dir.iterdir() if x.is_dir() and x.name.endswith('.kext')]
        amd_patches = None
        if (self.plan.profile.cpu.vendor == "amd"
                and _patch_on(opts, "cpu_amd")):
            from .amd_patches import fetch_amd_patches
            amd_patches = fetch_amd_patches(log=self._log)
            self._log(f"AMD kernel patches: {len(amd_patches) if amd_patches else 0}")
            if not amd_patches:
                res.errors.append(
                    "AMD kernel patches недоступны: EFI не загрузится на Ryzen")
                res.ok = False
        # config.plist пишется всегда: иначе на Intel остаются пустые Kernel/Add
        # и ACPI/Add — EFI без кекстов и таблиц.
        layout.write_plist_with_kexts(data, kexts_placed,
                                      driver_names=res.stats.get("drivers_placed", []),
                                      kernel_patches=amd_patches,
                                      acpi_names=res.stats.get("ssdt_placed", []),
                                      gui_picker=gui_picker)

        # Запись в локальную базу отчётов: и удачные, и неудачные сборки.
        # Из неё же строится страница новой задачи GitHub для общей базы.
        try:
            from ..knowledge import community
            cfg_bytes = (layout.oc / "config.plist").read_bytes()
            record = community.record_from_result(self.plan.profile, opts, res,
                                                  kexts=kexts_placed, config=cfg_bytes)
            res.stats["community_record"] = str(record)
            self._log(f"Отчёт о сборке сохранён: {record.name}")
        except Exception as exc:
            self._log(f"Отчёт о сборке не сохранён ({exc})")

        # 4.5) HeliPort для режима itlwm: без него в macOS нет меню Wi-Fi
        if (self.plan.options.wifi_kext_mode == "itlwm"
                and (self.plan.profile.net.wifi_chipset or "").lower() == "intel"):
            self._step(88, "Скачиваю HeliPort для itlwm…")
            extras = target / "EFI" / "HackicLab-Extras"
            heliport = dl.download_heliport(extras)
            if heliport:
                res.stats["heliport"] = heliport.name
                self._log(f"  HeliPort → {heliport}")
            else:
                self._log("  HeliPort: не скачан — интернет через itlwm будет, "
                          "но меню Wi-Fi в macOS не появится")

        # 5) ocvalidate финального config.plist
        cfg_path = layout.oc / "config.plist"
        from ..builder.ocvalidate import find_ocvalidate, run_ocvalidate
        ocv_tool = (find_ocvalidate(in_open_core_root=extract) if extract
                    else find_ocvalidate())
        self._step(93, "Проверяю config.plist через ocvalidate…")
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

        # пустая папка Tools только путает: OpenCore её не требует
        tools_dir = layout.oc / "Tools"
        try:
            if tools_dir.is_dir() and not any(tools_dir.iterdir()):
                tools_dir.rmdir()
        except OSError:
            pass

        # чистим временные папки, чтобы не мусорить в выбранной директории
        shutil.rmtree(str(tmp), ignore_errors=True)
        shutil.rmtree(str(target / ".ssdt"), ignore_errors=True)

        res.stats = {
            "kexts": self.plan.kext_names,
            "kexts_downloaded": downloaded,
            "kexts_missing": res.stats.get("kexts_missing", []),
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
        self._step(100, "Сборка завершена")
        return res




