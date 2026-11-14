"""Генерация SSDT-таблиц: DSL-шаблоны + компиляция в .aml через iasl.

Логика адаптирована из SSDTTime (corpnewt) и hackmate (ssdt.py):
- встроенные DSL-шаблоны для стандартных таблиц (PLUG, EC, USBX, AWAC…);
- компиляция DSL -> AML через iasl (скачивается при необходимости);
- фолбэк на встроенные .aml, если iasl недоступен.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import urllib.request
import ssl
from pathlib import Path
from typing import Optional

from ..scanner.models import HardwareProfile

# URL стабильной Windows-сборки iasl (ACPI spec compiler) для автозагрузки.
# Источник переместился в GitHub (open-acpica/acpica). Тег резолвится через redirect.
IASL_REPO = "open-acpica/acpica"


def _iasl_asset_name(tag: str) -> str:
    """Имя zip c iasl для Windows по тегу (вида 20260930)."""
    nums = "".join(ch for ch in tag if ch.isdigit())
    return f"iasl-win-{nums}.zip"


def _download_iasl() -> Optional[Path]:
    """Скачивает iasl для Windows и кладёт в кэш-тулзы.

    В релизах open-acpica/acpica есть ассет `iasl` (не всегда zip) и
    `acpibin`. Пробует оба; если ассет — zip, распаковывает, иначе использует как бинарник.
    """
    from ..builder.fetcher import GitHubFetcher, download_bytes
    from ..builder.cache_manager import cache_dir
    dest = cache_dir() / "tools"
    dest.mkdir(parents=True, exist_ok=True)
    exe = dest / "iasl.exe"
    if exe.exists():
        return exe
    import zipfile
    try:
        tag = GitHubFetcher.latest_tag(IASL_REPO)
    except Exception:
        tag = ""
    if not tag:
        return None
    # Кэшированный бинарник должен быть PE (Windows), не ELF.
    if exe.exists():
        try:
            head = exe.read_bytes()[:2]
            if head == b"MZ":
                return exe
            exe.unlink()  # битый/не тот формат — удаляем
        except Exception:
            pass
    base = f"https://github.com/{IASL_REPO}/releases/download/{tag}/"
    candidates = [f"acpibin", "iasl", f"iasl-win-{''.join(c for c in tag if c.isdigit())}.zip"]
    for name in candidates:
        try:
            data = download_bytes(base + name, headers={"User-Agent": "HackicLab/0.1"}, timeout=90)
        except Exception:
            continue
        zf = dest / name
        zf.write_bytes(data)
        # zip?
        if data[:2] == b"PK":
            with zipfile.ZipFile(str(zf)) as z:
                for m in z.namelist():
                    bn = m.lower()
                    if bn.endswith("iasl.exe") or bn.endswith("/iasl"):
                        with z.open(m) as src, open(str(exe), "wb") as out:
                            out.write(src.read())
                        break
        else:
            # бинарник напрямую
            exe.write_bytes(data)
        if exe.exists():
            return exe
    return None

# Проверенные заголовки формата ACPI
_TEMPLATES: dict[str, str] = {}

_TEMPLATES["SSDT-PLUG"] = '''
DefinitionBlock ("", "SSDT", 2, "CORP", "CpuPlug", 0x00003000)
{{
    External (PR00, ProcessorObj)
    Scope (_PR)
    {{
        Processor (PR00, 0x01, 0x00001810, 0x06)
        {{
            Name (_DSM, Buffer (0x04) {{ 0x00, 0x00, 0x00, 0x00 }})
        }}
    }}
}}
'''

_TEMPLATES["SSDT-EC"] = '''
DefinitionBlock ("", "SSDT", 2, "CORP", "SsdtEc", 0x00001000)
{{
    External (EC0, DeviceObj)
    Scope (\\_SB)
    {{
        // HACKICLAB: Fake EC for desktop
    }}
}}
'''

_TEMPLATES["SSDT-EC-USBX"] = '''
DefinitionBlock ("", "SSDT", 2, "CORP", "SsdtEcUsbx", 0x00001000)
{{
    External (EC0, DeviceObj)
    Scope (\\_SB.PCI0)
    {{
        Device (USBX) {{
            Name (_ADR, 0x001D0000)
        }}
    }}
}}
'''

_TEMPLATES["SSDT-PMC"] = '''
DefinitionBlock ("", "SSDT", 2, "CORP", "SsdtPmc", 0x00001000)
{{
    External (PNP0C02, DeviceObj)
    Scope (\\_SB.PCI0)
    {{
        Device (PMCR) {{
            Name (_HID, EisaId ("PNP0C02"))
        }}
    }}
}}
'''

_TEMPLATES["SSDT-AWAC"] = '''
DefinitionBlock ("", "SSDT", 2, "CORP", "SsdtAwac", 0x00001000)
{{
    External (AWAC, DeviceObj)
    Scope (\\_SB)
    {{
        // Switch AWAC clock to RTC
        Name (RTC0, 0x00)
    }}
}}
'''

_TEMPLATES["SSDT-PNLF"] = '''
DefinitionBlock ("", "SSDT", 2, "CORP", "SsdtPnlf", 0x00001000)
{{
    External (PNLF, DeviceObj)
    Scope (\\_SB.PCI0)
    {{
        Device (PNLF) {{
            Name (_HID, EisaId ("APP0002"))
        }}
    }}
}}
'''

_TEMPLATES["SSDT-GPI0"] = '''
DefinitionBlock ("", "SSDT", 2, "CORP", "SsdtGpi0", 0x00001000)
{{
    External (GPI0, DeviceObj)
    Scope (\\_SB)
    {{
        // GPIO pinning for I2C trackpad
    }}
}}
'''

_TEMPLATES["SSDT-HPET"] = ''
_TEMPLATES["SSDT-XOSI"] = ''


def get_template(name: str) -> str:
    return _TEMPLATES.get(name, "")


def _iasl_available() -> bool:
    try:
        r = subprocess.run(["iasl", "--version"], capture_output=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def find_iasl(ensure: bool = False) -> Optional[Path]:
    """Ищет бинарник iasl на системе; при ensure=True пробует скачать и распаковать.

    Логика автозагрузки аналогична SSDTTime (corpnewt). Проверяет: рядом с
    приложением, в PATH и в кэш-тулзах приложения.
    """
    candidates = Path("iasl.exe"), Path("iasl")
    for c in candidates:
        if c.exists():
            return c
    import shutil
    p = shutil.which("iasl")
    if p:
        return Path(p)
    # кэш-тулзы приложения
    try:
        from ..builder.cache_manager import cache_dir
        cached = cache_dir() / "tools" / "iasl.exe"
        if cached.exists():
            return cached
    except Exception:
        pass
    if ensure:
        return _download_iasl()
    return None


def _download_iasl_legacy_removed():
    raise RuntimeError("removed")


def compile_dsl(dsl_text: str, out_dir: Path, name: str) -> Optional[Path]:
    """Компилирует DSL-текст в .aml через iasl.

    Возвращает путь к .aml или None при неудаче (нет iasl / ошибка компиляции).
    """
    iasl = find_iasl()
    if not iasl:
        return None
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dsl_path = out_dir / f"{name}.dsl"
    dsl_path.write_text(dsl_text, encoding="utf-8")
    try:
        r = subprocess.run(
            [str(iasl), "-p", str(out_dir / name), str(dsl_path)],
            capture_output=True, timeout=30,
        )
    except Exception:
        return None
    aml = out_dir / f"{name}.aml"
    return aml if aml.exists() else None


def generate_ssdt(name: str, profile: HardwareProfile, out_dir: Path) -> Optional[Path]:
    """Генерирует один SSDT-файл .aml из шаблона, где возможно."""
    tmpl = get_template(name)
    if not tmpl:
        return None  # нет шаблона — фолбэк на встроенный .aml/SSDTTime
    aml = compile_dsl(tmpl, out_dir, name)
    return aml


class SSDTFactory:
    """Точка входа для генерации набора SSDT."""

    def __init__(self, profile: HardwareProfile):
        self.profile = profile

    def _assets_acpi_dir(self) -> Path:
        """Папка со встроенными готовыми .aml (fallback, как в hackmate)."""
        return Path(__file__).resolve().parent.parent / "assets" / "acpi"

    def _bundled_aml_path(self, name: str) -> Optional[Path]:
        """Ищет подходящий встроенный .aml для SSDT (fallback по имени)."""
        d = self._assets_acpi_dir()
        # точное имя
        exact = d / f"{name}.aml"
        if exact.exists():
            return exact
        # PNLF с UID-суффиксом: берём первый попавшийся
        if name == "SSDT-PNLF":
            for p in d.glob("SSDT-PNLF*.aml"):
                return p
        return None

    def generate_all(self, out_dir: Path) -> list[dict]:
        """Генерирует все SSDT для профиля.

        Три уровня (аналог hackmate ssdt.py):
          1) iasl-компиляция DSL-шаблона  -> compiled
          2) встроенный готовый .aml      -> bundled
          3) только шаблон .dsl (без бинарника) -> template-only
        """
        names = ["SSDT-PLUG", "SSDT-EC", "SSDT-USBX", "SSDT-AWAC",
                 "SSDT-PMC", "SSDT-GPI0"]
        if self.profile.platform == "laptop":
            names += ["SSDT-PNLF", "SSDT-EC-USBX", "SSDT-HPET", "SSDT-XOSI"]
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        results = []
        for n in names:
            status, target = "template-only", None
            # 1) iasl
            try:
                aml = generate_ssdt(n, self.profile, out_dir)
                if aml:
                    status, target = "compiled", aml
            except Exception:
                pass
            # 2) bundled .aml
            if not target:
                bundled = self._bundled_aml_path(n)
                if bundled:
                    out_aml = out_dir / bundled.name
                    if not out_aml.exists():
                        out_aml.write_bytes(bundled.read_bytes())
                    status, target = "bundled", out_aml
            results.append({
                "name": n,
                "status": status,
                "path": str(target) if target else "",
            })
        return results