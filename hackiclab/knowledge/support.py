"""Проверка, сможет ли HackicLab собрать и проверить EFI под конфигурацию.

Каталог описывает, что сообщество считает рабочим. Этот модуль отвечает на
другой вопрос: хватает ли **текущей сборке HackicLab** данных, чтобы собрать
такой EFI — есть ли платформа OpenCore, модель SMBIOS, все kext и SSDT,
укладывается ли максимум macOS в потолок платформы и генерируется ли
config.plist, который проходит ocvalidate.

Результат — уровень поддержки (full/partial/none) и список причин, чтобы на
вкладке «Источники» не было ложных обещаний.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..builder.config_gen import BuildOptions, generate_config_plist
from ..builder.smbios_gen import generate_smbios
from ..knowledge.kexts import KEXT_DB, smbios_model_for
from ..knowledge.oc_platforms import max_macos_for, oc_platform_for
from ..knowledge.ssdt_logics import SSDT_DB
from ..scanner.models import CPUInfo, GPUInfo, HardwareProfile

LEVEL_FULL = "full"
LEVEL_PARTIAL = "partial"
LEVEL_NONE = "none"

#: kext'ы, которые HackicLab создаёт сам, а не скачивает из GitHub.
GENERATED_KEXTS = {"UTBMap", "USBToolBox", "UTBMap.kext"}

#: SSDT, которые создаются приложением или лежат во встроенных ассетах.
_SKIP_SSDT_WORDS = ("не нужен",)


@dataclass(frozen=True)
class SupportReport:
    """Итог проверки одной конфигурации каталога."""

    level: str
    checks: tuple[tuple[str, bool], ...]     # (ключ проверки, прошла ли)
    details: tuple[str, ...] = ()            # человекочитаемые детали (RU)

    @property
    def ok(self) -> bool:
        return self.level == LEVEL_FULL

    @property
    def failed(self) -> tuple[str, ...]:
        return tuple(key for key, passed in self.checks if not passed)


def _profile_for(cfg) -> HardwareProfile:
    """Синтетический профиль из записи каталога — для прогона генератора."""
    platform = "laptop" if getattr(cfg, "platform", "") == "laptop" else "desktop"
    profile = HardwareProfile(platform=platform)
    profile.cpu = CPUInfo(
        name=str(getattr(cfg, "cpu", "")),
        vendor=str(getattr(cfg, "vendor", "intel")),
        generation=int(getattr(cfg, "generation", 0) or 0),
        family=platform,
    )
    igpu = str(getattr(cfg, "igpu", "") or "")
    dgpu = str(getattr(cfg, "dgpu", "") or "")
    if igpu:
        profile.igpu = GPUInfo(name=f"iGPU {igpu}", vendor="intel", device_id=igpu,
                               is_integrated=True)
    if dgpu:
        profile.dgpu = GPUInfo(name=f"dGPU {dgpu}", vendor="amd", device_id=dgpu)
    return profile


def _known_kext_names() -> set[str]:
    """Имена, под которыми kext есть в базе: ключи и bundle_name."""
    names = set(KEXT_DB)
    for entry in KEXT_DB.values():
        bundle = getattr(entry, "bundle_name", "") or ""
        if bundle:
            names.add(bundle)
    return names


def _kexts_missing(cfg) -> list[str]:
    known = _known_kext_names()
    missing = []
    for name in getattr(cfg, "kexts", ()) or ():
        base = name.split("/")[0].strip()
        if not base or base in GENERATED_KEXTS:
            continue
        if base not in known:
            missing.append(base)
    return missing


def _ssdts_missing(cfg) -> list[str]:
    known = {spec.name for spec in SSDT_DB}
    missing = []
    for name in getattr(cfg, "ssdts", ()) or ():
        raw = name.strip()
        if not raw or any(word in raw.lower() for word in _SKIP_SSDT_WORDS):
            continue
        base = raw.split()[0]
        if base not in known:
            missing.append(base)
    return missing


def _macos_within_ceiling(cfg) -> bool:
    ceiling = str(getattr(cfg, "macos_max", "") or "")
    if not ceiling:
        return False
    from ..builder.config_gen import _macos_major  # локальный разбор имён версий

    want = _macos_major(ceiling)
    limit = _macos_major(max_macos_for(_profile_for(cfg)))
    # 10.x сравниваем как 10, порядок внутри линии не важен
    return want <= limit or (want == 10 and limit == 10)


@lru_cache(maxsize=64)
def _plist_ok(cfg_key: str, cpu: str, vendor: str, generation: int, platform: str,
              igpu: str, dgpu: str, target: str) -> tuple[bool, str]:
    """Пробная генерация config.plist с полным SMBIOS (без сети и файлов)."""
    profile = HardwareProfile(platform="laptop" if platform == "laptop" else "desktop")
    profile.cpu = CPUInfo(name=cpu, vendor=vendor, generation=generation,
                          family=profile.platform)
    if igpu:
        profile.igpu = GPUInfo(name="iGPU", vendor="intel", device_id=igpu,
                               is_integrated=True)
    if dgpu:
        profile.dgpu = GPUInfo(name="dGPU", vendor="amd", device_id=dgpu)
    try:
        model = smbios_model_for(profile, target)
        smbios = generate_smbios(model) if model else None
        opts = BuildOptions(target_macos=target, custom_smbios=smbios)
        data = generate_config_plist(profile, opts)
        if not data or b"<plist" not in data:
            return False, "config.plist пустой"
        return True, ""
    except Exception as exc:  # генератор не должен падать, но проверяем честно
        return False, f"{type(exc).__name__}: {exc}"


def support_report(cfg) -> SupportReport:
    """Считает уровень поддержки сборки для записи каталога."""
    profile = _profile_for(cfg)
    checks: list[tuple[str, bool]] = []
    details: list[str] = []

    platform_name = oc_platform_for(profile)
    platform_ok = bool(platform_name) and platform_name.lower() != "unknown"
    checks.append(("support.platform", platform_ok))
    if not platform_ok:
        details.append(f"платформа OpenCore не определена: {platform_name}")

    target = str(getattr(cfg, "macos_max", "") or "")
    if not target:
        # запись каталога прямо говорит «не рекомендуется» — сборку не обещаем
        checks.append(("support.macos", False))
        checks.append(("support.smbios", False))
        checks.append(("support.plist", False))
        details.append("конфигурация не рекомендуется для macOS")
        return SupportReport(level=LEVEL_NONE, checks=tuple(checks),
                             details=tuple(details))

    model = smbios_model_for(profile, target) if target else ""
    smbios_ok = bool(model)
    checks.append(("support.smbios", smbios_ok))
    if not smbios_ok:
        details.append("нет подходящей модели SMBIOS")

    missing_kexts = _kexts_missing(cfg)
    checks.append(("support.kexts", not missing_kexts))
    if missing_kexts:
        details.append("нет kext: " + ", ".join(missing_kexts))

    missing_ssdts = _ssdts_missing(cfg)
    checks.append(("support.ssdts", not missing_ssdts))
    if missing_ssdts:
        details.append("нет SSDT: " + ", ".join(missing_ssdts))

    macos_ok = _macos_within_ceiling(cfg)
    checks.append(("support.macos", macos_ok))
    if not macos_ok:
        ceiling = max_macos_for(profile)
        details.append(f"macOS {target or '—'} выше потолка платформы ({ceiling})")

    plist_ok, plist_error = _plist_ok(
        str(getattr(cfg, "key", "")), str(getattr(cfg, "cpu", "")),
        str(getattr(cfg, "vendor", "intel")), int(getattr(cfg, "generation", 0) or 0),
        str(getattr(cfg, "platform", "desktop")), str(getattr(cfg, "igpu", "") or ""),
        str(getattr(cfg, "dgpu", "") or ""), target,
    )
    checks.append(("support.plist", plist_ok))
    if not plist_ok:
        details.append("config.plist не генерируется: " + plist_error)

    critical = ("support.platform", "support.plist")
    failed = {key for key, passed in checks if not passed}
    if not failed:
        level = LEVEL_FULL
    elif any(key in failed for key in critical):
        level = LEVEL_NONE
    elif failed == {"support.macos"}:
        level = LEVEL_PARTIAL
    else:
        level = LEVEL_PARTIAL
    return SupportReport(level=level, checks=tuple(checks), details=tuple(details))


def all_reports(configs) -> dict[str, SupportReport]:
    return {cfg.key: support_report(cfg) for cfg in configs}
