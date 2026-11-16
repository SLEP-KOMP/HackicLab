"""Темы оформления HackicLab.

Темы строятся из палитр, а не из независимых QSS-простыней: так проще
добавлять новые оформления и подмешивать пользовательский фон.

- ``system`` — следует теме Windows (реестр AppsUseLightTheme);
- ``light`` / ``dark`` — базовые;
- ``custom`` — фирменная тема с возможностью подставить своё изображение;
- ``aqua``, ``graphite``, ``sonoma``, ``bigsur`` — встроенные оформления
  в духе macOS: свои поверхности, градиенты и акценты, без ассетов Apple.
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
    surface: str = ""           # фон карточек
    window: str = ""            # фон рабочей области (можно градиент)
    ok: str = "#16a34a"
    warn: str = "#d97706"
    danger: str = "#dc2626"


DARK = Palette(
    "dark", "#14151f", "#0f1018", "#2b2d3d", "#e6e8f2", "#8d92a8",
    "#8b5cf6", "#a78bfa", "#ffffff", "#12131c", "#0d0e15", "#232537",
    "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #7c5cff, stop:1 #b06cff)",
    surface="#1b1c29",
    window="qlineargradient(x1:0,y1:0,x2:0.6,y2:1, stop:0 #161724, stop:1 #101119)",
    ok="#4ade80", warn="#fbbf24", danger="#fb7185",
)

LIGHT = Palette(
    "light", "#f2f4f8", "#ffffff", "#dde1e9", "#14161c", "#62687a",
    "#6d4bff", "#8568ff", "#ffffff", "#ffffff", "#f7f8fb", "#e6e9f0",
    "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #6d4bff, stop:1 #9a6bff)",
    surface="#ffffff",
    window="qlineargradient(x1:0,y1:0,x2:0.6,y2:1, stop:0 #f7f9fc, stop:1 #eef1f7)",
    ok="#15803d", warn="#b45309", danger="#be123c",
)

CUSTOM = Palette(
    "custom", "#0f172a", "#0b1120", "#1e293b", "#e2e8f0", "#7c8aa5",
    "#06b6d4", "#22d3ee", "#ffffff", "#0b1120", "#0b1120", "#1e293b",
    "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #06b6d4, stop:1 #8b5cf6)",
    surface="#111c33",
    window="qlineargradient(x1:0,y1:0,x2:0.7,y2:1, stop:0 #0d1628, stop:1 #0a101f)",
    ok="#34d399", warn="#fbbf24", danger="#fb7185",
)

AQUA = Palette(
    "aqua", "#eaf2fb", "#ffffff", "#cbdcee", "#0d2238", "#5d7490",
    "#0a84ff", "#3d9bff", "#ffffff", "#ffffff", "#f5f9fd", "#dbe8f4",
    "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0a84ff, stop:1 #40c8e0)",
    surface="#ffffff",
    window="qlineargradient(x1:0,y1:0,x2:0.6,y2:1, stop:0 #f2f8ff, stop:1 #e3eefb)",
    ok="#0f766e", warn="#b45309", danger="#be123c",
)

GRAPHITE = Palette(
    "graphite", "#16171b", "#0f1014", "#34373f", "#edeef2", "#9a9ea9",
    "#b9becb", "#d3d7df", "#101114", "#1c1e23", "#121317", "#24262c",
    "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #8b909c, stop:1 #c9ced8)",
    surface="#202228",
    window="qlineargradient(x1:0,y1:0,x2:0.6,y2:1, stop:0 #191a1f, stop:1 #121317)",
    ok="#5eead4", warn="#fcd34d", danger="#fda4af",
)

SONOMA = Palette(
    "sonoma", "#170f1d", "#1f1426", "#46304f", "#f8eef4", "#b9a2b4",
    "#ff6fae", "#ff8fc2", "#2b0f1c", "#2a1a33", "#180f1d", "#31203a",
    "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #ff6fae, stop:1 #ffa14a)",
    surface="#2a1a33",
    window="qlineargradient(x1:0,y1:0,x2:0.7,y2:1, stop:0 #1d1224, stop:1 #241430)",
    ok="#86efac", warn="#fde68a", danger="#fda4af",
)

BIGSUR = Palette(
    "bigsur", "#071022", "#0a1529", "#24355e", "#e8eefc", "#93a4c9",
    "#4f8cff", "#7aa6ff", "#ffffff", "#122043", "#0a1020", "#1b2647",
    "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #4f8cff, stop:1 #9d6bff)",
    surface="#122043",
    window="qlineargradient(x1:0,y1:0,x2:0.6,y2:1, stop:0 #0a1428, stop:1 #0b1731)",
    ok="#7dd3fc", warn="#fcd34d", danger="#fda4af",
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


def tone(theme: str, level: str) -> tuple[str, str]:
    """Цвет текста и подложки для статуса: (текст, плашка)."""
    p = palette(theme)
    color = {"ok": p.ok, "warn": p.warn, "err": p.danger}.get(level, p.muted)
    return color, _rgba(color, 0.16)


def build_qss(theme: str, background: str = "") -> str:
    """Собирает QSS для темы. ``background`` — путь к картинке своей темы."""
    p = palette(theme)
    translucent = bool(background)
    bg = _rgba(p.bg, 0.88) if translucent else p.bg
    panel = _rgba(p.panel, 0.90) if translucent else p.panel
    surface = _rgba(p.surface or p.panel, 0.84) if translucent else (p.surface or p.panel)
    field = _rgba(p.input_bg, 0.86) if translucent else p.input_bg
    code = _rgba(p.code_bg, 0.90) if translucent else p.code_bg
    border = _rgba(p.border, 0.80) if translucent else p.border
    hover = _rgba(p.hover, 0.90) if translucent else p.hover
    soft = _rgba(p.accent, 0.14)
    soft_hover = _rgba(p.accent, 0.22)
    window = p.window or p.bg

    bg_image = ""
    if background:
        safe = background.replace("\\", "/").replace('"', '\\"')
        bg_image = (
            f'background-image: url("{safe}"); '
            "background-position: center; background-repeat: no-repeat;"
        )

    return f"""
QWidget {{
    background-color: transparent;
    color: {p.text};
    font-family: 'Segoe UI Variable Text', 'Segoe UI';
    font-size: 13px;
}}
QMainWindow, QDialog {{ background: {bg}; {bg_image} }}
#pageRoot {{ background: {window}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
#sidebar {{ background-color: {panel}; border-right: 1px solid {border}; }}
#sidebar QLabel#logo {{
    color: {p.text}; font-size: 21px; font-weight: 800;
    letter-spacing: 0.2px; padding: 18px 14px 2px 14px;
}}
#sidebar QLabel#sub {{ color: {p.muted}; font-size: 11px; padding: 0 14px 14px 14px; }}
#navList {{ background: transparent; border: none; outline: none; }}
#navList::item {{
    padding: 11px 14px; margin: 2px 10px; border-radius: 9px;
    color: {p.muted}; font-size: 13px;
}}
#navList::item:hover {{ background: {hover}; color: {p.text}; }}
#navList::item:selected {{
    background: {soft}; color: {p.text}; font-weight: 600;
    border-left: 3px solid {p.accent};
}}
#navList::item:focus {{ outline: none; }}
QPushButton {{
    background: {_accent(p)}; color: {p.accent_text}; border: none;
    border-radius: 9px; padding: 9px 18px; font-weight: 600;
}}
QPushButton:hover {{ background: {_accent_hover(p)}; }}
QPushButton:pressed {{ background: {p.accent}; }}
QPushButton:disabled {{ background: {border}; color: {p.muted}; }}
QPushButton#ghost {{
    background: {surface}; border: 1px solid {border}; color: {p.text};
    padding: 8px 14px; font-weight: 500;
}}
QPushButton#ghost:hover {{ background: {hover}; border-color: {p.accent}; }}
QPushButton#ghost:disabled {{ background: transparent; color: {p.muted}; }}
QPushButton#chip {{
    background: {p.input_bg}; border: 1px solid {border}; color: {p.text};
    border-radius: 15px; padding: 6px 16px; font-size: 12px; font-weight: 600;
}}
QPushButton#chip:hover {{ border-color: {p.accent}; color: {p.accent}; }}
QFrame#logoPlate {{
    background: #ffffff; border: 1px solid #d8dbe6; border-radius: 8px;
}}
QPushButton#chip:checked {{
    border-color: {p.accent}; color: {p.accent};
    background: {_rgba(p.accent, 0.14)};
}}
#card {{
    background: {surface}; border: 1px solid {border};
    border-radius: 14px;
}}
QLabel#h1 {{ font-size: 22px; font-weight: 700; color: {p.text}; }}
QLabel#h2 {{ font-size: 13px; font-weight: 700; color: {p.text}; letter-spacing: 0.2px; }}
QLabel#val {{ font-size: 13px; color: {p.text}; }}
QLabel#muted, QLabel#kv {{ color: {p.muted}; font-size: 12px; }}
QLabel#ok {{ color: {p.ok}; font-size: 12px; font-weight: 600; }}
QLabel#warn {{ color: {p.warn}; font-size: 12px; font-weight: 600; }}
QLabel#err {{ color: {p.danger}; font-size: 12px; font-weight: 600; }}
QLabel#badge {{
    border-radius: 9px; padding: 2px 9px; font-size: 11px; font-weight: 600;
}}
QLabel#badge[tone="ok"] {{ color: {p.ok}; background: {_rgba(p.ok, 0.16)}; }}
QLabel#badge[tone="warn"] {{ color: {p.warn}; background: {_rgba(p.warn, 0.16)}; }}
QLabel#badge[tone="err"] {{ color: {p.danger}; background: {_rgba(p.danger, 0.16)}; }}
QLabel#badge[tone="muted"] {{ color: {p.muted}; background: {_rgba(p.muted, 0.16)}; }}
QGroupBox {{
    background: {surface}; border: 1px solid {border}; border-radius: 12px;
    margin-top: 16px; padding: 14px 12px 12px 12px;
    font-size: 12px; font-weight: 700; color: {p.muted};
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 6px; }}
QProgressBar {{
    background: {_rgba(p.border, 0.6)}; border: none; border-radius: 5px;
    height: 6px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {_accent(p)}; border-radius: 5px; }}
QPlainTextEdit, QTextEdit, QTextBrowser {{
    background: {code}; border: 1px solid {border}; border-radius: 10px;
    color: {p.text}; font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 12px; padding: 8px; selection-background-color: {p.accent};
}}
QListWidget {{
    background: {surface}; border: 1px solid {border}; border-radius: 10px;
    padding: 4px;
}}
QListWidget::item {{ padding: 8px 10px; border-radius: 8px; }}
QListWidget::item:hover {{ background: {hover}; }}
QListWidget::item:selected {{ background: {soft_hover}; color: {p.text}; }}
QListWidget#issueList::item {{ border-bottom: 1px solid {border}; padding: 6px 8px; }}
QComboBox {{
    background: {field}; border: 1px solid {border}; border-radius: 9px;
    padding: 7px 12px; min-height: 20px;
}}
QComboBox:hover {{ border-color: {p.accent}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {field}; color: {p.text}; border: 1px solid {border};
    selection-background-color: {soft_hover};
}}
QCheckBox {{ spacing: 9px; font-size: 13px; }}
QCheckBox::indicator {{
    width: 17px; height: 17px; border-radius: 5px;
    border: 1.5px solid {border}; background: {field};
}}
QCheckBox::indicator:hover {{ border-color: {p.accent}; }}
QCheckBox::indicator:checked {{ background: {_accent(p)}; border-color: {p.accent}; }}
QCheckBox::indicator:checked:hover {{ background: {_accent_hover(p)}; }}
QSplitter::handle {{ background: {border}; }}
QLineEdit {{
    background: {field}; border: 1px solid {border}; border-radius: 9px;
    padding: 8px 12px; selection-background-color: {p.accent};
}}
QLineEdit:focus {{ border-color: {p.accent}; }}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 4px 2px 4px 0;
}}
QScrollBar::handle:vertical {{
    background: {_rgba(p.muted, 0.45)}; border-radius: 5px; min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{ background: {_rgba(p.muted, 0.7)}; }}
QScrollBar:horizontal {{
    background: transparent; height: 10px; margin: 0 4px 2px 4px;
}}
QScrollBar::handle:horizontal {{
    background: {_rgba(p.muted, 0.45)}; border-radius: 5px; min-width: 32px;
}}
QScrollBar::handle:horizontal:hover {{ background: {_rgba(p.muted, 0.7)}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QStatusBar {{ background: {panel}; border-top: 1px solid {border}; color: {p.muted}; }}
QMenu {{
    background: {surface}; border: 1px solid {border}; border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{ padding: 7px 18px; border-radius: 7px; }}
QMenu::item:selected {{ background: {soft_hover}; }}
QToolTip {{
    background-color: {surface}; color: {p.text};
    border: 1px solid {border}; border-radius: 8px; padding: 6px 9px;
}}
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
