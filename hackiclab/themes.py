"""Темы оформления HackicLab.

Темы строятся из палитр, а не из трёх независимых QSS-простыней: так проще
добавлять новые оформления и подмешивать пользовательский фон.

- ``system`` — следует теме Windows (реестр AppsUseLightTheme);
- ``light`` / ``dark`` — базовые;
- ``custom`` — фирменная тема с возможностью подставить своё изображение;
- ``aqua``, ``graphite``, ``sonoma``, ``bigsur`` — встроенные оформления
  в духе macOS. Это собственные градиенты и цвета, без ассетов Apple.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str
    panel: str
    border: str
    text: str
    muted: str
    accent: str
    accent_hover: str
    accent_text: str
    input_bg: str
    code_bg: str
    hover: str
    gradient: str = ""          # градиент для кнопок и выделения


DARK = Palette(
    "dark", "#1e1e2e", "#181825", "#313244", "#cdd6f4", "#7f849c",
    "#8839ef", "#9d4ef0", "#ffffff", "#181825", "#11111b", "#313244",
)

LIGHT = Palette(
    "light", "#f4f5f7", "#ffffff", "#d0d3d8", "#1f2328", "#6c7278",
    "#8839ef", "#9d4ef0", "#ffffff", "#ffffff", "#ffffff", "#e0e3e6",
)

CUSTOM = Palette(
    "custom", "#0f172a", "#0b1120", "#1e293b", "#e2e8f0", "#64748b",
    "#06b6d4", "#22d3ee", "#ffffff", "#0b1120", "#0b1120", "#1e293b",
    "qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #06b6d4, stop:1 #8b5cf6)",
)

AQUA = Palette(
    "aqua", "#eef5fb", "#ffffff", "#c7d9ea", "#10243a", "#5b7591",
    "#0a84ff", "#3d9bff", "#ffffff", "#ffffff", "#f6fafd", "#dbe8f4",
    "qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0a84ff, stop:1 #64b5ff)",
)

GRAPHITE = Palette(
    "graphite", "#232427", "#1b1c1f", "#33353a", "#e8e9ec", "#8b8e96",
    "#8e9198", "#a8abb3", "#101114", "#1b1c1f", "#17181b", "#2c2e33",
    "qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #6f747d, stop:1 #a8abb3)",
)

SONOMA = Palette(
    "sonoma", "#1c1420", "#241a29", "#3a2b41", "#f7e9f0", "#b39bab",
    "#ff7ab6", "#ff9bc8", "#2b0f1c", "#241a29", "#180f1d", "#34243c",
    "qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #ff7ab6, stop:1 #ffb454)",
)

BIGSUR = Palette(
    "bigsur", "#0b1226", "#111a33", "#223055", "#e6ecfb", "#8b9bc4",
    "#4f8cff", "#7aa6ff", "#ffffff", "#111a33", "#0a1020", "#1b2647",
    "qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #4f8cff, stop:1 #9d6bff)",
)

PALETTES: dict[str, Palette] = {
    p.name: p for p in (DARK, LIGHT, CUSTOM, AQUA, GRAPHITE, SONOMA, BIGSUR)
}

#: Темы, которые можно выбрать плиткой. Порядок важен для интерфейса.
BUILTIN_THEMES: tuple[str, ...] = ("aqua", "graphite", "sonoma", "bigsur")
BASE_THEMES: tuple[str, ...] = ("system", "light", "dark", "custom")


def _hc_enabled() -> bool:
    """Включён ли режим высокой контрастности Windows.

    В этом режиме Windows подменяет системные цвета своей схемой, а
    ``AppsUseLightTheme`` продолжает показывать обычную тему приложений —
    из-за этого «системная» тема могла оказаться светлой на чёрной схеме.
    """
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\Accessibility\HighContrast",
        ) as key:
            flags, _ = winreg.QueryValueEx(key, "Flags")
        return bool(int(flags) & 0x1)
    except Exception:
        return False


def _hc_scheme() -> str | None:
    """Схема высокой контрастности по цвету системного окна."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Control Panel\Colors",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "Window")
        parts = [int(p) for p in str(value).split()[:3]]
        if len(parts) != 3:
            return None
        r, g, b = parts
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return "dark" if luminance < 128 else "light"
    except Exception:
        return None


def _apps_light() -> bool | None:
    """Значение AppsUseLightTheme из реестра (None, если недоступно)."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return bool(int(value))
    except Exception:
        return None


def _qt_color_scheme() -> str | None:
    try:  # Qt 6.5+: реальная схема оформления
        from PySide6.QtGui import QGuiApplication
        hints = QGuiApplication.styleHints()
        name = getattr(hints.colorScheme(), "name", "").lower()
        if "light" in name:
            return "light"
        if "dark" in name:
            return "dark"
    except Exception:
        pass
    return None


def _palette_scheme() -> str | None:
    """Запасной вариант: светлый/тёмный цвет окна в текущей палитре Qt."""
    try:
        from PySide6.QtGui import QPalette
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return None
        color = app.palette().color(QPalette.ColorRole.Window)
        return "dark" if color.lightness() < 128 else "light"
    except Exception:
        return None


def detect_system_scheme() -> str:
    """Возвращает «light» или «dark» с учётом высокой контрастности.

    Порядок: схема высокой контрастности → AppsUseLightTheme → схема Qt →
    фактическая палитра → тёмная по умолчанию.
    """
    if _hc_enabled():
        hc = _hc_scheme()
        if hc:
            return hc
    light = _apps_light()
    if light is not None:
        return "light" if light else "dark"
    return _qt_color_scheme() or _palette_scheme() or "dark"


def resolve(theme: str) -> str:
    """Имя темы → конкретная палитра (для system подставляется текущая схема)."""
    if theme == "system":
        return detect_system_scheme()
    return theme if theme in PALETTES else "dark"


def palette(theme: str) -> Palette:
    return PALETTES.get(resolve(theme), DARK)


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return hex_color
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha:g})"


def _accent(p: Palette) -> str:
    return p.gradient or p.accent


def _accent_hover(p: Palette) -> str:
    return p.accent_hover


def build_qss(theme: str, background: str = "") -> str:
    """Собирает QSS для темы. ``background`` — путь к картинке своей темы."""
    p = palette(theme)
    translucent = bool(background)
    bg = _rgba(p.bg, 0.88) if translucent else p.bg
    panel = _rgba(p.panel, 0.86) if translucent else p.panel
    card = _rgba(p.panel, 0.82) if translucent else p.panel
    field = _rgba(p.input_bg, 0.84) if translucent else p.input_bg
    code = _rgba(p.code_bg, 0.86) if translucent else p.code_bg
    border = _rgba(p.border, 0.75) if translucent else p.border
    hover = _rgba(p.hover, 0.9) if translucent else p.hover

    bg_image = ""
    if background:
        safe = background.replace("\\", "/").replace('"', '\\"')
        bg_image = (
            f'background-image: url("{safe}"); '
            "background-position: center; background-repeat: no-repeat;"
        )

    return f"""
QWidget {{ background-color: {bg}; color: {p.text}; font-family: 'Segoe UI'; font-size: 13px; }}
QMainWindow {{ background-color: {p.bg}; {bg_image} }}
QScrollArea {{ background: transparent; border: none; }}
#sidebar {{ background-color: {panel}; border-right: 1px solid {border}; }}
#sidebar QLabel#logo {{ color: {p.accent}; font-size: 22px; font-weight: 800; padding: 16px 12px 4px 12px; }}
#sidebar QLabel#sub {{ color: {p.muted}; font-size: 11px; padding: 0 12px 12px 12px; }}
#navList {{ background: transparent; border: none; outline: none; }}
#navList::item {{ padding: 12px 16px; margin: 2px 8px; border-radius: 8px; color: {p.muted}; }}
#navList::item:hover {{ background: {hover}; color: {p.text}; }}
#navList::item:selected {{ background: {_accent(p)}; color: {p.accent_text}; font-weight: 600; }}
QPushButton {{ background: {_accent(p)}; color: {p.accent_text}; border: none; border-radius: 8px; padding: 10px 16px; font-weight: 600; }}
QPushButton:hover {{ background: {_accent_hover(p)}; }}
QPushButton:disabled {{ background: {border}; color: {p.muted}; }}
QPushButton#ghost {{ background: transparent; border: 1px solid {border}; color: {p.text}; }}
QPushButton#ghost:hover {{ background: {hover}; }}
#card {{ background: {card}; border: 1px solid {border}; border-radius: 12px; padding: 14px; }}
QLabel#h1 {{ font-size: 20px; font-weight: 700; color: {p.text}; }}
QLabel#h2 {{ font-size: 14px; font-weight: 600; color: {p.text}; }}
QLabel#val {{ font-size: 13px; color: {p.text}; }}
QLabel#muted {{ color: {p.muted}; font-size: 12px; }}
QLabel#kv {{ color: {p.muted}; font-size: 12px; }}
QGroupBox {{ border: 1px solid {border}; border-radius: 10px; margin-top: 14px; padding: 12px 10px; color: {p.muted}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; }}
QProgressBar {{ background: {border}; border: none; border-radius: 6px; height: 8px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {_accent(p)}; border-radius: 6px; }}
QTextEdit, QPlainTextEdit {{ background: {code}; border: 1px solid {border}; border-radius: 8px; color: {p.text}; font-family: 'Cascadia Code','Consolas'; font-size: 12px; }}
QListWidget {{ background: {card}; border: 1px solid {border}; border-radius: 8px; }}
QListWidget::item {{ padding: 8px; }}
QListWidget#issueList::item {{ border-bottom: 1px solid {border}; padding: 6px; }}
QComboBox {{ background: {field}; border: 1px solid {border}; border-radius: 8px; padding: 6px 10px; }}
QComboBox QAbstractItemView {{ background: {field}; selection-background-color: {p.accent}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 2px solid {border}; background: {field}; }}
QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; }}
QSplitter::handle {{ background: {border}; }}
QLineEdit {{ background: {field}; border: 1px solid {border}; border-radius: 8px; padding: 6px 10px; }}
QToolTip {{ background-color: {p.panel}; color: {p.text}; border: 1px solid {border}; }}
"""


def get_qss(theme: str, background: str = "") -> str:
    """QSS выбранной темы; для ``custom`` можно передать картинку фона."""
    if theme not in ("custom",) and theme not in PALETTES and theme != "system":
        theme = "dark"
    return build_qss(theme, background if theme == "custom" else "")


def preview(theme: str) -> tuple[str, str]:
    """Два цвета для плитки-превью: верх и низ «экрана монитора»."""
    p = palette(theme)
    return p.panel, p.accent


# Совместимость со старым API: тема → готовый QSS.
THEMES: dict[str, str] = {
    name: build_qss(name) for name in ("dark", "light", "system", "custom",
                                       *BUILTIN_THEMES)
}
