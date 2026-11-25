"""Ресурсы OpenCanopy: иконки, шрифты и подписи для графического меню.

Архив OpenCore 1.0.8 приходит с пустыми папками EFI/OC/Resources — самих
иконок и шрифтов в нём нет. Официальный источник этих файлов — отдельный
репозиторий acidanthera/OcBinaryData; приложение скачивает его по запросу
пользователя и берёт только Font, Image и Label (Audio — лишние звуки).
"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path
from typing import Callable, Optional

#: Архив репозитория OcBinaryData (единственный официальный источник иконок).
RESOURCES_URL = ("https://codeload.github.com/acidanthera/OcBinaryData/"
                 "tar.gz/refs/heads/master")

#: Папки внутри Resources, которые нужны OpenCanopy.
_KEEP = ("Font", "Image", "Label", "Audio")


def has_real_files(folder: Optional[Path]) -> bool:
    """Есть ли в папке хоть один файл (в архиве OpenCore только пустые папки)."""
    if folder is None or not folder.is_dir():
        return False
    return any(item.is_file() for item in folder.rglob("*"))


def _safe_target(root: Path, member_name: str) -> Optional[Path]:
    """Путь внутри root или None, если архив пытается выйти наружу."""
    parts = [p for p in member_name.replace("\\", "/").split("/") if p and p != "."]
    if not parts or ".." in parts:
        return None
    target = (root / Path(*parts)).resolve()
    root_resolved = root.resolve()
    if target != root_resolved and root_resolved not in target.parents:
        return None
    return target


def extract_resources(data: bytes, dest: Path,
                      log: Optional[Callable[[str], None]] = None) -> int:
    """Распаковывает Font/Image/Label из архива OcBinaryData; число файлов."""
    written = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            path = member.name.replace("\\", "/")
            if "/Resources/" not in path:
                continue
            tail = path.split("/Resources/", 1)[1]
            top = tail.split("/", 1)[0]
            if top not in _KEEP:
                continue
            target = _safe_target(dest, tail)
            if target is None:
                if log:
                    log(f"Resources: пропущен небезопасный путь {path}")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                continue
            target.write_bytes(source.read())
            written += 1
    return written


def fetch_resources(dest: Path, log: Optional[Callable[[str], None]] = None,
                    downloader: Optional[Callable[[str], bytes]] = None) -> int:
    """Скачивает Resources в dest; возвращает число файлов (0 — не вышло)."""
    if downloader is None:
        from .fetcher import download_bytes
        downloader = download_bytes
    try:
        data = downloader(RESOURCES_URL)
    except Exception as exc:
        if log:
            log(f"Resources: скачать не удалось ({exc})")
        return 0
    try:
        written = extract_resources(data, dest, log=log)
    except Exception as exc:
        if log:
            log(f"Resources: архив не распакован ({exc})")
        return 0
    if written and log:
        log(f"Resources: {written} файлов из OcBinaryData")
    return written


#: Что OpenCanopy обязан найти в Resources, иначе меню будет пустым.
REQUIRED_FILES = (
    "Font/Font_1x.bin",
    "Font/Font_1x.png",
    "Font/Font_2x.bin",
)


def missing_parts(resources: Optional[Path], variant: str = "GoldenGate") -> list[str]:
    """Чего не хватает в Resources: шрифтов, иконок темы, подписей."""
    if resources is None:
        return ["Resources"]
    root = Path(resources)
    missing = [item for item in REQUIRED_FILES if not (root / item).is_file()]
    theme = root / "Image" / "Acidanthera" / variant
    if not (theme.is_dir() and any(theme.iterdir())):
        missing.append("Image/Acidanthera/" + variant)
    labels = root / "Label"
    if not (labels.is_dir() and any(labels.glob("*.lbl"))):
        missing.append("Label")
    return missing


def count_files(folder: Optional[Path]) -> int:
    """Сколько файлов лежит в папке (0, если её нет)."""
    if folder is None or not folder.is_dir():
        return 0
    return sum(1 for item in folder.rglob("*") if item.is_file())


def ensure_resources(dest: Path, log: Optional[Callable[[str], None]] = None,
                     downloader: Optional[Callable[[str], bytes]] = None,
                     cache: Optional[Path] = None) -> int:
    """Кладёт Resources в dest, переиспользуя закешированную копию.

    Архив OcBinaryData весит десятки мегабайт, поэтому скачиваем его один
    раз в кэш приложения, а в каждый следующий EFI копируем уже готовое.
    """
    import shutil

    if cache is None:
        from .cache_manager import cache_dir
        cache = cache_dir() / "canopy" / "Resources"
    if not has_real_files(cache):
        written = fetch_resources(cache, log=log, downloader=downloader)
        if not written:
            return 0
    elif log:
        log("Resources: беру из кэша")
    try:
        if dest.exists():
            shutil.rmtree(str(dest), ignore_errors=True)
        shutil.copytree(str(cache), str(dest))
    except Exception as exc:
        if log:
            log(f"Resources: скопировать не удалось ({exc})")
        return 0
    return count_files(dest)

