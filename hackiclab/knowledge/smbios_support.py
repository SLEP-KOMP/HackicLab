"""Диапазоны macOS для SMBIOS-моделей, которые мы выдаём.

Модель обязана существовать в выбранной macOS: iMac19,1 не появится в
High Sierra, а iMacPro1,1 не «доживает» до Sequoia. Таблица — только те
модели, которые встречаются в SMBIOS_MAP/_AMD_DESKTOP_SMBIOS; сверять с
официальными списками Apple при добавлении новых.
"""

from __future__ import annotations

#: Модель -> (минимальная macOS, максимальная macOS).
SUPPORT: dict[str, tuple[str, str]] = {
    "MacBookPro8,1": ("High Sierra", "High Sierra"),
    "MacBookPro9,2": ("High Sierra", "Catalina"),
    "MacBookPro11,1": ("High Sierra", "Catalina"),
    "MacBookPro12,1": ("High Sierra", "Monterey"),
    "MacBookPro13,1": ("High Sierra", "Ventura"),
    "MacBookPro14,1": ("High Sierra", "Ventura"),
    "MacBookPro15,2": ("Mojave", "Sequoia"),
    "MacBookPro16,1": ("Catalina", "Tahoe"),
    "MacBookPro16,2": ("Catalina", "Tahoe"),
    "iMac13,1": ("High Sierra", "Catalina"),
    "iMac14,2": ("High Sierra", "Catalina"),
    "iMac15,1": ("High Sierra", "Monterey"),
    "iMac17,1": ("High Sierra", "Monterey"),
    "iMac18,3": ("High Sierra", "Ventura"),
    "iMac19,1": ("Mojave", "Sequoia"),
    "iMac20,1": ("Catalina", "Tahoe"),
    "iMacPro1,1": ("High Sierra", "Sonoma"),
    "MacPro7,1": ("Catalina", "Tahoe"),
}

#: Порядок версий: индекс = «новее».
ORDER: tuple[str, ...] = (
    "High Sierra", "Mojave", "Catalina", "Big Sur", "Monterey",
    "Ventura", "Sonoma", "Sequoia", "Tahoe", "Golden Gate",
)


def _bare(name: str) -> str:
    return (name or "").replace("macOS ", "").strip()


def index_of(name: str) -> int:
    bare = _bare(name)
    return ORDER.index(bare) if bare in ORDER else -1


def support(model: str) -> tuple[str, str] | None:
    """Диапазон модели или None, если модели нет в таблице."""
    return SUPPORT.get(model or "")


def supports(model: str, macos: str) -> bool:
    """Поддерживает ли модель указанную macOS (неизвестная модель — да)."""
    rng = support(model)
    if rng is None:
        return True
    need = index_of(macos)
    if need < 0:
        return True
    return index_of(rng[0]) <= need <= index_of(rng[1])


def pick(candidates: list[str], macos: str) -> str:
    """Первая модель из списка, которая держит нужную macOS; иначе последняя."""
    for model in candidates:
        if supports(model, macos):
            return model
    return candidates[-1] if candidates else ""
