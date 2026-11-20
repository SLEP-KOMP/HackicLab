"""Генерация SSDT-таблиц: DSL-шаблоны и компиляция в .aml через iasl.

Таблицы собираются тремя путями, по убыванию точности:
- DSL-шаблон под профиль железа, скомпилированный iasl (скачивается сам);
- готовый .aml из ``assets/acpi``, если компилятора нет;
- только исходник .dsl — когда нет ни того, ни другого.

Пути контроллеров для USB-сброса и AWAC берутся из DSDT пользователя,
поэтому таблицы не привязаны к одной материнской плате.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from ..knowledge.ssdt_logics import required_ssdts
from ..proc import run as hidden_run
from ..scanner.models import HardwareProfile

# URL стабильной Windows-сборки iasl (ACPI spec compiler) для автозагрузки.
# Источник переместился в GitHub (open-acpica/acpica). Тег резолвится через redirect.
IASL_REPO = "open-acpica/acpica"


def _windows_iasl_zip_urls() -> list[str]:
    """Прямые ссылки на Windows-архив iasl со страницы релизов acpica.

    В релизах open-acpica/acpica Windows-сборки лежат как user-attachments,
    а не как release assets, поэтому ищем их в HTML страницы релизов.
    """
    from ..builder.fetcher import download_bytes
    try:
        html = download_bytes(
            f"https://github.com/{IASL_REPO}/releases",
            headers={"User-Agent": "HackicLab/0.1"},
            timeout=90,
        ).decode("utf-8", "replace")
    except Exception:
        return []
    urls: list[str] = []
    for url in re.findall(r'href="(https://github\.com/user-attachments/files/[^"]+)"', html):
        low = url.lower()
        if "iasl-win-" in low and low.endswith(".zip") and url not in urls:
            urls.append(url)
    return urls


# Стабильный фолбэк: Windows-сборка iasl из репозитория corpnewt.
IASL_LEGACY_ZIP = "https://raw.githubusercontent.com/corpnewt/iasl-legacy/main/iasl-legacy-windows.zip"


def _is_pe_binary(path: Path) -> bool:
    try:
        return path.exists() and path.read_bytes()[:2] == b"MZ"
    except Exception:
        return False


def _extract_iasl_from_zip(data: bytes) -> Optional[bytes]:
    """Достаёт PE-исполняемый iasl из архива (None, если нет)."""
    import io
    import zipfile
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for member in z.namelist():
                low = member.lower()
                if not low.endswith(".exe") or "iasl" not in low:
                    continue
                payload = z.read(member)
                if payload[:2] == b"MZ":
                    return payload
    except Exception:
        return None
    return None


def _download_iasl() -> Optional[Path]:
    """Скачивает iasl для Windows и кладёт в кэш-тулзы.

    Windows-сборки acpica публикуются как user-attachments на странице
    релизов; если их не нашли — берём стабильный legacy-архив corpnewt.
    Принимаем только PE (MZ): ELF в кэше «молча» ломает компиляцию.
    """
    from ..builder.cache_manager import cache_dir
    from ..builder.fetcher import download_bytes
    dest = cache_dir() / "tools"
    dest.mkdir(parents=True, exist_ok=True)
    exe = dest / "iasl.exe"
    if _is_pe_binary(exe):
        return exe
    try:
        exe.unlink(missing_ok=True)
    except Exception:
        pass

    urls = _windows_iasl_zip_urls()
    urls.append(IASL_LEGACY_ZIP)
    for url in urls:
        try:
            data = download_bytes(url, headers={"User-Agent": "HackicLab/0.1"}, timeout=120)
        except Exception:
            continue
        if data[:2] != b"PK":
            continue
        payload = _extract_iasl_from_zip(data)
        if payload:
            exe.write_bytes(payload)
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

_TEMPLATES["SSDT-GPRW"] = '''
DefinitionBlock ("", "SSDT", 2, "HACK", "SsdtGPRW", 0x00000000)
{{
    // Сон/пробуждение: macOS не просыпается по _PRW со значением 0x6D.
    // Работает вместе с ACPI > Patch, который переименовывает _PRW в XPRW.
    // Пакет собирается через Local0: iasl 2025 не принимает ссылки на Arg
    // прямо в инициализаторе Package.
    Method (GPRW, 2, NotSerialized)
    {{
        Local0 = Package (0x02) {{ 0x6D, Zero }}
        Local0 [0] = Arg0
        Local0 [1] = Arg1
        If ((0x6D == Arg0))
        {{
            Local0 [1] = Zero
        }}
        Return (Local0)
    }}
}}
'''

_TEMPLATES["SSDT-HPET"] = ''
_TEMPLATES["SSDT-XOSI"] = ''


def get_template(name: str) -> str:
    return _TEMPLATES.get(name, "")


def render_template(name: str) -> str:
    """Шаблон в виде готового DSL: снимает экранирование фигурных скобок."""
    tmpl = get_template(name)
    if not tmpl:
        return ""
    return tmpl.format()


def _enclosing_scopes(dsl_text: str, index: int) -> list[str]:
    """Имена Scope/Device, внутри которых стоит позиция ``index`` (снаружи внутрь)."""
    prefix = dsl_text[:index]
    names: list[str] = []
    depth = 0
    for pos in range(len(prefix) - 1, -1, -1):
        char = prefix[pos]
        if char == "}":
            depth += 1
        elif char == "{":
            depth -= 1
            if depth < 0:
                depth = 0
                head = prefix[:pos]
                match = re.search(r"(Device|Scope|Processor)\s*\(\s*([^)]+)\)\s*$", head)
                if match:
                    names.append(match.group(2).strip())
    names.reverse()
    return names


def rhub_path(dsl_text: str) -> str:
    """Полный ACPI-путь устройства RHUB внутри XHCI (пусто, если его нет).

    USB-хаб на новых платах объявлен как ``Device (RHUB)``; SSDT-RHUB гасит его
    через ``_STA = 0``, и macOS сам поднимает порты заново.
    """
    match = re.search(r"Device\s*\(\s*RHUB\s*\)", dsl_text or "", re.IGNORECASE)
    if not match:
        return ""
    parts: list[str] = []
    for scope in _enclosing_scopes(dsl_text, match.start()):
        parts.extend(part for part in scope.split(".") if part)
    parts.append("RHUB")
    return "\\" + ".".join(parts)


def build_usb_reset(dsl_text: str) -> str:
    """DSL для SSDT-USB-Reset по декомпилированному DSDT (пусто без RHUB)."""
    path = rhub_path(dsl_text)
    if not path:
        return ""
    return f'''
DefinitionBlock ("", "SSDT", 2, "Hackic", "UsbReset", 0x00000000)
{{
    External ({path}, DeviceObj)

    Scope ({path})
    {{
        Method (_STA, 0, NotSerialized)
        {{
            Return (Zero)
        }}
    }}
}}
'''


def _iasl_available() -> bool:
    try:
        r = hidden_run(["iasl", "--version"], capture_output=True, timeout=10)
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
        if _is_pe_binary(c):
            return c
    import shutil
    p = shutil.which("iasl")
    if p:
        return Path(p)
    if os.name != "nt":
        # macOS/Linux: Windows-архив iasl не подойдёт, ищем системный компилятор
        # (на macOS ставится через `brew install acpica`).
        for folder in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"):
            candidate = Path(folder) / "iasl"
            if candidate.is_file():
                return candidate
        return None
    # кэш-тулзы приложения: ELF из старых загрузок не годится
    try:
        from ..builder.cache_manager import cache_dir
        cached = cache_dir() / "tools" / "iasl.exe"
        if cached.exists():
            if _is_pe_binary(cached):
                return cached
            cached.unlink(missing_ok=True)
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
        hidden_run(
            [str(iasl), "-p", str(out_dir / name), str(dsl_path)],
            capture_output=True, timeout=30,
        )
    except Exception:
        return None
    aml = out_dir / f"{name}.aml"
    return aml if aml.exists() else None


def generate_ssdt(name: str, profile: HardwareProfile, out_dir: Path,
                  dsdt_text: str = "") -> Optional[Path]:
    """Генерирует один SSDT-файл .aml; USB-Reset строится по DSDT."""
    if name == "SSDT-USB-Reset":
        dsl = build_usb_reset(dsdt_text)
        return compile_dsl(dsl, out_dir, name) if dsl else None
    tmpl = render_template(name)
    if not tmpl:
        return None  # нет шаблона — фолбэк на встроенный .aml/SSDTTime
    aml = compile_dsl(tmpl, out_dir, name)
    return aml


class SSDTFactory:
    """Точка входа для генерации набора SSDT."""

    def __init__(self, profile: HardwareProfile, dsdt_text: str = ""):
        self.profile = profile
        # Декомпилированный DSDT: нужен для таблиц, которые строятся по железу
        # (сейчас — SSDT-USB-Reset по устройству RHUB).
        self.dsdt_text = dsdt_text

    def _assets_acpi_dir(self) -> Path:
        """Папка со встроенными готовыми .aml — фолбэк, если iasl недоступен."""
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

    def _effective_names(self) -> list[str]:
        """Список таблиц под профиль, с поправкой на содержимое DSDT.

        AWAC добавляется, только если в DSDT действительно есть эти часы:
        на старых платах таблица бессмысленна и только злит валидатор.
        """
        names = [spec.name for spec in required_ssdts(self.profile)]
        if self.dsdt_text and "AWAC" not in self.dsdt_text:
            names = [n for n in names if n != "SSDT-AWAC"]
        return names

    def _compiled(self, name: str, out_dir: Path) -> Optional[Path]:
        try:
            return generate_ssdt(name, self.profile, out_dir, dsdt_text=self.dsdt_text)
        except Exception:
            return None

    def _bundled(self, name: str, out_dir: Path) -> Optional[Path]:
        source = self._bundled_aml_path(name)
        if source is None:
            return None
        target = out_dir / source.name
        if not target.exists():
            target.write_bytes(source.read_bytes())
        return target

    def generate_all(self, out_dir: Path) -> list[dict]:
        """Генерирует все SSDT для профиля.

        Сначала берётся готовый встроенный .aml: он проверен на реальных
        платах, а DSL-шаблон даёт упрощённую таблицу. Шаблон компилируется
        только когда готового .aml нет, иначе статус ``template-only``.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        results: list[dict] = []
        for name in self._effective_names():
            target = self._bundled(name, out_dir)
            status = "bundled"
            if target is None:
                target = self._compiled(name, out_dir)
                status = "compiled"
            if target is None:
                status = "template-only"
            results.append({
                "name": name,
                "status": status,
                "path": str(target) if target else "",
            })
        return results
