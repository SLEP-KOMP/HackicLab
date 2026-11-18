"""Структура папки EFI: создание каталогов, раскладка файлов, config.plist."""

from __future__ import annotations

import plistlib
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EFIBuildResult:
    root: Path            # папка, куда записана EFI
    ok: bool
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)  # {categ: [names]}


# Порядок в Kernel > Add: Lilu и VirtualSMC обязаны идти раньше плагинов,
# иначе ocvalidate ругается «Parent … is placed after».
_KEXT_ORDER = {"Lilu": 0, "VirtualSMC": 1}
_ACPI_ORDER = {"SSDT-PLUG": 0, "SSDT-PLUG-AMD": 0, "SSDT-EC": 1,
               "SSDT-EC-USBX": 1, "SSDT-USBX": 2}

# OpenCanopy работает только с PickerMode=External, а у нас встроенный пикер.
_DRIVERS_SKIP = frozenset({"OpenCanopy.efi"})


def _plain_name(name: str, suffix: str) -> str:
    """Имя без расширения: нужен для сортировки по таблицам приоритетов."""
    return name[: -len(suffix)] if name.endswith(suffix) else name


class EFILayout:
    """Создаёт типовую структуру EFI/OC и раскладывает компоненты."""

    OC_FOLDERS = ("ACPI", "Drivers", "Kexts", "Tools")

    def __init__(self, root: Path):
        self.root = root
        self.oc = root / "EFI" / "OC"
        self.warnings: list[str] = []
        self.errors: list[str] = []

    # ---- каталоги и файлы ----
    def _ensure(self, *parts: str) -> Path:
        folder = self.oc.joinpath(*parts)
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _copy_into(self, folder: Path, src: Path, label: str) -> None:
        try:
            shutil.copy2(str(src), str(folder / src.name))
        except OSError as exc:
            self.errors.append(f"{label}: {exc}")

    def create(self) -> None:
        self.oc.mkdir(parents=True, exist_ok=True)
        for folder in self.OC_FOLDERS:
            (self.oc / folder).mkdir(parents=True, exist_ok=True)

    def place_opencore(self, source_efi: Path) -> None:
        """OpenCore.efi грузится из EFI/OC — его запускает BOOTx64.efi."""
        self._copy_into(self._ensure(), source_efi, "OpenCore.efi")

    def place_bootx64(self, source_efi: Path) -> None:
        """BOOTx64.efi из архива OpenCore кладём в EFI/BOOT."""
        if source_efi.name.lower() == "opencore.efi":
            self.errors.append("BOOTx64: передан OpenCore.efi вместо BOOTx64.efi")
            return
        boot = self.root / "EFI" / "BOOT"
        boot.mkdir(parents=True, exist_ok=True)
        self._copy_into(boot, source_efi, "BOOTx64")

    def place_driver(self, src: Path) -> None:
        self._copy_into(self._ensure("Drivers"), src, "Driver")

    def place_kext(self, src: Path) -> None:
        kexts = self._ensure("Kexts")
        dst = kexts / src.name
        if not src.is_dir():
            self._copy_into(kexts, src, "Kext")
            return
        if dst.exists():
            shutil.rmtree(str(dst))
        shutil.copytree(str(src), str(dst))

    def place_acpi(self, src: Path) -> None:
        self._copy_into(self._ensure("ACPI"), src, "ACPI")

    def place_tool(self, src: Path) -> None:
        self._copy_into(self._ensure("Tools"), src, "Tool")

    def write_plist(self, data: bytes, name: str = "config.plist") -> Path:
        target = self.oc / name
        target.write_bytes(data)
        return target

    # ---- config.plist ----
    def _kext_entries(self, kext_names: list) -> list[dict]:
        names = sorted(kext_names,
                       key=lambda n: (_KEXT_ORDER.get(_plain_name(n, ".kext"), 99),
                                      _plain_name(n, ".kext")))
        entries = []
        for raw in names:
            bundle_path = raw if raw.endswith(".kext") else f"{raw}.kext"
            bundle = bundle_path[: -len(".kext")]
            executable = self.oc / "Kexts" / bundle_path / "Contents" / "MacOS" / bundle
            entries.append({
                "Arch": "Any" if bundle in _KEXT_ORDER else "x86_64",
                "BundlePath": bundle_path,
                "Enabled": True,
                "ExecutablePath": f"Contents/MacOS/{bundle}" if executable.is_file() else "",
                "MaxKernel": "",
                "MinKernel": "",
                "PlistPath": "Contents/Info.plist",
                "Comment": "",
            })
        return entries

    def _driver_entries(self, driver_names: list | None) -> list[dict]:
        return [
            {
                "Path": name,
                "Enabled": True,
                "Comment": "",
                "Arguments": "",
                "HideVerbose": False,
                "LoadEarly": False,   # OpenVariableRuntimeDxe не используется
            }
            for name in (driver_names or [])
            if name and name not in _DRIVERS_SKIP
        ]

    def _acpi_entries(self, acpi_names: list) -> list[dict]:
        ordered = sorted(acpi_names,
                         key=lambda n: (_ACPI_ORDER.get(_plain_name(n, ".aml"), 50),
                                        _plain_name(n, ".aml")))
        return [
            {
                "Comment": Path(name).stem,
                "Enabled": True,
                "Path": name if name.endswith(".aml") else f"{name}.aml",
            }
            for name in ordered
        ]

    def write_plist_with_kexts(self, data: bytes, kext_names: list, name: str = "config.plist",
                               driver_names: list | None = None,
                               kernel_patches: list | None = None,
                               acpi_names: list | None = None) -> Path:
        """Пишет config.plist, подставляя реальные Kernel/Add, UEFI/Drivers и ACPI/Add."""
        cfg = plistlib.loads(data)
        cfg["Kernel"]["Add"] = self._kext_entries(kext_names)
        cfg["UEFI"]["Drivers"] = self._driver_entries(driver_names)
        if acpi_names:
            cfg["ACPI"]["Add"] = self._acpi_entries(acpi_names)
        if kernel_patches:
            cfg["Kernel"]["Patch"] = kernel_patches
        elif "Patch" not in cfg["Kernel"]:
            cfg["Kernel"]["Patch"] = []
        payload = plistlib.dumps(cfg, fmt=plistlib.FMT_XML, sort_keys=False)
        return self.write_plist(payload, name)


def extract_zip_clean(zip_path: Path, dest: Path) -> None:
    """Распаковка архива без служебных __MACOSX и отладочных .dSYM."""
    root = Path(dest).resolve()
    with zipfile.ZipFile(str(zip_path)) as archive:
        for member in archive.namelist():
            lowered = member.lower()
            if "__macosx" in lowered or lowered.endswith(".dsym") or "/.dsym" in lowered:
                continue
            target = (root / member).resolve()
            if target != root and root not in target.parents:
                continue  # не даём архиву писать за пределы папки
            archive.extract(member, str(root))
