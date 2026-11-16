"""Модуль анализа и рекомендаций.

Сопоставляет скан железа с файлами/папкой EFI клиента, находит недостающие
компоненты, устаревшие версии, несовместимости и выдаёт предупреждения +
рекомендации. Здесь реализуется ключевая функция «укажи свои файлы — HackicLab
проверит и подскажет».
"""

from .engine import (
    AnalysisIssue,
    Analyzer,
    Severity,
    analyze_folders,
    analyze_profile,
)

__all__ = [
    "AnalysisIssue",
    "Analyzer",
    "Severity",
    "analyze_folders",
    "analyze_profile",
]
