"""Манифест целостности собранного EFI.

После сборки в корень EFI пишется ``.hackiclab-manifest.json`` со sha256
каждого файла. При следующем аудите видно, что EFI изменили после сборки
(правка config.plist руками, подмена кекста, вирус) — и какие именно файлы.

Идея взята у OpCore-Simplify (integrity_checker), но сравнение идёт по
манифесту внутри EFI, поэтому проверка работает и на чужой машине.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_NAME = ".hackiclab-manifest.json"
SCHEMA = 1


def sha256_file(path: Path, block_size: int = 1 << 16) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(block_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _files(root: Path) -> list[Path]:
    return sorted(
        (item for item in root.rglob("*")
         if item.is_file() and item.name != MANIFEST_NAME),
        key=lambda item: item.relative_to(root).as_posix(),
    )


def write_manifest(root: Path) -> Path | None:
    """Пишет манифест; None — если папка пустая или запись не удалась."""
    root = Path(root)
    if not root.is_dir():
        return None
    files = _files(root)
    if not files:
        return None
    payload = {
        "schema": SCHEMA,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": {item.relative_to(root).as_posix(): sha256_file(item)
                  for item in files},
    }
    target = root / MANIFEST_NAME
    try:
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        return None
    return target


def read_manifest(root: Path) -> dict | None:
    """Содержимое манифеста или None, если он битый/отсутствует."""
    try:
        data = json.loads((Path(root) / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        return None
    return data


@dataclass
class IntegrityReport:
    """Итог сверки: что изменилось с момента сборки."""

    ok: bool = True
    checked: int = 0
    changed: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    created: str = ""
    manifest: Path | None = None

    @property
    def drift(self) -> int:
        return len(self.changed) + len(self.missing)


def verify_manifest(root: Path) -> IntegrityReport | None:
    """Сверяет EFI с манифестом; None — манифеста нет (EFI собран не нами)."""
    root = Path(root)
    data = read_manifest(root)
    if data is None:
        return None
    expected = data.get("files") or {}
    report = IntegrityReport(
        checked=0, created=str(data.get("created") or ""),
        manifest=root / MANIFEST_NAME)
    for rel, digest in expected.items():
        path = root / rel
        if not path.is_file():
            report.missing.append(rel)
            continue
        report.checked += 1
        try:
            if sha256_file(path) != digest:
                report.changed.append(rel)
        except OSError:
            report.changed.append(rel)
    expected_names = set(expected)
    for item in _files(root):
        rel = item.relative_to(root).as_posix()
        if rel not in expected_names:
            report.added.append(rel)
    report.ok = not (report.changed or report.missing)
    return report
