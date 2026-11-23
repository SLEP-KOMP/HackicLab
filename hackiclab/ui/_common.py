"""Общие константы и модульные хелперы интерфейса.

Выделено из ``main_window.py``: виджеты-фабрики подписей, утилиты для
релиз-заметок и диагностики i18n, константы раскладки и одноэкземплярности.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PySide6.QtCore import QTranslator
from PySide6.QtWidgets import QApplication, QLabel

from ..i18n import tr

#: Имя локального сервера для проверки «программа уже запущена».
SINGLE_INSTANCE = "hackiclab-single-instance"

#: Ширина центральной колонки контента — как у «Параметров» Windows.
COLUMN_MAX_WIDTH = 1280

#: Перевод стандартных кнопок Qt (Yes/No, OK) — живёт весь запуск.
_QT_TRANSLATOR = None


def install_qt_translator(lang: str) -> None:
    """Подключает qtbase_<lang>.qm, чтобы кнопки диалогов были на языке UI.

    Файлы переводов лежат в PySide6/translations; в собранном EXE путь
    подсказывает ``sys._MEIPASS``. Если файла нет, диалоги останутся на
    английском, поэтому приложение дополнительно задаёт подписи само.
    """
    global _QT_TRANSLATOR
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return
    if _QT_TRANSLATOR is not None:
        app.removeTranslator(_QT_TRANSLATOR)
        _QT_TRANSLATOR = None
    from PySide6.QtCore import QLibraryInfo

    folders = [Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))]
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        folders.append(Path(bundled) / "PySide6" / "translations")
    for folder in folders:
        qm = folder / f"qtbase_{lang}.qm"
        if not qm.exists():
            continue
        translator = QTranslator()
        if translator.load(str(qm)):
            app.installTranslator(translator)
            _QT_TRANSLATOR = translator
            return


#: Ссылка на сервер живёт весь запуск — иначе Qt соберёт его как мусор.
_SINGLE_SERVER = None


def _h1(parent, text):
    l = QLabel(text, parent); l.setObjectName("h1"); return l
def _h2(parent, text):
    l = QLabel(text, parent); l.setObjectName("h2"); return l
def _muted(parent, text):
    l = QLabel(text, parent); l.setObjectName("muted"); return l
def _kv(parent, text):
    l = QLabel(text, parent); l.setObjectName("kv"); return l
def _val(parent, text):
    l = QLabel(text, parent); l.setObjectName("val"); return l


def _release_notes_text(text: str, limit: int = 4000) -> str:
    """Превращает markdown релиза в читаемый текст для панели «Обновления».

    В релизе описание хранится разметкой, и в QPlainTextEdit она выглядела
    как мусор: «### Установка», «> ⚠️», обратные кавычки и звёздочки.
    """
    result: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            result.append("")
            continue
        stripped = re.sub(r"^#{1,6}\s*", "", stripped)
        stripped = re.sub(r"^[-*+]\s+", "• ", stripped)
        stripped = re.sub(r"^\d+[.)]\s+", lambda m: f"{m.group(0).strip()} ", stripped)
        stripped = re.sub(r"^>\s*", "", stripped)
        stripped = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", stripped)
        stripped = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)
        stripped = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
        stripped = re.sub(r"__(.+?)__", r"\1", stripped)
        stripped = re.sub(r"`([^`]+)`", r"\1", stripped)
        stripped = re.sub(r"^\s*[—–-]{3,}\s*$", "", stripped)
        result.append(stripped.strip())
    cleaned = "\n".join(result)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned[:limit]


def _has_cyrillic(text: str) -> bool:
    return any("\u0400" <= ch <= "\u04FF" for ch in (text or ""))


def _issue_title(issue) -> str:
    """EN-заголовок проблемы с сохранением имени файла/кекста после двоеточия."""
    title = tr.issue(issue.code, "title", issue.title)
    if title != issue.title and ":" in issue.title:
        tail = issue.title.split(":", 1)[1].strip()
        if tail and not _has_cyrillic(tail):
            title = f"{title}: {tail}"
    return title


def _efi_root_for(folder) -> Path:
    """Корень сборки: выбранная папка, а если выбрана сама папка EFI — её родитель."""
    root = Path(str(folder))
    if root.name.upper() == "EFI":
        root = root.parent
    return root


def _macos_newer(a: str, b: str) -> bool:
    """Версия a новее b? (по имени macOS). Для подсказки о несовместимости."""
    order = ["High Sierra", "Mojave", "Catalina", "Big Sur", "Monterey",
             "Ventura", "Sonoma", "Sequoia", "Tahoe"]

    def idx(x):
        for i, n in enumerate(order):
            if n.lower() in (x or "").lower():
                return i
        return -1
    ia, ib = idx(a), idx(b)
    if ia == -1 or ib == -1:
        return False
    return ia > ib
