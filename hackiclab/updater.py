"""Проверка и установка обновлений через GitHub Releases.

Схема простая и без сервера: HackicLab читает последний релиз репозитория,
сравнивает тег с собственной версией и, если доступна более новая сборка,
предлагает скачать `HackicLab.exe` из вложений.

Самообновление возможно только у собранного EXE: подменять работающий файл
нельзя, поэтому скачанный образ кладётся рядом, а маленький cmd-скрипт ждёт
закрытия процесса, заменяет файл и запускает новую версию.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import __version__
from .builder.fetcher import download_bytes

REPO = "SLEP-KOMP/HackicLab"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
ASSET_NAME = "HackicLab.exe"


@dataclass(frozen=True)
class UpdateInfo:
    version: str          # "1.0.2"
    tag: str              # "v1.0.2"
    notes: str            # текст релиза
    page_url: str         # страница релиза
    asset_url: str        # прямая ссылка на EXE (может быть пустой)
    asset_size: int = 0

    @property
    def has_asset(self) -> bool:
        return bool(self.asset_url)


def parse_version(text: str) -> tuple[int, ...]:
    """«v1.0.2» / «1.0.2-beta» → (1, 0, 2). Нечисловые хвосты отбрасываются."""
    raw = (text or "").strip().lstrip("vV")
    parts: list[int] = []
    for chunk in raw.replace("-", ".").replace("_", ".").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts) or (0,)


def is_newer(latest: str, current: str = __version__) -> bool:
    """Сравнивает версии по числовым сегментам, дополняя нулями."""
    a, b = parse_version(latest), parse_version(current)
    width = max(len(a), len(b))
    a += (0,) * (width - len(a))
    b += (0,) * (width - len(b))
    return a > b


def _find_asset(release: dict) -> tuple[str, int]:
    for asset in release.get("assets") or []:
        if (asset.get("name") or "").lower() == ASSET_NAME.lower():
            return str(asset.get("browser_download_url") or ""), int(asset.get("size") or 0)
    return "", 0


def parse_release(release: dict) -> Optional[UpdateInfo]:
    """Разбирает ответ GitHub API; None — если версия не новее текущей."""
    tag = str(release.get("tag_name") or "").strip()
    if not tag:
        return None
    version = tag.lstrip("vV")
    if not is_newer(version):
        return None
    url, size = _find_asset(release)
    return UpdateInfo(
        version=version,
        tag=tag,
        notes=str(release.get("body") or ""),
        page_url=str(release.get("html_url") or RELEASES_PAGE),
        asset_url=url,
        asset_size=size,
    )


def check_for_update(timeout: int = 25) -> Optional[UpdateInfo]:
    """Возвращает описание нового релиза или None. Бросает исключение при сети."""
    data = download_bytes(
        LATEST_API,
        headers={
            "User-Agent": f"HackicLab/{__version__}",
            "Accept": "application/vnd.github+json",
        },
        timeout=timeout,
    )
    release = json.loads(data.decode("utf-8"))
    if not isinstance(release, dict):
        return None
    return parse_release(release)


def can_self_update() -> bool:
    """Подменять исполняемый файл можно только у собранного EXE."""
    return bool(getattr(sys, "frozen", False))


def update_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "HackicLab" / "update"


def download_update(info: UpdateInfo, progress: Optional[Callable[[int], None]] = None) -> Path:
    """Скачивает EXE обновления и возвращает путь к нему."""
    if not info.asset_url:
        raise RuntimeError("В релизе нет вложения HackicLab.exe")
    target_dir = update_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"HackicLab-{info.version}.exe"
    if target.exists() and info.asset_size and target.stat().st_size == info.asset_size:
        if progress:
            progress(100)
        return target

    data = download_bytes(
        info.asset_url,
        headers={"User-Agent": f"HackicLab/{__version__}"},
        timeout=180,
    )
    if info.asset_size and abs(len(data) - info.asset_size) > 1024:
        raise RuntimeError(
            f"Размер обновления не совпал: ожидалось {info.asset_size}, получено {len(data)}"
        )
    tmp = target.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.replace(target)
    if progress:
        progress(100)
    return target


def helper_script(target_exe: Path, new_exe: Path, pid: int) -> str:
    """Текст cmd-скрипта: ждёт закрытия процесса, подменяет EXE, запускает его."""
    return f"""@echo off
chcp 65001 >nul
:wait
tasklist /FI "PID eq {pid}" | find "{pid}" >nul
if not errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto wait
)
:replace
copy /y "{new_exe}" "{target_exe}" >nul 2>&1
if errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto replace
)
start "" "{target_exe}"
del "%~f0"
"""


def apply_update(new_exe: Path) -> bool:
    """Готовит подмену текущего EXE и запускает её отдельным процессом.

    Возвращает True, если скрипт запущен: вызывающему остаётся закрыть
    приложение, иначе файл останется занятым.
    """
    if not can_self_update():
        return False
    target = Path(sys.executable).resolve()
    script = Path(tempfile.gettempdir()) / f"hackiclab-update-{os.getpid()}.cmd"
    script.write_text(
        helper_script(target, Path(new_exe).resolve(), os.getpid()),
        encoding="utf-8",
    )
    flags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    subprocess.Popen(
        ["cmd", "/c", str(script)],
        creationflags=flags,
        close_fds=True,
    )
    return True


def open_release_page(url: str = RELEASES_PAGE) -> bool:
    try:
        return bool(webbrowser.open(url))
    except Exception:
        return False
