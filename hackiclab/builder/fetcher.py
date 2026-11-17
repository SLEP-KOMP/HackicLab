"""Загрузка компонентов из GitHub (OpenCore, кексты) с кэшем и валидацией.

Логика адаптирована из hackmate (kexts.py kexts/_cached_or_download) и
OpCore-Simplify (gathering_files.py). Использует GitHub API для релизов.
"""

from __future__ import annotations

import io
import json
import ssl
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

from .cache_manager import cache_dir


def _ssl_contexts():
    """Контексты с обязательной проверкой сертификата: системный, затем certifi.

    Незашифрованный fallback (CERT_NONE) намеренно убран: по этим загрузкам в
    EFI попадают OpenCore и kext'ы, которые затем загружает ядро. Непроверенное
    TLS-соединение здесь означало бы возможность подмены.
    """
    ctxs = []
    try:
        ctxs.append(ssl.create_default_context())
    except Exception:
        pass
    try:
        import certifi
        ctxs.append(ssl.create_default_context(cafile=certifi.where()))
    except Exception:
        pass
    if not ctxs:
        ctxs.append(ssl.create_default_context())
    return ctxs


def download_bytes(url: str, headers: Optional[dict] = None, timeout: int = 60) -> bytes:
    """Скачивает URL с проверкой TLS (системное хранилище, затем certifi)."""
    last = None
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "HackicLab/0.1"})
    for ctx in _ssl_contexts():
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
    raise RuntimeError(
        f"Не удалось скачать {url}: {last}. Проверьте дату и время системы, "
        f"доступ к сети и корневые сертификаты (пакет certifi)."
    ) from last


class GitHubFetcher:
    """Минимальный доступ к GitHub releases.

    Не зависит от API rate-limit: использует HTTP-редирект releases/latest
    для получения тега, а затем прямой URL архива. Работает без токена и
    не расходует лимит 60/час на незарегистрированные запросы.
    """

    BASE = "https://github.com"

    @staticmethod
    def latest_tag(owner_repo: str) -> str:
        """Возвращает тег последнего релиза через redirect (без API)."""
        url = f"{GitHubFetcher.BASE}/{owner_repo}/releases/latest"
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "HackicLab/0.1"})
        ctx = _ssl_contexts()[0]
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
                return r.geturl().rstrip("/").split("/")[-1]
        except Exception:
            # если HEAD не даёт redirect, вернёмся к GET
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "HackicLab/0.1"})
                with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
                    return r.geturl().rstrip("/").split("/")[-1]
            except Exception:
                return ""

    @staticmethod
    def release_download_url(owner_repo: str, tag: str) -> str:
        """Прямой URL архива репозитория по тегу."""
        return f"{GitHubFetcher.BASE}/{owner_repo}/archive/refs/tags/{tag}.zip"

    @staticmethod
    def latest_release(owner_repo: str, headers: Optional[dict] = None) -> Optional[dict]:
        """Пытается получить релиз через API; если API заблокирован — фолбэк на redirect."""
        try:
            data = download_bytes(
                f"https://api.github.com/repos/{owner_repo}/releases/latest",
                headers=headers, timeout=30)
            return json.loads(data.decode("utf-8"))
        except Exception:
            tag = GitHubFetcher.latest_tag(owner_repo)
            if tag:
                return {"tag_name": tag, "name": tag, "assets": []}
            return None

    @staticmethod
    def find_asset(release: dict, pattern: str) -> Optional[dict]:
        """Ищет asset-release по подстроке имени."""
        assets = release.get("assets") or []
        for a in assets:
            if pattern in (a.get("name") or ""):
                return a
        return None


def download_asset(release: dict, pattern: str, dest_dir: Path, cache_name: str = "kexts") -> Optional[Path]:
    """Скачивает первый asset release по pattern в dest_dir, кэшируя по имени (hackmate-стиль)."""
    asset = GitHubFetcher.find_asset(release, pattern)
    if not asset:
        return None
    name = asset.get("name")
    url = asset.get("browser_download_url")
    size = asset.get("size") or 0
    if not name or not url:
        return None

    cache_root = cache_dir() / cache_name
    cached = cache_root / name
    if cached.exists() and (not size or abs(cached.stat().st_size - size) <= 1024):
        return cached

    out = dest_dir / name
    data = download_bytes(url, timeout=120)
    # Проверка размера и формата до записи: иначе страница ошибки GitHub
    # или обрезанный архив ложится в кэш как «скачанный» файл.
    if size and abs(len(data) - size) > 1024:
        raise IOError(f"Size mismatch for {name}")
    if len(data) < 512:
        raise IOError(f"{name}: ответ слишком короткий ({len(data)} байт)")
    if name.lower().endswith(".zip") and not zipfile.is_zipfile(io.BytesIO(data)):
        raise IOError(f"{name}: скачанный файл не является zip-архивом")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    try:
        cache_root.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(str(out), str(cached))
    except Exception:
        pass
    return out
