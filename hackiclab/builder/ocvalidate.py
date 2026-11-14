"""Интеграция утилиты ocvalidate из OpenCore.

ocvalidate проверяет config.plist на соответствие схеме и соглашениям
текущей версии OpenCore. Утилита входит в бинарный релиз OpenCorePkg
(Utilities/ocvalidate/...). Здесь она ищется в распакованном пакете,
а в EXE-сборке может скачиваться отдельно.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class OCVResult:
    ok: bool
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    full_output: str = ""
    # структурированные категории
    missing_keys: list = field(default_factory=list)      # "Missing key …" (схема неполная)
    schema_errors: list = field(default_factory=list)     # ошибки OCS: типа/структуры/значений
    version_note: str = ""                                # "ocvalidate X.Y.Z (compatible…)" доп.
    tool_version: str = ""                                # версия ocvalidate, если распознана
    tool_missing: bool = False                            # ocvalidate не найден

    @property
    def issues(self) -> list:
        return self.warnings + self.errors

    def categorized(self) -> list:
        """Возвращает список (категория, строка) для детального свода."""
        out = []
        for m in self.missing_keys:
            out.append(("missing", m))
        for e in self.schema_errors:
            out.append(("error", e))
        for w in self.warnings:
            out.append(("warning", w))
        return out


def find_ocvalidate(in_open_core_root: Optional[Path] = None) -> Optional[Path]:
    """Ищет бинарник ocvalidate.

    Сначала в распакованном OpenCore-пакете (Utilities/ocvalidate/*/ocvalidate*),
    затем в PATH. На Windows предпочитает .exe (в пакете есть и Linux/DSYM копии).
    """
    import os
    is_win = os.name == "nt"
    if in_open_core_root:
        candidates = list(in_open_core_root.rglob("ocvalidate*"))
        # приоритет: .exe на Windows, иначе первый файл
        for p in candidates:
            if p.is_file():
                if is_win and p.name == "ocvalidate.exe":
                    return p
                if not is_win and p.name == "ocvalidate":
                    return p
        for p in candidates:
            if p.is_file():
                return p
    p = shutil.which("ocvalidate")
    if p:
        return Path(p)
    return None


_VERSION_RE = re.compile(r"ocvalidate\s+([0-9]+\.[0-9]+\.[0-9]+)")


def run_ocvalidate(config_path: Path, ocvalidate: Optional[Path] = None) -> OCVResult:
    """Запускает ocvalidate config.plist и разбирает вывод по категориям."""
    if not config_path.exists():
        return OCVResult(ok=False, errors=[f"config.plist не найден: {config_path}"])
    # Если утилита не передана/не найдена — не блокируем, помечаем статистикой
    tool = ocvalidate or find_ocvalidate()
    if not tool:
        return OCVResult(ok=True, full_output="<ocvalidate не найден — пропущено>",
                         warnings=["ocvalidate не найден — валидация пропущена"],
                         tool_missing=True)
    try:
        r = subprocess.run([str(tool), str(config_path)],
                           capture_output=True, text=True, timeout=60)
    except Exception as e:
        return OCVResult(ok=False, errors=[f"ocvalidate не запустился: {e}"])
    out = (r.stdout or "") + "\n" + (r.stderr or "")
    out = out.strip()

    lines = out.splitlines()
    warnings: list = []
    errors: list = []
    missing: list = []
    schema: list = []
    version_note = ""
    mver = _VERSION_RE.search(out)
    tool_version = mver.group(1) if mver else ""

    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if "NOTE:" in s or "compatible with OpenCore" in s:
            version_note = s
            continue
        low = s.lower()
        if low.startswith("missing key") or low.startswith("osbs:"):
            missing.append(s)
        elif low.startswith("ocvalidate") and "compatible" in low:
            version_note = s
        elif s.startswith("OCS:"):
            schema.append(s)
            errors.append(s)
        elif "warning:" in low:
            warnings.append(s)
        elif "error:" in low:
            schema.append(s)
            errors.append(s)

    # ocvalidate: код возврата 0 == схема корректна; ошибки «Missing key» считаем
    # несовершенством схемы, а не блокирующими дефектами конфига.
    blocking = [e for e in errors if e not in missing]
    return OCVResult(
        ok=(r.returncode == 0 and not blocking),
        warnings=warnings,
        errors=errors,
        full_output=out,
        missing_keys=missing,
        schema_errors=[e for e in schema if e not in missing],
        version_note=version_note,
        tool_version=tool_version,
    )