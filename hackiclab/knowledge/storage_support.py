"""Накопители, с которыми macOS не работает: предупреждения до сборки.

Список — подмножество Anti-Hackintosh Buyers Guide (Dortania), только те
модели/контроллеры, что реально встречаются в сборках. Полный гайд шире:
https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StorageNote:
    """Правило по накопителю: что искать и насколько это критично."""

    match: tuple[str, ...]
    severity: str        # blocker / warning
    ru: str
    en: str


#: Ключи сравниваются с нижним регистром строк контроллеров и модели диска.
NOTES: tuple[StorageNote, ...] = (
    StorageNote(
        ("pm981", "pm991", "mzvlb"),
        "blocker",
        "Samsung PM981/PM991 (OEM): macOS не загрузится — контроллер не "
        "поддерживается. Нужен другой NVMe.",
        "Samsung PM981/PM991 (OEM): macOS will not boot — unsupported controller. "
        "Use another NVMe drive."),
    StorageNote(
        ("600p", "660p", "665p"),
        "warning",
        "Intel 600p/660p/665p: частые зависания и потери диска после сна. "
        "Работоспособность не гарантируется.",
        "Intel 600p/660p/665p: frequent hangs and drive dropouts after sleep. "
        "Not guaranteed to work."),
    StorageNote(
        ("970 evo plus", "970evoplus"),
        "warning",
        "Samsung 970 EVO Plus со старой прошивкой зависает: обновите firmware "
        "через Samsung Magician до сборки.",
        "Samsung 970 EVO Plus with old firmware hangs: update firmware via "
        "Samsung Magician before building."),
    StorageNote(
        ("asm1061", "asm1062", "asm106x"),
        "blocker",
        "SATA-контроллер ASMedia ASM1061/1062: диски за ним macOS не увидит.",
        "ASMedia ASM1061/1062 SATA controller: macOS will not see drives behind it."),
    StorageNote(
        ("88se92", "88se9230", "88se9215"),
        "warning",
        "Marvell 88SE92xx: SATA-порты работают нестабильно, лучше использовать "
        "порты чипсета.",
        "Marvell 88SE92xx: SATA ports are unstable, prefer chipset ports."),
)


def _haystack(storage) -> str:
    parts: list[str] = []
    for item in getattr(storage, "controllers", None) or []:
        parts.append(str(item))
    for field in ("nvme_name", "sata_name"):
        value = getattr(storage, field, "")
        if value:
            parts.append(str(value))
    return " ".join(parts).lower().replace("_", "")


def storage_notes(storage) -> list[StorageNote]:
    """Найденные проблемы накопителей (пусто, если всё в порядке)."""
    text = _haystack(storage)
    if not text:
        return []
    return [n for n in NOTES if any(key in text for key in n.match)]


def warnings(storage, lang: str = "ru") -> list[str]:
    """Тексты предупреждений на выбранном языке."""
    en = str(lang).startswith("en")
    return [n.en if en else n.ru for n in storage_notes(storage)]
