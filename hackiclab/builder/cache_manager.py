"""Управление кэшем приложения (загруженные компоненты, профили)."""

from __future__ import annotations

import os
from pathlib import Path


def app_home() -> Path:
    """Домашняя папка приложения (~/.hackiclab)."""
    home = Path(os.path.expanduser("~")) / ".hackiclab"
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
