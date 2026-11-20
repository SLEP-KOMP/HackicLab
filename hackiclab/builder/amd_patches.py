"""AMD_Vanilla kernel patches для Ryzen.

OpenCore на AMD без этих патчей не стартует: ядро macOS рассчитано на Intel
CPUID/MSR. Патчи берутся из официального репозитория AMD-OSX/AMD_Vanilla
(patches.plist) и кэшируются локально.
"""

from __future__ import annotations

import plistlib
import time
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
        return extend_for_tahoe(patches)
    except Exception as e:
        _log(f"AMD patches: ошибка ({e})")
        return []


#: Варианты патчей для ядра 26.x (macOS Tahoe). В AMD_Vanilla диапазоны
#: заканчиваются на 25.99.99, поэтому на Tahoe эти патчи молча не применяются
#: и Ryzen не стартует. Байты взяты из config.plist, который собирает
#: OpCore Simplify (BSD-3-Clause) для macOS 26.
_TAHOE_10BIT_COMMENT = "Disable 10 bit tags"
_TAHOE_10BIT_26 = {
    "Comment": "CaseySJ | probeBusGated | Disable 10 bit tags | 26.0+",
    "MinKernel": "25.0.0",
    "MaxKernel": "25.99.99",
    "Find": b"\xe0\x11s@",
    "Replace": b"\x00\x00\x02\x00",
    "Mask": b"\xf0\xff\xff\xf0",
    "ReplaceMask": b"\x00\x00\x0f\x00",
}
_TAHOE_PANIC_COMMENT = "non-monotonic time panic"
_TAHOE_PANIC_26 = {
    "Comment": "laobamac | thread_invoke, thread_dispatch | "
               "Remove non-monotonic time panic | 26.4+",
    "MinKernel": "25.4.0",
    "MaxKernel": "25.99.99",
    "Find": b"H\x00\x00\x90\x04\x00\x00\x0f\x00\x00\x00\x00\x00",
    "Replace": b"\x00\x00\x00\x00\x00\x00\x00f\x90f\x90f\x90",
    "Mask": b"H\x00\x00\xf0\xff\xff\xff\xff\x00\x00\x00\x00\x00",
    "ReplaceMask": b"\x00\x00\x00\x00\x00\x00\x00\xff\xff\xff\xff\xff\xff",
}


def extend_for_tahoe(patches: list) -> list:
    """Дополняет набор AMD_Vanilla вариантами под ядро 26.x.

    Патчи, у которых MaxKernel = 25.99.99, на Tahoe не применяются: адреса
    и байты ядра там другие. Для двух таких патчей есть проверенные байты —
    обрезаем прежний диапазон и добавляем вариант для 26.x.
    """
    if not patches:
        return patches
    extended: list = []
    for patch in patches:
        comment = str(patch.get("Comment", ""))
        if (patch.get("MaxKernel") == "25.99.99"
                and _TAHOE_10BIT_COMMENT in comment):
            trimmed = dict(patch)
            trimmed["MaxKernel"] = "24.99.99"
            extended.append(trimmed)
            extra = {**patch, **_TAHOE_10BIT_26}
            extended.append(extra)
            continue
        if (patch.get("MaxKernel") == "25.99.99"
                and _TAHOE_PANIC_COMMENT in comment
                and "thread_invoke, thread_dispatch" in comment):
            trimmed = dict(patch)
            trimmed["MaxKernel"] = "25.3.99"
            extended.append(trimmed)
            extra = {**patch, **_TAHOE_PANIC_26}
            extended.append(extra)
            continue
        extended.append(patch)
    return extended
