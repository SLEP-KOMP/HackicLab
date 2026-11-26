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


def _configured_cache_root() -> str:
    """Путь к сетевой папке кэша: переменная окружения, затем настройка."""
    env = os.environ.get("HACKICLAB_CACHE", "").strip()
    if env:
        return env
    try:
        from .. import uistate

        return str(uistate.get("cache_root", "") or "").strip()
    except Exception:
        return ""


def is_network_cache() -> bool:
    return bool(_configured_cache_root()) and cache_dir() == Path(_configured_cache_root())


def check_cache_path(path: str) -> tuple[bool, str]:
    """Проверяет, что в папку можно писать (для сетевого пути — доступность шары)."""
    raw = (path or "").strip()
    if not raw:
        return False, "empty"
    try:
        folder = Path(raw)
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".hackiclab-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True, str(folder)
    except OSError as exc:
        return False, str(exc)


def cache_dir() -> Path:
    override = _configured_cache_root()
    if override:
        try:
            folder = Path(override)
            folder.mkdir(parents=True, exist_ok=True)
            return folder
        except OSError:
            # Шара недоступна — молча работаем на локальном кэше, чтобы сборка
            # не падала из-за выключенного ПК или пропавшей сети.
            pass
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
