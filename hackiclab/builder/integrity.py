"""Контроль целостности скачанных файлов: SHA-256 и манифест кэша.

Кэш кекстов/OpenCore лежит в пользовательской папке и переиспользуется между
сборками, поэтому файл может быть обрезан или подменён. Мы запоминаем хэш
после успешной загрузки и сверяем его при повторном использовании.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    """SHA-256 файла (потоково, без чтения целиком в память)."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path(root: Path) -> Path:
    return Path(root) / "manifest.json"


def load_manifest(root: Path) -> dict:
    try:
        return json.loads(_manifest_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_manifest(root: Path, data: dict) -> None:
    try:
        _manifest_path(root).write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8")
    except OSError:
        pass


def record(root: Path, key: str, path: Path) -> str:
    """Запоминает SHA-256 файла в манифесте кэша и возвращает хэш."""
    digest = sha256_file(path)
    data = load_manifest(root)
    data[key] = digest
    save_manifest(root, data)
    return digest


def verify(root: Path, key: str, path: Path) -> bool:
    """True, если хэш файла совпадает с записанным; нет записи — False."""
    expected = load_manifest(root).get(key)
    if not expected or not Path(path).is_file():
        return False
    return sha256_file(path) == expected
