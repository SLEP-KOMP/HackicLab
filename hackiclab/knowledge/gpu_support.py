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
    low = (name or "").lower()
    if vend == "nvidia":
        if any(key in low for key in ("rtx 50", "gtx 50", "blackwell", "b100", "b200")):
            return {
                "ru": "Blackwell (RTX 50): драйверов нет ни в одной macOS — ускорения "
                      "не будет. Карту лучше вынуть или отключить: без драйвера она "
                      "работает через VESA и ломает сон.",
                "en": "Blackwell (RTX 50): no driver in any macOS, so there is no "
                      "acceleration. Better remove or disable the card: without a "
                      "driver it runs on VESA and breaks sleep.",
            }
        if any(key in low for key in ("rtx 40", "rtx 30", "rtx 20", "gtx 16", "ada",
                                      "ampere", "turing")):
            return {
                "ru": "NVIDIA Turing/Ampere/Ada: драйверов для macOS нет вообще "
                      "(даже для High Sierra), нужна дискретная AMD.",
                "en": "NVIDIA Turing/Ampere/Ada: no macOS drivers at all (not even "
                      "High Sierra); use an AMD dGPU.",
            }
        return {
            "ru": "NVIDIA: нативно поддерживаются только Kepler/Maxwell/Pascal до "
                  "macOS 10.13–11. Для новых систем нужна AMD.",
            "en": "NVIDIA: only Kepler/Maxwell/Pascal are native up to macOS "
                  "10.13–11. Newer systems need AMD.",
        }
    if vend == "amd":
        for prefix, family, ok, ru, en in AMD_PREFIXES:
            if dev.startswith(prefix):
                return {"ru": f"{family}: {ru}", "en": f"{family}: {en}"}
        return {"ru": "AMD: семейство не распознано, сверьтесь с гайдом.",
                "en": "AMD: family not recognised, check the guide."}
    if vend == "intel":
        if any(key in low for key in ("uhd graphics 7", "uhd 7", "iris xe", "xe graphics",
                                      "uhd graphics for", "graphics 7")):
            return {
                "ru": "iGPU Xe (11-е поколение и новее, UHD 770/750): драйвера в macOS "
                      "нет. Нужна дискретная AMD — встроенная графика не спасёт.",
                "en": "Xe iGPU (11th gen and newer, UHD 770/750): there is no macOS "
                      "driver. An AMD dGPU is required — the iGPU cannot render.",
            }
        return {"ru": "Intel iGPU: поддержка зависит от поколения (до Comet Lake).",
                "en": "Intel iGPU: support depends on generation (up to Comet Lake)."}
    return {}
