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


#: Кексты, которые нельзя держать вместе: (первый, второй, пояснение).
#: Лежит здесь, чтобы им пользовались и анализ по профилю, и аудит готовой EFI.
KEXT_CONFLICTS = (
    ("NootRX", "WhateverGreen",
     "NootRX сам заводит Navi 2x и конфликтует с WhateverGreen: в документации "
     "проекта прямо запрещено держать их вместе."),
    ("AirportItlwm", "itlwm",
     "AirportItlwm и itlwm — две реализации одного драйвера Intel Wi-Fi, "
     "одновременно они не работают."),
    ("NootedRed", "WhateverGreen",
     "NootedRed сам заводит Vega APU и в требованиях проекта сказано удалить "
     "WhateverGreen — вместе они конфликтуют."),
    ("NootedRed", "NootRX",
     "NootedRed (iGPU) и NootRX (dGPU) не работают одновременно: в требованиях "
     "обоих проектов сказано удалить второй кекс."),
    ("VirtualSMC", "FakeSMC",
     "VirtualSMC и FakeSMC — два провайдера SMC, вместе ломают загрузку."),
)
