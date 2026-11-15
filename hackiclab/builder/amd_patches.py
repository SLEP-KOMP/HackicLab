"""AMD_Vanilla kernel patches для Ryzen.

OpenCore на AMD без этих патчей не стартует: ядро macOS рассчитано на Intel
CPUID/MSR. Патчи берутся из официального репозитория AMD-OSX/AMD_Vanilla
(patches.plist) и кэшируются локально.
"""

from __future__ import annotations

import plistlib
from pathlib import Path

_URL = "https://raw.githubusercontent.com/AMD-OSX/AMD_Vanilla/master/patches.plist"


def fetch_amd_patches(log=None) -> list:
    """Возвращает список Kernel -> Patch (или [] при ошибке)."""
    from .cache_manager import cache_dir
    from .fetcher import download_bytes

    def _log(msg: str):
        if log:
            log(msg)

    cache: Path = cache_dir() / "amd_patches.plist"
    try:
        if not cache.exists() or cache.stat().st_size < 1024:
            _log("AMD patches: скачиваю AMD_Vanilla…")
            data = download_bytes(
                _URL, headers={"User-Agent": "HackicLab"}, timeout=60)
            if not data:
                _log("AMD patches: пустой ответ GitHub")
                return []
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(data)
        with open(cache, "rb") as f:
            plist = plistlib.load(f)
        patches = list((plist.get("Kernel") or {}).get("Patch") or [])
        if not patches:
            _log("AMD patches: в patches.plist нет Kernel/Patch")
        return patches
    except Exception as e:
        _log(f"AMD patches: ошибка ({e})")
        return []
