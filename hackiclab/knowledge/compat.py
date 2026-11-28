"""Проверки совместимости по итогам тем сообщество (Sequoia/Sonoma/Ventura/…)."""

from __future__ import annotations

from ..builder.config_gen import _macos_major
from .storage_support import storage_notes


def _has(name: str, *keys: str) -> bool:
    low = (name or "").lower()
    return any(k in low for k in keys)


def warnings_for(profile, target: str = "") -> list[tuple[str, str]]:
    """Список (ru, en) предупреждений для профиля и целевой macOS."""
    out: list[tuple[str, str]] = []
    for note in storage_notes(getattr(profile, "storage", None)):
        out.append((note.ru, note.en))
    cpu = getattr(profile, "cpu", None)
    if cpu is None:
        return out
    gen = int(getattr(cpu, "generation", 0) or 0)
    major = _macos_major(target)

    if (getattr(cpu, "vendor", "") == "intel" and gen < 4 and major >= 12):
        out.append((
            "Haswell и старше на Monterey+ требует CryptexFixup/OCLP: без патчей не загрузится.",
            "Haswell and older need CryptexFixup/OCLP on Monterey+: no boot without patches."))

    gpu = getattr(profile, "dgpu", None)
    if gpu is not None and getattr(gpu, "vendor", "") == "nvidia":
        name = str(getattr(gpu, "name", ""))
        if _has(name, "gtx 7", "gtx 9", "gtx 10", "rtx", "maxwell", "pascal", "turing"):
            out.append((
                "NVIDIA Maxwell/Pascal/Turing: Web Driver нет, на Big Sur+ не заведётся.",
                "NVIDIA Maxwell/Pascal/Turing: no Web Driver, won't work on Big Sur+."))

    igpu = getattr(profile, "igpu", None)
    if (igpu is not None and getattr(igpu, "vendor", "") == "intel"
            and gen and (gen < 2 or gen > 10)):
        out.append((
            "iGPU без драйвера: в системе будет ~7 МБ видеопамяти. Нужна дискретная карта.",
            "iGPU has no driver: expect ~7 MB VRAM. A discrete GPU is required."))

    audio = getattr(profile, "audio", None)
    if audio is not None and getattr(audio, "codec", "") and not getattr(audio, "layout_id", 0):
        out.append((
            "Кодек найден, но layout-id не подобран: переберите alcid или используйте VoodooHDA.",
            "Codec found but no layout-id: try other alcid values or VoodooHDA."))

    if major >= 26:
        # macOS 26 (Tahoe): проверено по Dortania OS Specific: macOS 26 Tahoe.
        out.append((
            "macOS 26 без AppleHDA: AppleALC и alcid не дают аналоговый звук — "
            "нужен VoodooHDA или root-патч с возвратом AppleHDA.",
            "macOS 26 has no AppleHDA: AppleALC and alcid give no analog sound — "
            "use VoodooHDA or a root patch restoring AppleHDA."))
        dgpu = getattr(profile, "dgpu", None)
        if dgpu is not None and str(getattr(dgpu, "vendor", "") or "").lower() == "amd":
            out.append((
                "WhateverGreen на macOS 26 конфликтует с AMD: возможна паника на "
                "коннекторах. При панике кекст убирают, а agdpmod=pikera ставят "
                "патчем в Kernel → Patch.",
                "WhateverGreen clashes with AMD on macOS 26: connector-related kernel "
                "panics. On panic remove the kext and add agdpmod=pikera via "
                "Kernel → Patch."))
        out.append((
            "OTA-обновления на macOS 14.4+: нужны RestrictEvents, revpatch=sbvmm "
            "и SecureBootModel Disabled (или iBridged).",
            "OTA updates on macOS 14.4+: RestrictEvents, revpatch=sbvmm and "
            "SecureBootModel Disabled (or iBridged) are required."))
    return out
