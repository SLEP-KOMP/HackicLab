"""Диапазон macOS для профиля: минимум, потолок и рекомендация с причинами.

Считается из наших баз: потолок — oc_platforms.max_macos_for (поколение CPU),
минимум — требования железа (драйверы GPU/сети). Внешних таблиц не заводим.
"""

from __future__ import annotations

from dataclasses import dataclass

from .oc_platforms import MACOS_VERSIONS, OC_PLATFORMS, max_macos_for

#: «Sequoia» -> «15» для подписи в интерфейсе.
_VERSION_OF = {v["name"].removeprefix("macOS "): v["version"] for v in MACOS_VERSIONS}

#: От старых к новым: индекс = «новее».
ORDER: tuple[str, ...] = (
    "High Sierra", "Mojave", "Catalina", "Big Sur", "Monterey",
    "Ventura", "Sonoma", "Sequoia", "Tahoe", "Golden Gate",
)

#: Семейства Navi: драйвер появился только в 12.1.
_NAVI = ("731", "73b", "73d", "73e", "73f")


def _bare(name: str) -> str:
    return (name or "").replace("macOS ", "").strip()


def index_of(name: str) -> int:
    """Индекс версии в ORDER; -1 для неизвестной."""
    return ORDER.index(_bare(name)) if _bare(name) in ORDER else -1


def label(name: str) -> str:
    """Подпись версии с номером: «macOS Sequoia (15)»."""
    bare = _bare(name)
    version = _VERSION_OF.get(bare)
    return f"macOS {bare} ({version})" if version else bare


@dataclass(frozen=True)
class MacRange:
    lowest: str
    highest: str
    recommended: str
    reasons: tuple[tuple[str, str], ...] = ()


def _gpu_ids(profile) -> list[str]:
    out: list[str] = []
    for gpu in (getattr(profile, "igpu", None), getattr(profile, "dgpu", None)):
        if gpu is None:
            continue
        dev = (getattr(gpu, "device_id", "") or "").lower().replace("0x", "")
        if dev:
            out.append(dev)
    return out


def _floors(profile) -> list[tuple[str, str, str]]:
    """Минимальные версии macOS, которые требует железо: (версия, ru, en)."""
    out: list[tuple[str, str, str]] = []
    if any(dev.startswith(_NAVI) for dev in _gpu_ids(profile)):
        out.append((
            "Monterey",
            "AMD Navi: драйвер появился в macOS 12.1 — ниже не заведётся.",
            "AMD Navi: driver appeared in macOS 12.1, older systems will not work."))
    net = getattr(profile, "net", None)
    eth = " ".join(str(getattr(net, key, "") or "")
                   for key in ("eth_chipset", "eth_name")).lower()
    if "i211" in eth:
        out.append((
            "Monterey",
            "Intel I211 работает через AppleIGB — драйвер есть только с Monterey.",
            "Intel I211 needs AppleIGB, available from Monterey on."))
    return out


def mac_range(profile, preferred: str = "") -> MacRange:
    """Диапазон macOS для профиля и рекомендация под выбранную версию."""
    highest = _bare(max_macos_for(profile)) or "High Sierra"
    hi = index_of(highest)
    reasons: list[tuple[str, str]] = []

    lo = 0
    lowest = ORDER[0]
    for name, ru, en in _floors(profile):
        idx = index_of(name)
        if idx > lo:
            lo, lowest = idx, name
        reasons.append((ru, en))

    cpu = getattr(profile, "cpu", None)
    gen = int(getattr(cpu, "generation", 0) or 0) if cpu is not None else 0
    is_intel = (getattr(cpu, "vendor", "") or "").lower() == "intel" if cpu is not None else False
    # OC_PLATFORMS для AMD даёт «Core 2» (generation=0) — кодовая метка только для Intel.
    codename = OC_PLATFORMS.get(gen, "") if is_intel else ""
    if hi >= 0:
        suffix = f" ({codename})" if codename else ""
        reasons.append((f"Потолок по железу — {highest}{suffix}.",
                        f"Hardware ceiling — {highest}{suffix}."))

    if hi >= 0 and lo > hi:
        reasons.append((
            f"Минимум {lowest} выше потолка {highest}: нужен OCLP или другое железо.",
            f"Minimum {lowest} is above the ceiling {highest}: OCLP or other hardware needed."))
        return MacRange(lowest, highest, highest, tuple(reasons))

    want = _bare(preferred)
    wi = index_of(want)
    if wi < 0:
        recommended = highest
    elif wi > hi:
        recommended = highest
        reasons.append((f"{want} выше потолка — рекомендуем {highest}.",
                        f"{want} is above the ceiling — {highest} recommended."))
    elif wi < lo:
        recommended = lowest
        reasons.append((f"{want} ниже минимума — нужно {lowest} или новее.",
                        f"{want} is below the minimum — {lowest} or newer needed."))
    else:
        recommended = want

    return MacRange(lowest, highest, recommended, tuple(reasons))
