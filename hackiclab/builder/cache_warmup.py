"""Наполнение кэша HackicLab: все кексты реестра и OpenCore.

Нужно, чтобы EFI собирался на другой машине (или при лимитах GitHub) из уже
скачанного: архивы лежат в `cache_dir()`, а сборщик берёт их оттуда.
"""

from __future__ import annotations

import tempfile
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

OPEN_CORE_REPO = "acidanthera/OpenCorePkg"


@dataclass
class WarmResult:
    ok: int = 0
    failed: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.ok + len(self.failed)


def kext_entries() -> list[tuple[str, object]]:
    """Кексты реестра, которые реально качаются с GitHub/прямой ссылки."""
    from ..knowledge.kexts import KEXT_DB

    return [(name, entry) for name, entry in sorted(KEXT_DB.items())
            if not getattr(entry, "internal", False)
            and (getattr(entry, "repo", "") or getattr(entry, "url", ""))]


def warm_cache(on_progress: Callable[[int, str], None] | None = None) -> WarmResult:
    """Скачивает все кексты и OpenCore в текущий кэш (в т.ч. сетевой)."""
    from .downloader import Downloader
    from .fetcher import GitHubFetcher, download_asset

    def report(percent: int, message: str) -> None:
        if on_progress is not None:
            on_progress(max(0, min(100, int(percent))), message)

    result = WarmResult()
    entries = kext_entries()
    total = max(1, len(entries) + 1)
    tmp = Path(tempfile.mkdtemp(prefix="hackiclab-warm-"))
    downloader = Downloader()
    try:
        for index, (name, entry) in enumerate(entries, 1):
            report(int(100 * index / total), f"{name}…")
            seen = len(downloader.log)
            try:
                path = downloader.download_kext(entry, tmp, "")
            except Exception as exc:  # сеть/архив — не рушим весь прогрев
                downloader.log.append(f"{name}: ошибка ({exc})")
                path = None
            result.log.extend(downloader.log[seen:])
            if path:
                result.ok += 1
            else:
                result.failed.append(name)
        report(int(100 * (total - 1) / total), "OpenCore…")
        release = GitHubFetcher.latest_release(OPEN_CORE_REPO) or {}
        if GitHubFetcher.find_asset(release, ".zip"):
            path = download_asset(release, ".zip", tmp, cache_name="opencore")
            if path:
                result.ok += 1
            else:
                result.failed.append("OpenCore")
        else:
            result.failed.append("OpenCore")
        report(100, "Готово")
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)
    return result
