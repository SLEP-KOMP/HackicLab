"""Справочник подтверждённых сборок из hackmate-hwdb.

Данные — снимок репозитория https://github.com/hackmatelabs/hackmate-hwdb
(логи присылают пользователи Hackmate). Каталог ``hackiclab/assets/hwdb``
разложен так же, как в первоисточнике: режим сборки → поколение CPU → файл
устройства. Формат лога — плоский список ``ключ: значение`` из ``TEMPLATE.log``.

Модуль только читает вшитые данные: сети не касается, ничего не скачивает.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..scanner.models import HardwareProfile

SOURCE_URL = "https://github.com/hackmatelabs/hackmate-hwdb"
SOURCE_SNAPSHOT = "70ed4588db787915d8014093625376d24e752d51"

# папка режима в базе → ключ режима в интерфейсе
FEATURES = {
    "full-build-logs": "full",
    "already-formatted-logs": "formatted",
    "repair-efi-logs": "repair",
    "no-usb-logs": "no_usb",
    "dual-boot-logs": "dual_boot",
    "efi-health-check-logs": "health",
}

# В логах номера поколений AMD идут от вендора (Zen 4 → 12), а в проекте
# используется своя нумерация (Zen 4 → 12, Zen 3 → 11, Zen 2 → 10, Zen+ → 8).
_ZEN_BY_GENERATION = {
    8: {"zen", "zen+"},
    9: {"zen+"},
    10: {"zen 2"},
    11: {"zen 3", "zen 3+"},
    12: {"zen 4", "zen 5"},
}

_AMD_NAMES = re.compile(r"\b(amd|ryzen|threadripper|athlon)\b", re.I)
_INTEL_NAMES = re.compile(r"\b(intel|core|xeon|celeron|pentium)\b", re.I)
_CODEC = re.compile(r"(alc|al|ad)\s*(\d{3,4})", re.I)
_PLACEHOLDER = re.compile(r"^<.*>$")


@dataclass(frozen=True)
class Report:
    """Один присланный лог: железо и результат сборки."""

    device: str
    feature: str
    path: str
    cpu: str = ""
    generation: int = 0
    codename: str = ""
    platform: str = ""
    igpu: str = ""
    dgpu: str = ""
    audio_codec: str = ""
    ethernet: str = ""
    wifi: str = ""
    touchpad: str = ""
    nvme: bool = False
    thunderbolt: bool = False
    macos: str = ""
    worked: str = ""
    issues: str = ""
    notes: str = ""

    @property
    def vendor(self) -> str:
        if _AMD_NAMES.search(self.cpu):
            return "amd"
        if _INTEL_NAMES.search(self.cpu):
            return "intel"
        return ""

    @property
    def succeeded(self) -> bool:
        """Сборка дошла до конца (не гарантирует, что macOS загрузилась)."""
        return self.worked.lower() in {"build completed", "yes", "worked"}

    @property
    def failed(self) -> bool:
        return self.worked.lower() in {"build failed", "no", "failed"}

    @property
    def partial(self) -> bool:
        return self.worked.lower() == "partial"


def _dir() -> Path:
    """Путь к вшитой базе с учётом onefile-сборки PyInstaller."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidate = Path(base) / "hackiclab" / "assets" / "hwdb"
        if candidate.is_dir():
            return candidate
    return Path(__file__).resolve().parent.parent / "assets" / "hwdb"


def _clean(value: str) -> str:
    value = value.strip()
    if not value or _PLACEHOLDER.match(value):
        return ""
    if value.lower() in {"none", "n/a", "no", "unknown"}:
        return "" if value.lower() == "none" else value
    return value


def _flag(value: str) -> bool:
    return value.strip().lower() in {"yes", "true", "1", "да"}


def parse_log(text: str, path: str = "") -> Optional[Report]:
    """Разбирает один лог в ``Report``; ``None`` для пустого шаблона."""
    fields: dict[str, str] = {}
    last = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("---"):
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z_ ]*):\s*(.*)$", line)
        if match:
            last = match.group(1).strip().lower().replace(" ", "_")
            fields[last] = match.group(2).strip()
        elif last:
            # многострочные issues/notes: продолжение предыдущего ключа
            fields[last] = (fields[last] + " " + line.strip()).strip()

    if not any(_clean(fields.get(key, "")) for key in ("device", "cpu", "macos_version")):
        return None
    feature_dir = path.split("/")[0] if "/" in path else ""
    feature = FEATURES.get(feature_dir, fields.get("feature", "").strip())
    generation = 0
    try:
        generation = int(re.sub(r"\D", "", fields.get("cpu_generation", "")) or 0)
    except ValueError:
        generation = 0
    return Report(
        device=_clean(fields.get("device", "")),
        feature=feature,
        path=path,
        cpu=_clean(fields.get("cpu", "")),
        generation=generation,
        codename=_clean(fields.get("cpu_codename", "")),
        platform=_clean(fields.get("platform", "")).lower(),
        igpu=_clean(fields.get("igpu", "")),
        dgpu=_clean(fields.get("dgpu", "")),
        audio_codec=_clean(fields.get("audio_codec", "")),
        ethernet=_clean(fields.get("ethernet_chipset", "")),
        wifi=_clean(fields.get("wifi_chipset", "")),
        touchpad=_clean(fields.get("touchpad_type", "")),
        nvme=_flag(fields.get("nvme", "")),
        thunderbolt=_flag(fields.get("thunderbolt", "")),
        macos=_clean(fields.get("macos_version", "")),
        worked=_clean(fields.get("worked", "")),
        issues=_clean(fields.get("issues", "")),
        notes=_clean(fields.get("notes", "")),
    )


@lru_cache(maxsize=1)
def load_all() -> tuple[Report, ...]:
    """Все логи базы, разобранные один раз за запуск."""
    root = _dir()
    if not root.is_dir():
        return ()
    reports: list[Report] = []
    for log in sorted(root.rglob("*.log")):
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = log.relative_to(root).as_posix()
        report = parse_log(text, rel)
        if report is not None:
            reports.append(report)
    return tuple(reports)


def count() -> int:
    return len(load_all())


def _codec_key(value: str) -> str:
    match = _CODEC.search(value or "")
    return f"{match.group(1).lower()}{match.group(2)}" if match else ""


def _zen_family(report: Report) -> set[str]:
    names = {_norm(report.codename)}
    names |= _ZEN_BY_GENERATION.get(report.generation, set())
    return {name for name in names if name}


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _score(report: Report, profile: "HardwareProfile") -> int:
    """Насколько лог похож на профиль: 0 — чужая машина."""
    score = 0
    cpu = getattr(profile, "cpu", None)
    if cpu is None:
        return 0
    vendor = (getattr(cpu, "vendor", "") or "").lower()
    if vendor and report.vendor:
        if vendor != report.vendor:
            return 0
        score += 2
    platform = (getattr(profile, "platform", "") or "").lower()
    if platform and report.platform:
        if platform != report.platform:
            return 0
        score += 1
    generation = int(getattr(cpu, "generation", 0) or 0)
    if generation and report.generation:
        if vendor == "amd":
            if _zen_family(report) & _zen_by_project(generation):
                score += 3
        elif generation == report.generation:
            score += 3
    codec = _codec_key(getattr(getattr(profile, "audio", None), "codec", ""))
    if codec and codec == _codec_key(report.audio_codec):
        score += 3
    wifi = _norm(getattr(getattr(profile, "net", None), "wifi_chipset", ""))
    if wifi and wifi in _norm(report.wifi):
        score += 1
    eth = _norm(getattr(getattr(profile, "net", None), "eth_chipset", ""))
    if eth and eth in _norm(report.ethernet):
        score += 1
    igpu = _norm(getattr(getattr(profile, "igpu", None), "name", ""))
    if igpu and _norm(report.igpu) and _tokens(igpu) & _tokens(_norm(report.igpu)):
        score += 1
    return score


def _tokens(value: str) -> set[str]:
    return {word for word in re.split(r"[^0-9a-zа-я]+", value) if len(word) >= 3}


def _zen_by_project(generation: int) -> set[str]:
    return set(_ZEN_BY_GENERATION.get(generation, set()))


def match(profile: Optional["HardwareProfile"], limit: int = 3,
          min_score: int = 4) -> list[tuple[Report, int]]:
    """Логи с максимально похожим железом, лучшие сверху."""
    if profile is None:
        return []
    scored = [(report, _score(report, profile)) for report in load_all()]
    scored = [item for item in scored if item[1] >= min_score]
    scored.sort(key=lambda item: (item[1], item[0].succeeded), reverse=True)
    return scored[:limit]


def summary(profile: Optional["HardwareProfile"], limit: int = 3,
            min_score: int = 4) -> dict:
    """Короткая сводка для интерфейса: сколько отчётов и что с ними."""
    found = match(profile, limit=limit, min_score=min_score)
    return {
        "total": count(),
        "similar": len(found),
        "ok": sum(1 for report, _ in found if report.succeeded),
        "failed": sum(1 for report, _ in found if report.failed),
        "partial": sum(1 for report, _ in found if report.partial),
        "reports": found,
    }
