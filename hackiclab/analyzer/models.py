"""Общие модели анализа: уровень серьёзности и замечание.

Вынесены из engine.py, чтобы efi_health.py мог пользоваться ими без
циклического импорта (engine → efi_health → engine).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Severity(IntEnum):
    INFO = 0
    WARNING = 1
    ERROR = 2


@dataclass
class AnalysisIssue:
    severity: Severity
    code: str            # машинный идентификатор (kext_missing, etc.)
    title: str           # локализуемый ключ/текст
    detail: str = ""
    kext: str = ""       # имя кекста, если относится к кексту
    suggestion: str = ""

    @property
    def sev_label(self) -> str:
        return {Severity.INFO: "info", Severity.WARNING: "warning",
                Severity.ERROR: "error"}[self.severity]
