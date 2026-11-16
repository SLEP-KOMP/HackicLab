"""AMD_Vanilla kernel patches для Ryzen.

OpenCore на AMD без этих патчей не стартует: ядро macOS рассчитано на Intel
CPUID/MSR. Патчи берутся из официального репозитория AMD-OSX/AMD_Vanilla
(patches.plist) и кэшируются локально.
"""

from __future__ import annotations

import time
import plistlib
from pathlib import Path

_URL = "https://raw.githubusercontent.com/AMD-OSX/AMD_Vanilla/master/patches.plist"

#: Сколько дней кэш патчей считается свежим. AMD_Vanilla обновляется под новые
#: версии macOS, поэтому старый файл перекачивается.
CACHE_TTL_DAYS = 7


def _cache_is_fresh(cache: Path) -> bool:
    try:
        if not cache.exists() or cache.stat().st_size < 1024:
            return False
        age = time.time() - cache.stat().st_mtime
        return age < CACHE_TTL_DAYS * 86400
    except Exception:
        return False


def fetch_amd_patches(log=None) -> list:
    """Возвращает список Kernel -> Patch (или [] при ошибке)."""
    from .cache_manager import cache_dir
    from .fetcher import download_bytes

    def _log(msg: str):
        if log:
            log(msg)

    cache: Path = cache_dir() / "amd_patches.plist"
    try:
        if not _cache_is_fresh(cache):
            _log("AMD patches: скачиваю AMD_Vanilla…")
            try:
                data = download_bytes(
                    _URL, headers={"User-Agent": "HackicLab"}, timeout=60)
            except Exception as e:
                data = b""
                _log(f"AMD patches: сеть недоступна ({e})")
            if data:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_bytes(data)
            elif not cache.exists():
                _log("AMD patches: пустой ответ GitHub")
                return []
            else:
                _log("AMD patches: использую сохранённый кэш")
        with open(cache, "rb") as f:
            plist = plistlib.load(f)
        patches = list((plist.get("Kernel") or {}).get("Patch") or [])
        if not patches:
            _log("AMD patches: в patches.plist нет Kernel/Patch")
        return patches
    except Exception as e:
        _log(f"AMD patches: ошибка ({e})")
        return []
