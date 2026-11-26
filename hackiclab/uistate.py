"""Сохранение состояния интерфейса HackicLab.

Файл ``~/.hackiclab/ui.json`` хранит выбранную тему, фон пользовательской темы
и отложенные обновления. Ошибки чтения/записи не должны ломать приложение,
поэтому они глушатся: при потере файла интерфейс просто вернётся к системной
теме.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .builder.cache_manager import app_home

#: Значения по умолчанию. Новая установка стартует с системной темы.
DEFAULTS: dict[str, Any] = {
    "theme": "system",
    "language": "",
    "background": "",
    "check_updates": True,
    "postponed_update": "",
    "skipped_version": "",
    "usb_source": "",
    "usb_mode": "full",
    "usb_recovery": True,
    "usb_map": True,
    "cache_root": "",
    "ui_schema": 2,
}

#: Версия схемы настроек: 2 — тема «Системная» и язык системы по умолчанию.
UI_SCHEMA = 2


def _file() -> Path:
    return app_home() / "ui.json"


def load() -> dict[str, Any]:
    """Читает состояние, подставляя значения по умолчанию."""
    data = dict(DEFAULTS)
    try:
        raw = json.loads(_file().read_text(encoding="utf-8"))
    except Exception:
        return data
    if isinstance(raw, dict):
        for key in DEFAULTS:
            if key in raw:
                data[key] = raw[key]
        if int(raw.get("ui_schema") or 0) < UI_SCHEMA:
            # Настройки от старой версии: тогда тема и язык были жёсткими,
            # поэтому один раз возвращаем их к системным значениям.
            data["theme"] = "system"
            data["language"] = ""
            data["ui_schema"] = UI_SCHEMA
            try:
                _file().write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
    return data


def save(**changes: Any) -> dict[str, Any]:
    """Сохраняет переданные поля и возвращает полное состояние."""
    data = load()
    for key, value in changes.items():
        if key in DEFAULTS:
            data[key] = value
    try:
        _file().write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return data


def get(key: str, default: Any = None) -> Any:
    return load().get(key, DEFAULTS.get(key, default))


def set_value(key: str, value: Any) -> None:
    save(**{key: value})
