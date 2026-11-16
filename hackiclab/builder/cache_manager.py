"""Управление кэшем приложения (загруженные компоненты, профили)."""

from __future__ import annotations

import os
from pathlib import Path


def user_home() -> Path:
    """Домашний каталог пользователя с запасными вариантами.

    В некоторых окружениях (запуск из службы, урезанное окружение) переменные
    HOME/USERPROFILE отсутствуют, и ``Path.home()`` падает с RuntimeError.
    """
    for var in ("USERPROFILE", "HOME", "HOMEDRIVE"):
        value = os.environ.get(var)
        if value and (var != "HOMEDRIVE" or os.environ.get("HOMEPATH")):
            base = value if var != "HOMEDRIVE" else value + os.environ.get("HOMEPATH", "")
            return Path(base)
    try:
        return Path.home()
    except RuntimeError:
        import tempfile

        return Path(tempfile.gettempdir())


def app_home() -> Path:
    """Домашняя папка приложения (~/.hackiclab)."""
    home = user_home() / ".hackiclab"
    try:
        home.mkdir(parents=True, exist_ok=True)
    except OSError:
        import tempfile

        home = Path(tempfile.gettempdir()) / ".hackiclab"
        home.mkdir(parents=True, exist_ok=True)
    return home


def cache_dir() -> Path:
    d = app_home() / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def profiles_dir() -> Path:
    d = app_home() / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def builds_dir() -> Path:
    d = app_home() / "builds"
    d.mkdir(parents=True, exist_ok=True)
    return d
