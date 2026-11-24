"""Поддержка видеокарт: device-id -> семейство и статус."""

from __future__ import annotations

#: (префикс device-id, семейство, поддерживается, заметка RU, EN)
AMD_PREFIXES: tuple[tuple[str, str, bool, str, str], ...] = (
    ("67", "Polaris", True, "Polaris: нативно, agdpmod не нужен.", "Polaris: native, no agdpmod."),
    ("6f", "Polaris", True, "Polaris: нативно.", "Polaris: native."),
    ("731", "Navi 10/14", True, "Navi 1x: нужен agdpmod=pikera.", "Navi 1x: needs agdpmod=pikera."),
    ("73b", "Navi 21", True, "Navi 21: macOS 12.1+.", "Navi 21: macOS 12.1+."),
    ("73d", "Navi 22", True, "Navi 22: macOS 12.1+.", "Navi 22: macOS 12.1+."),
    ("73e", "Navi 23", True, "Navi 23: NootRX вместо WhateverGreen.", "Navi 23: NootRX instead of WhateverGreen."),
    ("73f", "Navi 23", True, "Navi 23: NootRX вместо WhateverGreen.", "Navi 23: NootRX instead of WhateverGreen."),
    ("687", "Vega", True, "Vega: нативно, нужен SMBIOS iMacPro1,1.", "Vega: native, use iMacPro1,1."),
    ("69a", "Vega", True, "Vega: нативно.", "Vega: native."),
)


def gpu_note(vendor: str, device_id: str = "", name: str = "") -> dict[str, str]:
    """Заметка о поддержке GPU: {'ru': ..., 'en': ...} или пусто."""
    vend = (vendor or "").lower()
    dev = (device_id or "").lower().replace("0x", "")
    if vend == "nvidia":
        return {
            "ru": "NVIDIA не поддерживается macOS 11+: нужен OCLP или старая система.",
            "en": "NVIDIA is unsupported on macOS 11+: use OCLP or an older macOS.",
        }
    if vend == "amd":
        for prefix, family, ok, ru, en in AMD_PREFIXES:
            if dev.startswith(prefix):
                return {"ru": f"{family}: {ru}", "en": f"{family}: {en}"}
        return {"ru": "AMD: семейство не распознано, сверьтесь с гайдом.",
                "en": "AMD: family not recognised, check the guide."}
    if vend == "intel":
        return {"ru": "Intel iGPU: поддержка зависит от поколения (до Comet Lake).",
                "en": "Intel iGPU: support depends on generation (up to Comet Lake)."}
    return {}
