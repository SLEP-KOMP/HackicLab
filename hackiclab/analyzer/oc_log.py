"""Разбор логов OpenCore: находим типовую ошибку загрузки и подсказываем шаг.

Правила ниже терпимы к различиям в формате между версиями OpenCore: сверяем
характерные фрагменты строк, а не точный текст. Подсказки живут в i18n
(`oclog.hint.<код>`), поэтому работают и по-русски, и по-английски.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class LogFinding:
    severity: str          # "error" | "warn" | "info"
    key: str               # ключ i18n
    detail: str = ""       # техническая строка из лога (без перевода)


# Код правила совпадает с суффиксом ключа i18n "oclog.hint.<код>".
# Порядок важен: первое совпадение выигрывает, частные случаи идут раньше общих.
_RULES: tuple[tuple[str, str], ...] = (
    ("root_hash", r"root_?hash[^\n]*Err\(|Err\(0xE\)[^\n]*root_?hash"),
    ("eb_ld", r"Err\(0xE\)[^\n]*EB\.LD|Cannot open EB\.LD"),
    ("mmio_stall", r"OCABC[^\n]*MMIO[^\n]*stall|MMIO[^\n]*(?:not|un)supported"),
    ("panic_init", r"panic[^\n]*(?:prior to|before)[^\n]*init"),
    ("lilu_missing", r"(?:requires|needs) Lilu|Lilu(?:\.kext)?[^\n]*(?:absent|not (?:found|loaded))"),
    ("kext_load", r"Could not load[^\n]*\.kext"),
    ("kext_inject", r"inject[^\n]*kext[^\n]*(?:fail|error)|fail[^\n]*inject[^\n]*kext"),
    ("driver_load", r"OC:[^\n]*load[^\n]*\.efi[^\n]*fail|fail[^\n]*load[^\n]*\.efi"),
    ("board_id", r"board-?id[^\n]*(?:not supported|mismatch|unsupported)"),
    ("security_policy", r"(?:blocked|denied)[^\n]*security policy|apfs[^\n]*security"),
    ("hidden_recovery", r"(?:HideAuxiliary|auxiliary)[^\n]*(?:hidden|not (?:shown|visible))"),
    ("malloc", r"(?:malloc|alloc)[^\n]*fail"),
    ("gpio_timeout", r"(?:VoodooI2C|GPIO)[^\n]*timeout"),
    ("alcid", r"AppleALC[^\n]*layout[^\n]*(?:not found|missing)|layout-?id[^\n]*invalid"),
    ("weg_patch", r"(?:WhateverGreen|WEG)[^\n]*(?:fail|patch[^\n]*fail)"),
    ("nvme_power", r"NVMeFix[^\n]*(?:not supported|fail)|nvme[^\n]*power[^\n]*fail"),
    ("smc_key", r"SMC[^\n]*(?:key[^\n]*not found|fail)|VirtualSMC[^\n]*fail"),
)

_COMPILED: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (code, re.compile(pattern, re.IGNORECASE)) for code, pattern in _RULES
)

# Строки без известного шаблона: показываем их как «сырые» ошибки.
_RUMBLE = re.compile(r"Err\(|error|panic|fail", re.IGNORECASE)


def parse_log_text(text: str) -> list[LogFinding]:
    """Все совпавшие правила; иначе — сырые строки ошибок; иначе «чисто»."""
    found: list[LogFinding] = []
    for code, regex in _COMPILED:
        hit = regex.search(text)
        if hit is not None:
            found.append(LogFinding("error", f"oclog.hint.{code}", hit.group(0).strip()))
    if found:
        return found

    noise = [row.strip() for row in text.splitlines() if _RUMBLE.search(row)]
    if noise:
        return [LogFinding("warn", "oclog.raw_unknown", "\n".join(noise[:10]))]
    return [LogFinding("info", "oclog.clean")]


def parse_log_file(path: Path) -> list[LogFinding]:
    """Разбирает файл лога; ошибка чтения — отдельная запись."""
    try:
        text = Path(path).read_text(errors="replace")
    except OSError:
        return [LogFinding("error", "oclog.read_error")]
    return parse_log_text(text)


def find_oc_log(root: Path) -> Optional[Path]:
    """Свежий opencore-*.txt в папке сборки; можно передать и сам файл."""
    root = Path(root)
    if root.is_file():
        return root
    for folder in (root / "EFI" / "OC", root):
        try:
            logs = sorted(folder.glob("opencore-*.txt"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            continue
        if logs:
            return logs[0]
    return None


def enable_logging(config_path: Path) -> bool:
    """Включает файловый лог OpenCore в config.plist, оставляя .bak рядом."""
    import plistlib
    import shutil

    path = Path(config_path)
    try:
        with open(path, "rb") as fh:
            cfg = plistlib.load(fh)
        debug = cfg.setdefault("Misc", {}).setdefault("Debug", {})
        debug.update({
            "AppleDebug": True,
            "ApplePanic": True,
            "DisableWatchDog": True,
            "Target": 67,               # файл + последовательный порт
            "DisplayLevel": 2147483650,
        })
        try:
            shutil.copy2(path, path.with_name(path.name + ".bak"))
        except OSError:
            pass
        with open(path, "wb") as fh:
            plistlib.dump(cfg, fh)
        return True
    except (OSError, ValueError):
        return False


def summarise(findings: list[LogFinding]) -> dict:
    """Счётчики по уровням для интерфейса."""
    counts = {"error": 0, "warn": 0, "info": 0}
    for item in findings:
        counts[item.severity] = counts.get(item.severity, 0) + 1
    return counts
