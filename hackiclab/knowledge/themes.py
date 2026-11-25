"""Темы графического меню OpenCanopy и превью из реальных иконок темы.

Официальный источник — acidanthera/OcBinaryData: тема «Acidanthera» с
вариантами Chardonnay / GoldenGate / Syrah. OpenCore показывает один вариант
(Misc → Boot → PickerVariant), но в EFI можно положить несколько и
переключать их в самом меню.
"""

from __future__ import annotations

from pathlib import Path

THEME_NAME = "Acidanthera"

#: (вариант, подпись RU, подпись EN)
VARIANTS: tuple[tuple[str, str, str], ...] = (
    ("GoldenGate", "GoldenGate — тёмное меню в стиле macOS",
     "GoldenGate — dark macOS-style menu"),
    ("Chardonnay", "Chardonnay — светлая классика",
     "Chardonnay — light classic"),
    ("Syrah", "Syrah — контрастная тёмная",
     "Syrah — high-contrast dark"),
)

#: Иконки, из которых собирается превью карточки.
PREVIEW_ICONS = ("AppleRecv", "HardDrive", "Windows", "Tool")

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def variant_ids() -> tuple[str, ...]:
    """Полные идентификаторы вариантов: «Acidanthera\\GoldenGate»."""
    return tuple(f"{THEME_NAME}\\{name}" for name, _ru, _en in VARIANTS)


def variant_label(variant: str, lang: str = "ru") -> str:
    """Человеческая подпись варианта по id или короткому имени."""
    short = short_name(variant)
    for name, ru, en in VARIANTS:
        if name == short:
            return en if str(lang).startswith("en") else ru
    return short


def short_name(variant: str) -> str:
    """«Acidanthera\\GoldenGate» → «GoldenGate»."""
    return (variant or "").replace("/", "\\").split("\\")[-1]


def picker_variant(variant: str) -> str:
    """Значение для Misc → Boot → PickerVariant."""
    return f"{THEME_NAME}\\{short_name(variant)}" if variant else ""


def variant_dir(resources: Path, variant: str) -> Path:
    """Папка варианта внутри EFI/OC/Resources."""
    return Path(resources) / "Image" / THEME_NAME / short_name(variant)


def available(resources: Path) -> list[str]:
    """Какие варианты реально лежат в Resources (полные id)."""
    out: list[str] = []
    for name, _ru, _en in VARIANTS:
        folder = Path(resources) / "Image" / THEME_NAME / name
        if folder.is_dir() and any(folder.iterdir()):
            out.append(f"{THEME_NAME}\\{name}")
    return out


def extract_png(icns_path: Path) -> bytes | None:
    """PNG из .icns: в контейнере Apple лежит готовый PNG-поток.

    Обходим без сторонних библиотек: ищем сигнатуру PNG и берём её до IEND.
    """
    try:
        data = Path(icns_path).read_bytes()
    except OSError:
        return None
    start = data.find(_PNG_MAGIC)
    if start < 0:
        return None
    end = data.find(b"IEND", start)
    if end < 0:
        return None
    return data[start:end + 8]


def preview_pngs_from_dir(folder: Path) -> list[bytes]:
    """PNG-иконки из указанной папки темы (порядок как в PREVIEW_ICONS)."""
    out: list[bytes] = []
    base = Path(folder)
    for name in PREVIEW_ICONS:
        for suffix in (".icns", ".png", ".jpg"):
            path = base / f"{name}{suffix}"
            if not path.is_file():
                continue
            png = (extract_png(path) if suffix == ".icns" else path.read_bytes())
            if png:
                out.append(png)
            break
    return out


def preview_pngs(resources: Path, variant: str) -> list[bytes]:
    """PNG-иконки варианта для карточки."""
    return preview_pngs_from_dir(variant_dir(resources, variant))


def looks_like_theme(folder: Path) -> bool:
    """Похожа ли папка на тему OpenCanopy (есть файлы .icns)."""
    path = Path(folder)
    return path.is_dir() and any(path.glob("*.icns"))


def custom_id(folder: Path) -> str:
    """Идентификатор сторонней темы: «custom\\<имя папки>»."""
    return f"custom\\{Path(folder).name}"


def is_custom(variant: str) -> bool:
    """Сторонняя ли тема (импортирована из папки)."""
    return str(variant).replace("/", "\\").startswith("custom\\")
