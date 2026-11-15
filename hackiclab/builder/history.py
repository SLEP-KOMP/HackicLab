"""История сборок EFI.

Храним только метаданные и путь к собранной EFI: сами папки могут быть
большими, а копия делается лишь при восстановлении. Каталог — в профиле
пользователя (``%LOCALAPPDATA%\\HackicLab\\history``), поэтому история не
попадает в репозиторий.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


def history_dir() -> Path:
    """Каталог истории сборок."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "HackicLab" / "history"


@dataclass
class HistoryEntry:
    id: str
    created_at: str
    efi_path: str
    smbios: str = ""
    macos: str = ""
    opencore: str = ""
    ocvalidate_ok: Optional[bool] = None
    profile: str = ""
    kext_count: int = 0

    @property
    def exists(self) -> bool:
        return Path(self.efi_path).exists()


def _entry_path(entry_id: str, root: Optional[Path] = None) -> Path:
    base = Path(root) if root else history_dir()
    return base / f"{entry_id}.json"


def add(entry: HistoryEntry, root: Optional[Path] = None) -> Path:
    """Сохраняет запись истории в JSON."""
    base = Path(root) if root else history_dir()
    base.mkdir(parents=True, exist_ok=True)
    path = _entry_path(entry.id, base)
    path.write_text(json.dumps(asdict(entry), ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


def get(entry_id: str, root: Optional[Path] = None) -> Optional[HistoryEntry]:
    path = _entry_path(entry_id, root)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return HistoryEntry(**data)
    except Exception:
        return None


def list_entries(root: Optional[Path] = None) -> list[HistoryEntry]:
    """Все записи истории, новые сверху."""
    base = Path(root) if root else history_dir()
    if not base.is_dir():
        return []
    entries: list[HistoryEntry] = []
    for path in base.glob("*.json"):
        try:
            entries.append(HistoryEntry(**json.loads(path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    entries.sort(key=lambda e: e.created_at, reverse=True)
    return entries


def remove(entry_id: str, root: Optional[Path] = None) -> bool:
    path = _entry_path(entry_id, root)
    if path.exists():
        path.unlink()
        return True
    return False


def restore(entry_id: str, target_dir: Path, root: Optional[Path] = None) -> Path:
    """Копирует EFI записи в target_dir (внутрь целевой папки)."""
    entry = get(entry_id, root)
    if entry is None:
        raise RuntimeError(f"Запись истории не найдена: {entry_id}")
    src = Path(entry.efi_path)
    if not src.exists():
        raise RuntimeError(f"Собранная EFI больше не существует: {src}")
    dst = Path(target_dir)
    dst.mkdir(parents=True, exist_ok=True)
    target = dst / src.name if src.name else dst
    if target.exists():
        raise RuntimeError(f"Папка уже существует: {target}")
    shutil.copytree(str(src), str(target))
    return target


def record_build(plan, result, root: Optional[Path] = None) -> Optional[HistoryEntry]:
    """Создаёт запись по результату EFIBuilder.build()."""
    try:
        built = Path(result.root)
        efi = built / "EFI" if (built / "EFI").is_dir() else built
        stats = getattr(result, "stats", {}) or {}
        cpu = getattr(getattr(plan, "profile", None), "cpu", None)
        profile_text = " / ".join(part for part in (
            getattr(cpu, "name", "") or getattr(cpu, "brand", ""),
            getattr(plan.profile, "platform", ""),
        ) if part)
        now = datetime.now()
        entry = HistoryEntry(
            id=now.strftime("%Y%m%d-%H%M%S-%f"),
            created_at=now.isoformat(timespec="seconds"),
            efi_path=str(efi),
            smbios=(plan.smbios.model if getattr(plan, "smbios", None) else ""),
            macos=getattr(getattr(plan, "options", None), "target_macos", "") or "",
            opencore=str(stats.get("opencore", "")),
            ocvalidate_ok=stats.get("ocvalidate_ok"),
            profile=profile_text,
            kext_count=len(stats.get("kexts_placed", []) or []),
        )
        add(entry, root)
        return entry
    except Exception:
        return None
