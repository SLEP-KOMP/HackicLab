"""Интеграция утилиты ocvalidate из OpenCore.

ocvalidate проверяет config.plist на соответствие схеме и соглашениям
текущей версии OpenCore. Утилита входит в бинарный релиз OpenCorePkg
(Utilities/ocvalidate/...). Здесь она ищется в распакованном пакете,
а в EXE-сборке может скачиваться отдельно.
"""

from __future__ import annotations

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

    @property
    def issues(self) -> list:
        return self.warnings + self.errors


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


def run_ocvalidate(config_path: Path, ocvalidate: Optional[Path] = None) -> OCVResult:
    """Запускает ocvalidate config.plist и разбирает вывод."""
    if not config_path.exists():
        return OCVResult(ok=False, errors=[f"config.plist не найден: {config_path}"])
    # Если утилита не передана/не найдена — не блокируем, помечаем статистикой
    tool = ocvalidate or find_ocvalidate()
    if not tool:
        return OCVResult(ok=True, full_output="<ocvalidate не найден — пропущено>",
                         warnings=["ocvalidate не найден — валидация пропущена"])
    try:
        r = subprocess.run([str(tool), str(config_path)],
                           capture_output=True, text=True, timeout=60)
    except Exception as e:
        return OCVResult(ok=False, errors=[f"ocvalidate не запустился: {e}"])
    out = (r.stdout or "") + "\n" + (r.stderr or "")
    out = out.strip()

    lines = out.splitlines()
    warnings = []
    errors = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        # вынос специальных retcode-фраз
        if "NOTE:" in s or "compatible with OpenCore" in s:
            continue
        low = s.lower()
        if "warning:" in low:
            warnings.append(s)
        elif "error:" in low:
            errors.append(s)
        elif s.startswith("OCS:"):
            errors.append(s)
        elif low.startswith("missing key"):
            errors.append(s)

    return OCVResult(
        ok=(r.returncode == 0 and not errors),
        warnings=warnings,
        errors=errors,
        full_output=out,
    )