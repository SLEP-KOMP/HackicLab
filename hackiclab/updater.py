"""Проверка и установка обновлений через GitHub Releases.

Схема простая и без сервера: HackicLab читает последний релиз репозитория,
сравнивает тег с собственной версией и, если доступна более новая сборка,
предлагает скачать `HackicLab.exe` из вложений.

Самообновление возможно только у собранного EXE: подменять работающий файл
нельзя, но его можно переименовать. Текущий EXE уводится в «<имя>.old», на его
место копируется новая сборка, после чего приложение перезапускается, а старая
копия удаляется при следующем старте. Отдельный cmd-скрипт и консольное окно
при этом не нужны.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
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
    asset_size: int | None = 0
    asset_digest: str = ""   # sha256 вложения по данным GitHub
    is_rebuild: bool = False  # та же версия, но другое содержимое сборки

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


def _find_asset(release: dict) -> tuple[str, int, str]:
    for asset in release.get("assets") or []:
        if (asset.get("name") or "").lower() == ASSET_NAME.lower():
            return (
                str(asset.get("browser_download_url") or ""),
                int(asset.get("size") or 0),
                str(asset.get("digest") or ""),
            )
    return "", 0, ""


def current_binary_digest() -> str:
    """sha256 запущенного EXE. Для запуска из исходников — пустая строка."""
    if not getattr(sys, "frozen", False):
        return ""
    try:
        digest = hashlib.sha256()
        with open(sys.executable, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return "sha256:" + digest.hexdigest()
    except Exception:
        return ""


def parse_release(release: dict, current_digest: str = "") -> Optional[UpdateInfo]:
    """Разбирает ответ GitHub API.

    Возвращает None, если версия не новее текущей. Исключение — пересборка:
    версия совпадает, но sha256 вложения отличается от запущенного EXE.
    Так обновления видны, даже когда релиз перезаливают без смены номера.
    """
    tag = str(release.get("tag_name") or "").strip()
    if not tag:
        return None
    version = tag.lstrip("vV")
    url, size, digest = _find_asset(release)
    newer = is_newer(version)
    rebuild = False
    if not newer:
        same_version = parse_version(version) == parse_version(__version__)
        if not (same_version and current_digest and digest):
            return None
        if digest == current_digest:
            return None
        rebuild = True
    return UpdateInfo(
        version=version,
        tag=tag,
        notes=str(release.get("body") or ""),
        page_url=str(release.get("html_url") or RELEASES_PAGE),
        asset_url=url,
        asset_size=size,
        asset_digest=digest,
        is_rebuild=rebuild,
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
    return parse_release(release, current_binary_digest())


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


OLD_SUFFIX = ".old"


def apply_update(new_exe: Path) -> bool:
    """Ставит скачанный EXE на место текущего.

    Запущенный файл нельзя перезаписать, но можно переименовать: текущий EXE
    уводится в «<имя>.old», на его место копируется новая сборка. Старая копия
    удаляется при следующем запуске (см. cleanup_old_binaries).

    Возвращает True, если файл подменён: вызывающему остаётся перезапустить
    приложение.
    """
    if not can_self_update():
        return False
    target = Path(sys.executable).resolve()
    source = Path(new_exe).resolve()
    if not source.is_file():
        return False
    backup = target.with_name(target.name + OLD_SUFFIX)
    try:
        if backup.exists():
            backup.unlink()
        os.replace(target, backup)
    except OSError:
        return False
    try:
        shutil.copy2(source, target)
    except OSError:
        try:
            os.replace(backup, target)
        except OSError:
            pass
        return False
    return True


def relaunch_self() -> bool:
    """Запускает обновлённый EXE отдельным процессом."""
    exe = str(Path(sys.executable).resolve())
    flags = 0
    if hasattr(subprocess, "DETACHED_PROCESS"):
        flags = subprocess.DETACHED_PROCESS
    try:
        subprocess.Popen([exe], close_fds=True, creationflags=flags)
    except OSError:
        return False
    return True


def cleanup_old_binaries() -> None:
    """Удаляет «<имя>.old», оставшийся от прошлого обновления."""
    if not getattr(sys, "frozen", False):
        return
    exe = Path(sys.executable)
    try:
        (exe.with_name(exe.name + OLD_SUFFIX)).unlink()
    except OSError:
        pass


def open_release_page(url: str = RELEASES_PAGE) -> bool:
    try:
        return bool(webbrowser.open(url))
    except Exception:
        return False
