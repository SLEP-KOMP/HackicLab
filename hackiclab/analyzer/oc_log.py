"""Разбор логов OpenCore: типовые ошибки загрузки -> причина и что делать.

Логика адаптирована из hackmate (oc_log.py, MIT): регулярные выражения
терпимы к изменениям формата между версиями OpenCore, тексты подсказок
живут в i18n (`oclog.hint.*`), чтобы работали RU и EN.
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


# (код -> регулярка); код превращается в ключ i18n "oclog.hint.<код>".
_PATTERNS: list[tuple[str, str]] = [
    ("root_hash", r"Err\(0xE\).*root_hash"),
    ("eb_ld", r"Err\(0xE\).*EB\.LD"),
    ("mmio_stall", r"OCABC.*MMIO.*stall"),
    ("panic_init", r"panic.*prior to initialization"),
    ("kext_load", r"Could not load.*\.kext"),
    ("lilu_missing", r"Lilu.*not found|requires Lilu"),
    ("kext_inject", r"Failed to inject.*kext"),
    ("driver_load", r"OC: Failed to load.*efi"),
    ("board_id", r"board-id.*not supported|board id.*mismatch"),
    ("security_policy", r"Blocked by.*security policy|apfs.*security"),
    ("hidden_recovery", r"HideAuxiliary.*recovery.*hidden|auxiliary.*not.*show"),
    ("malloc", r"malloc.*failed|alloc.*failed"),
    ("gpio_timeout", r"VoodooI2C.*gpio.*timeout|GPIO.*timeout"),
    ("alcid", r"AppleALC.*layout.*not found|layout.*id.*invalid"),
    ("weg_patch", r"WhateverGreen.*failed|WEG.*patch.*failed"),
    ("nvme_power", r"NVMeFix.*not.*supported|nvme.*power.*management.*failed"),
    ("smc_key", r"SMC.*key.*not found|VirtualSMC.*failed"),
]

_RAW_ERROR_RE = re.compile(r"Err\(|FAIL|panic", re.IGNORECASE)


def parse_log_text(text: str) -> list[LogFinding]:
    """Ищет известные ошибки; если их нет — сырые строки ошибок или «чисто»."""
    findings: list[LogFinding] = []
    for code, pattern in _PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            findings.append(LogFinding("error", f"oclog.hint.{code}",
                                       match.group(0).strip()))
    if findings:
        return findings

    raw = [line.strip() for line in text.splitlines() if _RAW_ERROR_RE.search(line)]
    if raw:
        return [LogFinding("warn", "oclog.raw_unknown", "\n".join(raw[:10]))]

    return [LogFinding("info", "oclog.clean")]


def parse_log_file(path: Path) -> list[LogFinding]:
    """Разбирает файл лога; ошибка чтения — отдельная запись."""
    try:
        text = Path(path).read_text(errors="replace")
    except Exception:
        return [LogFinding("error", "oclog.read_error")]
    return parse_log_text(text)


def find_oc_log(root: Path) -> Optional[Path]:
    """Ищет свежий opencore-*.txt в папке (или принимает сам файл)."""
    root = Path(root)
    if root.is_file():
        return root
    for folder in (root / "EFI" / "OC", root):
        try:
            logs = sorted(folder.glob("opencore-*.txt"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        except Exception:
            continue
        if logs:
            return logs[0]
    return None


def enable_logging(config_path: Path) -> bool:
    """Включает файловый лог OpenCore в config.plist (с резервной копией)."""
    import plistlib
    import shutil

    path = Path(config_path)
    try:
        with open(path, "rb") as f:
            cfg = plistlib.load(f)
        debug = (cfg.setdefault("Misc", {})).setdefault("Debug", {})
        debug["AppleDebug"] = True
        debug["ApplePanic"] = True
        debug["DisableWatchDog"] = True
        debug["Target"] = 67            # файл + последовательный порт
        debug["DisplayLevel"] = 2147483650
        try:
            shutil.copy2(path, path.with_name(path.name + ".bak"))
        except Exception:
            pass
        with open(path, "wb") as f:
            plistlib.dump(cfg, f)
        return True
    except Exception:
        return False


def summarise(findings: list[LogFinding]) -> dict:
    """Счётчики по уровням для интерфейса."""
    counts = {"error": 0, "warn": 0, "info": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return counts
