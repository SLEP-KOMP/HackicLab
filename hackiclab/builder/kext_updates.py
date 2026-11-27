"""Проверка обновлений уже собранного EFI: версии кекстов против GitHub.

Своя версия читается из ``Contents/Info.plist`` (CFBundleShortVersionString),
последняя — из тега свежего релиза репозитория. Как у OCAT, но без установки:
HackicLab только сообщает, что вышло новее.
"""

from __future__ import annotations

import plistlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from ..knowledge.kexts import KEXT_DB

_VERSION_RE = re.compile(r"\d+(?:\.\d+)*")


@dataclass(frozen=True)
class KextState:
    name: str
    installed: str
    latest: str
    repo: str = ""

    @property
    def comparable(self) -> bool:
        """Обе версии — числа: только такие можно честно сравнить.

        У части кекстов тег релиза — не версия кекса (у OCLP тег вида 2.1.3
        при AMFIPass 1.4.1, у SMCAMDProcessor — 0.7.2 при 1.0.1 в плагине).
        Такие пары помечаем как несравнимые, иначе программа советует
        «обновить» кекс на более старую версию.
        """
        inst = tuple(int(p) for p in self.installed.split(".") if p.isdigit())
        late = tuple(int(p) for p in self.latest.split(".") if p.isdigit())
        return bool(inst) and bool(late)

    @property
    def has_update(self) -> bool:
        if not (self.installed and self.latest):
            return False
        if self.comparable:
            inst = tuple(int(p) for p in self.installed.split(".") if p.isdigit())
            late = tuple(int(p) for p in self.latest.split(".") if p.isdigit())
            return late > inst
        return self.latest != self.installed

    @property
    def status(self) -> str:
        if not self.latest:
            return "unknown"
        if not self.installed:
            return "unknown"
        if not self.comparable:
            return "unknown"
        return "update" if self.has_update else "ok"


def normalize_version(raw: str, prefix: str = "") -> str:
    """'RestrictEvents-1.1.5' / 'v1.1.5' -> '1.1.5'."""
    text = (raw or "").strip()
    if prefix and prefix.lower() in text.lower():
        text = text[text.lower().index(prefix.lower()) + len(prefix):]
    match = _VERSION_RE.search(text)
    return match.group(0) if match else ""


def _bundle_version(bundle: Path) -> str:
    info = bundle / "Contents" / "Info.plist"
    try:
        data = plistlib.loads(info.read_bytes())
    except (OSError, ValueError):
        return ""
    for key in ("CFBundleShortVersionString", "CFBundleVersion"):
        value = str(data.get(key) or "").strip()
        if value:
            return value
    return ""


def installed_versions(kexts_dir: Path) -> dict[str, str]:
    """Кекст -> версия из Info.plist (включая вложенные PlugIns)."""
    versions: dict[str, str] = {}
    root = Path(kexts_dir)
    if not root.is_dir():
        return versions
    for bundle in sorted(root.rglob("*.kext")):
        if not bundle.is_dir():
            continue
        name = bundle.name[:-5]
        version = _bundle_version(bundle)
        if name in KEXT_DB and version:
            versions.setdefault(name, version)
    return versions


def _default_latest(repo: str) -> str:
    from .fetcher import GitHubFetcher

    release = GitHubFetcher.latest_release(repo) or {}
    return str(release.get("tag_name") or "")


def check_updates(
    kexts_dir: Path,
    fetch_latest: Callable[[str], str] | None = None,
    only: Iterable[str] | None = None,
) -> list[KextState]:
    """Сверяет установленные кексты с последними релизами GitHub."""
    latest_for = fetch_latest or _default_latest
    installed = installed_versions(kexts_dir)
    names = set(installed) if only is None else {n for n in only if n in installed}
    result: list[KextState] = []
    for name in sorted(names):
        entry = KEXT_DB.get(name)
        if entry is None or not entry.repo:
            continue
        prefix = entry.asset_pattern
        tag = latest_for(entry.repo)
        result.append(KextState(
            name=name,
            installed=normalize_version(installed.get(name, ""), prefix),
            latest=normalize_version(tag, prefix),
            repo=entry.repo,
        ))
    return result
