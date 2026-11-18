"""Классификация железа: CPU-поколения, GPU-вендоры, кодеки.

Логика адаптирована из hackmate (hardware.py) и OpCore-Simplify,
переработана под чистые структуры и полный охват Intel 1-15 / AMD Zen.
"""

from __future__ import annotations

import re

# Intel iGPU device-ids -> (generation, codename, oc_platform)
INTEL_IGPU_GENERATIONS: dict[str, tuple[int, str, str]] = {
    "0106": (2, "Sandy Bridge", "Sandy Bridge"),
    "0166": (3, "Ivy Bridge", "Ivy Bridge"),
    "0416": (4, "Haswell", "Haswell"),
    "0a16": (4, "Haswell", "Haswell"),
    "0d26": (4, "Haswell", "Haswell"),
    "1616": (5, "Broadwell", "Broadwell"),
    "1626": (5, "Broadwell", "Broadwell"),
    "1916": (6, "Skylake", "Skylake"),
    "191b": (6, "Skylake", "Skylake"),
    "1926": (6, "Skylake", "Skylake"),
    "5916": (7, "Kaby Lake", "Kaby Lake"),
    "591b": (7, "Kaby Lake", "Kaby Lake"),
    "5926": (7, "Kaby Lake", "Kaby Lake"),
    "591c": (7, "Kaby Lake", "Kaby Lake"),
    "591e": (7, "Kaby Lake", "Kaby Lake"),
    "5917": (8, "Kaby Lake-R", "Kaby Lake-R"),
    "3e9b": (8, "Coffee Lake", "Coffee Lake"),
    "3e92": (8, "Coffee Lake", "Coffee Lake"),
    "3e91": (8, "Coffee Lake", "Coffee Lake"),
    "87c0": (8, "Kaby Lake-R", "Kaby Lake-R"),
    "3ea0": (8, "Whiskey Lake", "Whiskey Lake"),
    "3ea5": (8, "Whiskey Lake", "Whiskey Lake"),
    "3ea6": (8, "Whiskey Lake", "Whiskey Lake"),
    "3ea9": (8, "Whiskey Lake", "Whiskey Lake"),
    "3e98": (9, "Coffee Lake Refresh", "Coffee Lake"),
    "9b41": (10, "Comet Lake", "Comet Lake"),
    "9bc8": (10, "Comet Lake", "Comet Lake"),
    "9bc4": (10, "Comet Lake", "Comet Lake"),
    "9bca": (10, "Comet Lake", "Comet Lake"),
    "8a52": (10, "Ice Lake", "Ice Lake"),
    "8a5a": (10, "Ice Lake", "Ice Lake"),
    "9a49": (11, "Tiger Lake", "Tiger Lake"),
    "9a40": (11, "Tiger Lake", "Tiger Lake"),
    "46a6": (12, "Alder Lake", "Alder Lake"),
    "4626": (12, "Alder Lake", "Alder Lake"),
    "a7a0": (13, "Raptor Lake", "Raptor Lake"),
    "a7a1": (14, "Raptor Lake Refresh", "Raptor Lake"),
    "a7a8": (14, "Raptor Lake Refresh", "Raptor Lake"),
    "7d55": (15, "Arrow Lake", "Arrow Lake"),
    "7d51": (15, "Arrow Lake", "Arrow Lake"),
}

_CODENAMES = {
    1: "Nehalem/Westmere", 2: "Sandy Bridge", 3: "Ivy Bridge", 4: "Haswell",
    5: "Broadwell", 6: "Skylake", 7: "Kaby Lake", 8: "Coffee Lake",
    9: "Coffee Lake Refresh", 10: "Ice Lake / Comet Lake", 11: "Tiger Lake",
    12: "Alder Lake", 13: "Raptor Lake", 14: "Raptor Lake Refresh",
    15: "Arrow Lake",
}


def parse_intel_model(name: str) -> tuple[int, str]:
    """(generation, codename) из строки модели Intel CPU; (0, '') если неизвестно."""
    low = name.lower()

    if "xeon" in low:
        m = re.search(r"\bv(\d)\b", low)
        if m:
            gen = {2: 3, 3: 4, 4: 5, 5: 6, 6: 7}.get(int(m.group(1)), 0)
        elif re.search(r"\be[357]-\d{4}\b", low):
            gen = 2
        else:
            gen = 0
        return gen, _CODENAMES.get(gen, "")

    m1 = re.search(r"i[357]-(\d{3})\b", name, re.IGNORECASE)
    if m1:
        return 1, _CODENAMES[1]

    m = re.search(r"i[3579]-(\d{4,5})", name, re.IGNORECASE)
    if not m:
        return 0, ""
    num = m.group(1)
    gen = int(num[:2]) if (len(num) == 5 or num[0] == "1") else int(num[0])
    if not (2 <= gen <= 15):
        return 0, ""
    codename = _CODENAMES.get(gen, "Unknown")
    if gen == 10:
        codename = "Ice Lake" if len(num) == 4 else "Comet Lake"
    elif gen == 11:
        codename = "Tiger Lake"
    return gen, codename


def infer_intel_gen(name: str) -> tuple[int, str, str]:
    """Определение поколения по ключевым словам в названии. Возвращает (gen, codename, oc_platform)."""
    n = name.lower()
    rules = [
        (("15th", "arrow", "core ultra 200"), 15, "Arrow Lake", "Arrow Lake"),
        (("core ultra",), 14, "Meteor Lake", "Meteor Lake"),
        (("14th", "raptor lake refresh"), 14, "Raptor Lake Refresh", "Raptor Lake"),
        (("13th", "raptor"), 13, "Raptor Lake", "Raptor Lake"),
        (("12th", "alder"), 12, "Alder Lake", "Alder Lake"),
        (("11th", "tiger", "rocket"), 11, "Tiger Lake", "Tiger Lake"),
        (("10th", "comet", "ice"), 10, "Comet Lake", "Comet Lake"),
        (("9th", "coffee lake refresh"), 9, "Coffee Lake Refresh", "Coffee Lake"),
        (("8th", "coffee", "kaby lake-r", "whiskey"), 8, "Coffee Lake / Kaby Lake-R", "Kaby Lake-R"),
        (("7th", "kaby"), 7, "Kaby Lake", "Kaby Lake"),
        (("6th", "skylake"), 6, "Skylake", "Skylake"),
        (("5th", "broadwell"), 5, "Broadwell", "Broadwell"),
        (("4th", "haswell"), 4, "Haswell", "Haswell"),
        (("3rd", "ivy"), 3, "Ivy Bridge", "Ivy Bridge"),
        (("2nd", "sandy"), 2, "Sandy Bridge", "Sandy Bridge"),
    ]
    for keys, gen, codename, oc in rules:
        if any(k in n for k in keys):
            return gen, codename, oc
    return 0, "", ""


def detect_amd_gen(name: str) -> tuple[int, str, str]:
    """Определение Zen-поколения AMD. Возвращает (fam, codename, oc_platform)."""
    n = name.lower()
    if "ryzen ai" in n:
        return 12, "Zen 5", "Ryzen"
    if "ryzen" in n or "threadripper" in n:
        m = re.search(r'ryzen\s+(?:threadripper\s+)?\d*\s*(?:pro\s+)?(\d{4})', n) or re.search(r'(\d{4})', n)
        if m:
            model = int(m.group(1))
            sfx = re.search(rf'{model}([a-z]+)', n.replace(" ", ""))
            u_series = bool(sfx) and sfx.group(1).startswith("u")
            g_series = bool(sfx) and sfx.group(1).startswith("g")
            if model >= 9000:
                return 12, "Zen 5", "Ryzen"
            if model >= 8000:
                return 12, "Zen 4", "Ryzen"
            if model >= 7000:
                if (model // 10) % 10 == 2:
                    return 10, "Zen 2", "Ryzen"
                if (model // 10) % 10 == 3:
                    return 11, "Zen 3", "Ryzen"
                return 12, "Zen 4", "Ryzen"
            if model >= 6000:
                return 11, "Zen 3+", "Ryzen"
            if model >= 5000:
                return (10, "Zen 2", "Ryzen") if (u_series and (model // 100) % 10 in (3, 5, 7)) else (11, "Zen 3", "Ryzen")
            if model >= 3000:
                return (8, "Zen+", "Ryzen") if (g_series or u_series) else (10, "Zen 2", "Ryzen")
            if model >= 2000:
                return (8, "Zen", "Ryzen") if g_series else (8, "Zen+", "Ryzen")
            return 8, "Zen", "Ryzen"
        return 8, "Zen (Ryzen)", "Ryzen"
    if "athlon" in n and ("200" in n or "300" in n):
        return 8, "Zen (Athlon)", "Ryzen"
    return 0, "Pre-Zen / unknown", ""


def cpu_brand(name: str) -> str:
    n = name.lower()
    if "xeon" in n: return "Xeon"
    if "pentium" in n: return "Pentium"
    if "celeron" in n: return "Celeron"
    if "atom" in n: return "Atom"
    if "core ultra" in n: return "Core Ultra"
    if "ryzen" in n: return "Ryzen"
    if "threadripper" in n: return "Threadripper"
    return "Core"


def eth_chipset_from_name(name: str) -> str:
    """Чипсет Ethernet по имени адаптера Windows.

    Порядок важен: I211/I210 идут до общего «intel», иначе AppleIGB не
    выберется и для I211 подставится IntelMausi.
    """
    el = (name or "").lower()
    if "i219" in el:
        return "i219"
    if "i218" in el:
        return "i218"
    if "i217" in el:
        return "i217"
    if "i211" in el:
        return "i211"
    if "i210" in el:
        return "i210"
    if "i350" in el:
        return "i350"
    if "i225" in el:
        return "i225"
    if "i226" in el:
        return "i226"
    if "rtl8125" in el or "2.5gbe" in el:
        return "rtl8125"
    if "rtl8111" in el or "rtl8168" in el or "pcie gbe" in el:
        return "rtl8111"
    if "realtek" in el:
        return "realtek"
    if "intel" in el:
        return "intel"
    return ""


# Audio codec -> поддерживаемые layout-id. Таблица лежит в knowledge/audio_layouts
# и собрана по ресурсам AppleALC: только эти id кекст реально знает.
from ..knowledge.audio_layouts import LAYOUTS as _LAYOUTS  # noqa: E402

ALC_LAYOUTS: dict[str, tuple[int, ...]] = dict(_LAYOUTS)
