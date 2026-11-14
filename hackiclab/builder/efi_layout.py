"""Формирование файловой структуры EFI и запись на диск."""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class EFIBuildResult:
    root: Path            # папка, куда записана EFI
    ok: bool
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)  # {categ: [names]}


class EFILayout:
    """Создаёт типовую структуру EFI/OC и раскладывает компоненты."""
    OC_FOLDERS = ("ACPI", "Drivers", "Kexts", "Tools")

    def __init__(self, root: Path):
        self.root = root
        self.oc = root / "EFI" / "OC"
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def create(self) -> None:
        self.oc.mkdir(parents=True, exist_ok=True)
        for f in self.OC_FOLDERS:
            (self.oc / f).mkdir(parents=True, exist_ok=True)

    def place_bootx64(self, source_efi: Path) -> None:
        """Копирует OpenCore.efi в EFI/BOOT/BOOTx64.EFI (или BOOTx64.efi)."""
        boot = self.root / "EFI" / "BOOT"
        boot.mkdir(parents=True, exist_ok=True)
        dst = boot / "BOOTx64.efi"
        try:
            shutil.copy2(str(source_efi), str(dst))
        except Exception as e:
            self.errors.append(f"BOOTx64: {e}")

    def place_driver(self, src: Path) -> None:
        (self.oc / "Drivers").mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(self.oc / "Drivers" / src.name))

    def place_kext(self, src: Path) -> None:
        (self.oc / "Kexts").mkdir(parents=True, exist_ok=True)
        dst = self.oc / "Kexts" / src.name
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(str(dst))
            shutil.copytree(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))

    def place_acpi(self, src: Path) -> None:
        (self.oc / "ACPI").mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(self.oc / "ACPI" / src.name))

    def place_tool(self, src: Path) -> None:
        (self.oc / "Tools").mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(self.oc / "Tools" / src.name))

    def write_plist(self, data: bytes, name: str = "config.plist") -> Path:
        p = self.oc / name
        p.write_bytes(data)
        return p

    def write_plist_with_kexts(self, data: bytes, kext_names: list, name: str = "config.plist") -> Path:
        """Записывает config.plist, дополнительно заполняя Kernel/Add реальными kext.

        Kексты по имени добавляются в Kernel/Add с BundlePath=имя, Enabled=True —
        важно, чтобы ocvalidate и сам загрузчик видели кексты в конфиге.
        """
        import plistlib
        cfg = plistlib.loads(data)
        adds = []
        for k in kext_names:
            if not k.endswith(".kext"):
                k = k + ".kext"
            adds.append({
                "BundlePath": k,
                "Enabled": True,
                "PlistPath": "Contents/Info.plist",
                "Comment": "",
            })
        cfg["Kernel"]["Add"] = adds
        out = plistlib.dumps(cfg, fmt=plistlib.FMT_XML, sort_keys=False)
        return self.write_plist(out, name)


def extract_zip_clean(zip_path: Path, dest: Path) -> None:
    """Распаковка zip без __MACOSX и dSYM (hackmate-подход)."""
    dest = dest.resolve()
    with zipfile.ZipFile(str(zip_path)) as z:
        for member in z.namelist():
            low = member.lower()
            if "__macosx" in low or ".dsym" in low:
                continue
            target = (dest / member).resolve()
            if target != dest and dest not in target.parents:
                continue  # zip-slip guard
            z.extract(member, str(dest))