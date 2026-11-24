"""Проверки совместимости по итогам тем сообщество (Sequoia/Sonoma/Ventura/…)."""

from __future__ import annotations

from ..builder.config_gen import _macos_major


def _has(name: str, *keys: str) -> bool:
    low = (name or "").lower()
    return any(k in low for k in keys)


def warnings_for(profile, target: str = "") -> list[tuple[str, str]]:
    """Список (ru, en) предупреждений для профиля и целевой macOS."""
    out: list[tuple[str, str]] = []
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
    if igpu is not None and getattr(igpu, "vendor", "") == "intel":
        if gen and (gen < 2 or gen > 10):
            out.append((
                "iGPU без драйвера: в системе будет ~7 МБ видеопамяти. Нужна дискретная карта.",
                "iGPU has no driver: expect ~7 MB VRAM. A discrete GPU is required."))

    audio = getattr(profile, "audio", None)
    if audio is not None and getattr(audio, "codec", "") and not getattr(audio, "layout_id", 0):
        out.append((
            "Кодек найден, но layout-id не подобран: переберите alcid или используйте VoodooHDA.",
            "Codec found but no layout-id: try other alcid values or VoodooHDA."))
    return out
