"""Проверка и установка обновлений через GitHub Releases.

Схема простая и без сервера: HackicLab читает последний релиз репозитория,
сравнивает тег с собственной версией и, если доступна более новая сборка,
предлагает скачать `HackicLab.exe` из вложений.

Самообновление возможно только у собранного EXE: подменять работающий файл
нельзя, но его можно переименовать. Текущий EXE уводится в «<имя>.old», на его
место копируется новая сборка, после чего приложение перезапускается, а старая
копия удаляется при следующем старте. Отдельный cmd-скрипт и консольное окно
при этом не нужны.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import __version__
from .builder.fetcher import _ssl_contexts, download_bytes

REPO = "SLEP-KOMP/HackicLab"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
RELEASES_ATOM = f"https://github.com/{REPO}/releases.atom"
ASSET_NAME = "HackicLab.exe"
ASSET_URL = f"https://github.com/{REPO}/releases/download/{{tag}}/{ASSET_NAME}"

#: Сколько держать результат проверки, чтобы не тратить лимит GitHub API.
CACHE_TTL = 6 * 3600


class UpdateError(RuntimeError):
    """Ошибка обновления с текстом, который можно показать пользователю."""

    def __init__(self, message: str, *, page_url: str = RELEASES_PAGE):
        super().__init__(message)
        self.page_url = page_url


class _RateLimited(Exception):
    """GitHub ответил 403/429 — исчерпан лимит запросов с этого IP."""

    def __init__(self, reset: str = ""):
        super().__init__("rate limited")
        self.reset = reset


@dataclass(frozen=True)
class UpdateInfo:
    version: str          # "1.0.2"
    tag: str              # "v1.0.2"
    notes: str            # текст релиза
    page_url: str         # страница релиза
    asset_url: str        # прямая ссылка на EXE (может быть пустой)
    asset_size: int | None = 0
    asset_digest: str = ""   # sha256 вложения по данным GitHub
    is_rebuild: bool = False  # та же версия, но другое содержимое сборки

    @property
    def has_asset(self) -> bool:
        return bool(self.asset_url)


def _cache_path() -> Path:
    return update_dir().parent / "release.json"


def _read_cache() -> dict:
    """Последний удачный ответ GitHub: нужен при лимите и без сети."""
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_cache(payload: dict) -> None:
    try:
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass


def _http(url: str, headers: Optional[dict] = None, timeout: int = 25,
          method: str = "GET") -> tuple[int, dict, bytes]:
    """HTTP-запрос с проверкой TLS; 403/429 превращает в _RateLimited."""
    request_headers = {"User-Agent": f"HackicLab/{__version__}"}
    request_headers.update(headers or {})
    last: Exception | None = None
    for ctx in _ssl_contexts():
        request = urllib.request.Request(url, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, context=ctx, timeout=timeout) as response:
                return int(response.status), dict(response.headers), response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                reset = ""
                try:
                    reset = str((exc.headers or {}).get("X-RateLimit-Reset") or "")
                except Exception:
                    reset = ""
                raise _RateLimited(reset) from exc
            if exc.code == 304:
                return 304, dict(exc.headers or {}), b""
            last = exc
            break
        except Exception as exc:  # сеть, DNS, сертификаты
            last = exc
    raise UpdateError(
        "Не удалось связаться с GitHub. Проверьте интернет или повторите позже.",
        page_url=RELEASES_PAGE,
    ) from last


def local_binary_size() -> int:
    """Размер запущенного EXE: сравнение размера ловит пересборку без API."""
    if not getattr(sys, "frozen", False):
        return 0
    try:
        return Path(sys.executable).stat().st_size
    except OSError:
        return 0


def _remote_size(url: str) -> int:
    try:
        _, headers, _ = _http(url, method="HEAD", timeout=20)
        for key, value in headers.items():
            if str(key).lower() == "content-length":
                return int(value)
    except Exception:
        pass
    return 0


def parse_version(text: str) -> tuple[int, ...]:
    """«v1.0.2» / «1.0.2-beta» → (1, 0, 2). Нечисловые хвосты отбрасываются."""
    raw = (text or "").strip().lstrip("vV")
    parts: list[int] = []
    for chunk in raw.replace("-", ".").replace("_", ".").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts) or (0,)


def is_newer(latest: str, current: str = __version__) -> bool:
    """Сравнивает версии по числовым сегментам, дополняя нулями."""
    a, b = parse_version(latest), parse_version(current)
    width = max(len(a), len(b))
    a += (0,) * (width - len(a))
    b += (0,) * (width - len(b))
    return a > b


def _find_asset(release: dict) -> tuple[str, int, str]:
    for asset in release.get("assets") or []:
        if (asset.get("name") or "").lower() == ASSET_NAME.lower():
            return (
                str(asset.get("browser_download_url") or ""),
                int(asset.get("size") or 0),
                str(asset.get("digest") or ""),
            )
    return "", 0, ""


def current_binary_digest() -> str:
    """sha256 запущенного EXE. Для запуска из исходников — пустая строка."""
    if not getattr(sys, "frozen", False):
        return ""
    try:
        digest = hashlib.sha256()
        with open(sys.executable, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return "sha256:" + digest.hexdigest()
    except Exception:
        return ""


def parse_release(release: dict, current_digest: str = "") -> Optional[UpdateInfo]:
    """Разбирает ответ GitHub API.

    Возвращает None, если версия не новее текущей. Исключение — пересборка:
    версия совпадает, но sha256 вложения отличается от запущенного EXE.
    Так обновления видны, даже когда релиз перезаливают без смены номера.
    """
    tag = str(release.get("tag_name") or "").strip()
    if not tag:
        return None
    version = tag.lstrip("vV")
    url, size, digest = _find_asset(release)
    newer = is_newer(version)
    rebuild = False
    if not newer:
        same_version = parse_version(version) == parse_version(__version__)
        if not (same_version and current_digest and digest):
            return None
        if digest == current_digest:
            return None
        rebuild = True
    return UpdateInfo(
        version=version,
        tag=tag,
        notes=str(release.get("body") or ""),
        page_url=str(release.get("html_url") or RELEASES_PAGE),
        asset_url=url,
        asset_size=size,
        asset_digest=digest,
        is_rebuild=rebuild,
    )


def _info_from_dict(data: dict) -> Optional[UpdateInfo]:
    """Собирает UpdateInfo из кэша (без обращения к сети)."""
    tag = str(data.get("tag") or "").strip()
    if not tag:
        return None
    version = str(data.get("version") or tag.lstrip("vV"))
    return UpdateInfo(
        version=version,
        tag=tag,
        notes=str(data.get("notes") or ""),
        page_url=str(data.get("page_url") or RELEASES_PAGE),
        asset_url=str(data.get("asset_url") or ""),
        asset_size=int(data.get("asset_size") or 0),
        asset_digest=str(data.get("asset_digest") or ""),
        is_rebuild=bool(data.get("is_rebuild")),
    )


def _cache_payload(release: dict, etag: str = "") -> dict:
    release_tag = str(release.get("tag_name") or "")
    url, size, digest = _find_asset(release)
    return {
        "tag": release_tag,
        "version": release_tag.lstrip("vV"),
        "notes": str(release.get("body") or ""),
        "page_url": str(release.get("html_url") or RELEASES_PAGE),
        "asset_url": url,
        "asset_size": size,
        "asset_digest": digest,
        "etag": etag,
        "ts": time.time(),
    }


def _info_from_tag(tag: str) -> Optional[UpdateInfo]:
    """Fallback без API: тег из ленты releases.atom и прямой URL вложения."""
    tag = (tag or "").strip()
    if not tag:
        return None
    version = tag.lstrip("vV")
    asset_url = ASSET_URL.format(tag=tag)
    page_url = f"https://github.com/{REPO}/releases/tag/{tag}"
    if is_newer(version):
        return UpdateInfo(
            version=version,
            tag=tag,
            notes="",
            page_url=page_url,
            asset_url=asset_url,
            asset_size=_remote_size(asset_url),
            asset_digest="",
        )
    if parse_version(version) != parse_version(__version__):
        return None
    local, remote = local_binary_size(), _remote_size(asset_url)
    if not local or not remote or local == remote:
        return None
    return UpdateInfo(
        version=version, tag=tag, notes="", page_url=page_url,
        asset_url=asset_url, asset_size=remote, asset_digest="", is_rebuild=True,
    )


_ATOM_LINK = re.compile(r'<link[^>]*rel="alternate"[^>]*href="([^"]+)"', re.I)


def _fetch_atom_tag() -> str:
    """Тег последнего релиза из Atom-ленты: лимит API не расходуется."""
    _, _, body = _http(RELEASES_ATOM, timeout=20)
    text = body.decode("utf-8", "replace")
    match = _ATOM_LINK.search(text)
    if not match:
        return ""
    return match.group(1).rstrip("/").split("/")[-1]


def check_for_update(timeout: int = 25, force: bool = False) -> Optional[UpdateInfo]:
    """Ищет новый релиз: API → лента releases.atom → кэш.

    При исчерпанном лимите GitHub (HTTP 403/429) это не ошибка для
    пользователя: сначала пробуем ленту релизов, затем последний удачный
    ответ из кэша. Исключение UpdateError бросается, только если данных нет
    совсем.
    """
    cache = _read_cache()
    cached = _info_from_dict(cache)
    fresh = (time.time() - float(cache.get("ts") or 0)) < CACHE_TTL
    if not force and cached is not None and fresh:
        return cached

    rate_limited = False
    try:
        headers = {"Accept": "application/vnd.github+json"}
        etag = str(cache.get("etag") or "")
        if etag:
            headers["If-None-Match"] = etag
        status, response_headers, body = _http(LATEST_API, headers=headers, timeout=timeout)
        if status == 304:
            _write_cache({**cache, "ts": time.time()})
            return cached
        release = json.loads(body.decode("utf-8"))
        if isinstance(release, dict) and release.get("tag_name"):
            new_etag = ""
            for key, value in response_headers.items():
                if str(key).lower() == "etag":
                    new_etag = str(value)
            payload = _cache_payload(release, new_etag)
            if payload["tag"]:
                _write_cache(payload)
            return parse_release(release, current_binary_digest())
    except _RateLimited:
        rate_limited = True
    except UpdateError:
        pass
    except Exception:
        pass

    try:
        tag = _fetch_atom_tag()
        if tag:
            info = _info_from_tag(tag)
            if info is not None:
                _write_cache({
                    "tag": info.tag, "version": info.version, "notes": info.notes,
                    "page_url": info.page_url, "asset_url": info.asset_url,
                    "asset_size": info.asset_size, "asset_digest": "",
                    "is_rebuild": info.is_rebuild, "ts": time.time(),
                })
            return info
    except Exception:
        pass

    if cached is not None:
        return cached
    if rate_limited:
        raise UpdateError(
            "GitHub временно ограничил частоту запросов с вашего адреса. "
            "Обновление можно скачать вручную со страницы релиза.",
        )
    raise UpdateError(
        "Не удалось проверить обновления: GitHub недоступен. "
        "Проверьте интернет и повторите попытку.",
    )


def can_self_update() -> bool:
    """Подменять исполняемый файл можно только у собранного EXE."""
    return bool(getattr(sys, "frozen", False))


def update_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "HackicLab" / "update"


def download_update(info: UpdateInfo, progress: Optional[Callable[[int], None]] = None) -> Path:
    """Скачивает EXE обновления и возвращает путь к нему."""
    if not info.asset_url:
        raise RuntimeError("В релизе нет вложения HackicLab.exe")
    target_dir = update_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"HackicLab-{info.version}.exe"
    if target.exists() and info.asset_size and target.stat().st_size == info.asset_size:
        if progress:
            progress(100)
        return target

    data = download_bytes(
        info.asset_url,
        headers={"User-Agent": f"HackicLab/{__version__}"},
        timeout=180,
    )
    if info.asset_size and abs(len(data) - info.asset_size) > 1024:
        raise UpdateError(
            f"Размер обновления не совпал: ожидалось {info.asset_size}, получено {len(data)}"
        )
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    if info.asset_digest and info.asset_digest.lower() != digest:
        raise UpdateError(
            "Скачанный файл не совпал с ожидаемым: обновление отменено. "
            "Попробуйте позже или скачайте EXE со страницы релиза.",
            page_url=info.page_url,
        )
    # пересборку определяли по размеру: подтверждаем хешем файла
    same_build = (not info.asset_digest
                  and parse_version(info.version) == parse_version(__version__)
                  and digest == current_binary_digest())
    if same_build:
        raise UpdateError("У вас уже установлена эта сборка — обновление не нужно.")
    tmp = target.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.replace(target)
    if progress:
        progress(100)
    return target


OLD_SUFFIX = ".old"


def apply_update(new_exe: Path) -> bool:
    """Ставит скачанный EXE на место текущего.

    Запущенный файл нельзя перезаписать, но можно переименовать: текущий EXE
    уводится в «<имя>.old», на его место копируется новая сборка. Старая копия
    удаляется при следующем запуске (см. cleanup_old_binaries).

    Возвращает True, если файл подменён: вызывающему остаётся перезапустить
    приложение.
    """
    if not can_self_update():
        return False
    target = Path(sys.executable).resolve()
    source = Path(new_exe).resolve()
    if not source.is_file():
        return False
    backup = target.with_name(target.name + OLD_SUFFIX)
    try:
        if backup.exists():
            backup.unlink()
        os.replace(target, backup)
    except OSError:
        return False
    try:
        shutil.copy2(source, target)
    except OSError:
        try:
            os.replace(backup, target)
        except OSError:
            pass
        return False
    return True


def relaunch_self() -> bool:
    """Запускает обновлённый EXE отдельным процессом."""
    exe = str(Path(sys.executable).resolve())
    flags = 0
    if hasattr(subprocess, "DETACHED_PROCESS"):
        flags = subprocess.DETACHED_PROCESS
    try:
        subprocess.Popen([exe], close_fds=True, creationflags=flags)
    except OSError:
        return False
    return True


def cleanup_old_binaries() -> None:
    """Удаляет «<имя>.old», оставшийся от прошлого обновления."""
    if not getattr(sys, "frozen", False):
        return
    exe = Path(sys.executable)
    try:
        (exe.with_name(exe.name + OLD_SUFFIX)).unlink()
    except OSError:
        pass


def open_release_page(url: str = RELEASES_PAGE) -> bool:
    try:
        return bool(webbrowser.open(url))
    except Exception:
        return False
