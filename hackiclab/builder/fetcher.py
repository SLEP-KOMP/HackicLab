"""Загрузка компонентов из GitHub (OpenCore, кексты) с кэшем и валидацией.

Каждый байт, попадающий в EFI, проходит три проверки: TLS-сертификат,
размер относительно метаданных релиза и формат архива. Кэш лежит в
каталоге приложения и переиспользуется между сборками.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import ssl
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

from .. import USER_AGENT
from .cache_manager import cache_dir
from .integrity import record, verify

_CONTEXTS: list[ssl.SSLContext] = []


def _ssl_contexts() -> list[ssl.SSLContext]:
    """Проверяющие TLS-контексты: системный и certifi, по одному на попытку.

    Отключение проверки сертификата здесь недопустимо: эти загрузки
    становятся загрузчиком OpenCore и кекстами ядра.
    """
    if _CONTEXTS:
        return _CONTEXTS
    candidates: list[ssl.SSLContext] = []
    try:
        candidates.append(ssl.create_default_context())
    except Exception:
        pass
    try:
        import certifi

        candidates.append(ssl.create_default_context(cafile=certifi.where()))
    except Exception:
        pass
    if not candidates:
        candidates.append(ssl.create_default_context())
    _CONTEXTS.extend(candidates)
    return _CONTEXTS


def _request(url: str, headers: Optional[dict], method: Optional[str] = None) -> urllib.request.Request:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": USER_AGENT})
    if method:
        req.method = method
    return req


def download_bytes(url: str, headers: Optional[dict] = None, timeout: int = 60) -> bytes:
    """Скачивает URL, пробуя хранилища сертификатов по очереди."""
    req = _request(url, headers)
    errors: list[str] = []
    for ctx in _ssl_contexts():
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as response:
                return response.read()
        except Exception as exc:
            errors.append(str(exc))
    reason = errors[-1] if errors else "нет доступных TLS-контекстов"
    raise RuntimeError(
        f"Не удалось скачать {url}: {reason}. Проверьте дату и время системы, "
        f"доступ к сети и корневые сертификаты (пакет certifi)."
    )


def _tag_from_redirect(url: str, timeout: int = 30) -> str:
    """Достаёт тег из конечного адреса releases/latest, пробуя HEAD, затем GET."""
    ctx = _ssl_contexts()[0]
    for method in ("HEAD", "GET"):
        req = _request(url, {"User-Agent": USER_AGENT}, method=method)
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as response:
                final = (response.geturl() or "").rstrip("/")
        except Exception:
            continue
        parts = [p for p in final.split("/") if p]
        if "tag" in parts:
            return parts[parts.index("tag") + 1]
    return ""


def _tag_from_listing(owner_repo: str, timeout: int = 30) -> str:
    """Берёт первый тег со страницы релизов.

    Нужен для проектов, у которых нет отметки «latest» (ChefKissInc и др.):
    редирект /releases/latest отдаёт 404, хотя релизы есть. Без фолбэка
    такой кекст молча не попадал в EFI.
    """
    try:
        html = download_bytes(f"{GitHubFetcher.BASE}/{owner_repo}/releases",
                              headers={"User-Agent": USER_AGENT}, timeout=timeout)
    except Exception:
        return ""
    text = html.decode("utf-8", "replace")
    match = re.search(r'/releases/tag/([^"\'?#<>]+)', text)
    return match.group(1) if match else ""


class GitHubFetcher:
    """Доступ к релизам GitHub без токена и без API-лимита.

    Тег берётся из редиректа страницы последнего релиза, поэтому лимит
    в 60 запросов в час на анонимный API не расходуется.
    """

    BASE = "https://github.com"

    @staticmethod
    def latest_tag(owner_repo: str) -> str:
        tag = _tag_from_redirect(f"{GitHubFetcher.BASE}/{owner_repo}/releases/latest")
        if tag and tag.lower() != "releases":
            return tag
        return _tag_from_listing(owner_repo)

    @staticmethod
    def release_download_url(owner_repo: str, tag: str) -> str:
        return f"{GitHubFetcher.BASE}/{owner_repo}/archive/refs/tags/{tag}.zip"

    @staticmethod
    def latest_release(owner_repo: str, headers: Optional[dict] = None) -> Optional[dict]:
        """Релиз через API, а при отказе — минимальное описание из редиректа."""
        api = f"https://api.github.com/repos/{owner_repo}/releases/latest"
        try:
            return json.loads(download_bytes(api, headers=headers, timeout=30).decode("utf-8"))
        except Exception:
            pass
        tag = GitHubFetcher.latest_tag(owner_repo)
        if not tag:
            return None
        return {"tag_name": tag, "name": tag, "assets": []}

    @staticmethod
    def find_asset(release: dict, pattern: str) -> Optional[dict]:
        for asset in release.get("assets") or []:
            if pattern in (asset.get("name") or ""):
                return asset
        return None


def _looks_like_zip(name: str, payload: bytes) -> bool:
    if not name.lower().endswith(".zip"):
        return True
    return zipfile.is_zipfile(io.BytesIO(payload))


def _check_payload(name: str, payload: bytes, expected_size: int) -> None:
    """Отсеивает страницы ошибок GitHub и обрезанные загрузки до записи."""
    if expected_size and abs(len(payload) - expected_size) > 1024:
        raise OSError(f"Size mismatch for {name}")
    if len(payload) < 512:
        raise OSError(f"{name}: ответ слишком короткий ({len(payload)} байт)")
    if not _looks_like_zip(name, payload):
        raise OSError(f"{name}: скачанный файл не является zip-архивом")


def _cache_copy(source: Path, cached: Path) -> None:
    try:
        cached.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(cached))
    except Exception:
        pass


def download_asset(release: dict, pattern: str, dest_dir: Path, cache_name: str = "kexts") -> Optional[Path]:
    """Скачивает первый подходящий asset в dest_dir и кладёт копию в кэш.

    Совпадение размера с метаданными допускается с точностью до килобайта:
    GitHub иногда отдаёт размер до сжатия на стороне CDN.
    """
    asset = GitHubFetcher.find_asset(release, pattern)
    if not asset:
        return None
    name = asset.get("name")
    url = asset.get("browser_download_url")
    expected = int(asset.get("size") or 0)
    if not name or not url:
        return None

    cache_root = cache_dir() / cache_name
    cached = cache_root / name
    if (cached.is_file()
            and (expected == 0 or abs(cached.stat().st_size - expected) <= 1024)
            # Хэш из манифеста ловит обрезанный или подменённый файл в кэше.
            and verify(cache_root, name, cached)):
        return cached

    payload = download_bytes(url, timeout=120)
    _check_payload(name, payload, expected)
    target = dest_dir / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    record(cache_root, name, target)
    _cache_copy(target, cached)
    return target
