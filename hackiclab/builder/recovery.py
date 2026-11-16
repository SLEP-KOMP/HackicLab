"""Скачивание macOS Recovery через macrecovery.py (подход acidanthera/hackmate).

macrecovery.py скачивает загрузочные recovery-файлы (BaseSystem.dmg, *.chunklist,
com.apple.recovery.*) с Apple CDN под конкретную версию macOS. HackicLab
использует ту же схему board_id + mlb, что и hackmate.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# URL официального macrecovery.py из Acidanthera OpenCorePkg
MACRECOVERY_URL = (
    "https://raw.githubusercontent.com/acidanthera/OpenCorePkg/"
    "master/Utilities/macrecovery/macrecovery.py"
)


@dataclass
class MacOSVersion:
    name: str            # "macOS Sonoma"
    version: str         # "14" или "10.15"
    board_id: str        # board-id для query
    mlb: str             # MLB для query
    os_flag: str = ""    # "-os latest" для Tahoe
    release: int = 0     # год релиза (не критично)

    @property
    def slug(self) -> str:
        return self.version.replace(".", "_")

    @property
    def cache_key(self) -> str:
        query = "\0".join((self.version, self.board_id, self.mlb, self.os_flag or "default"))
        digest = hashlib.sha256(query.encode()).hexdigest()[:12]
        return f"{self.slug}-{digest}"

    @property
    def major(self) -> int:
        return int(self.version.split(".")[0])


RECOVERY_CACHE_DIR = Path.home() / ".hackiclab" / "cache" / "recovery"


MACOS_VERSIONS: list[MacOSVersion] = [
    MacOSVersion("macOS Tahoe (26)", "26", "Mac-CFF7D910A743CAAF", "00000000000000000", os_flag="-os latest", release=2025),
    MacOSVersion("macOS Sequoia (15)", "15", "Mac-7BA5B2D9E42DDD94", "00000000000000000", release=2024),
    MacOSVersion("macOS Sonoma (14)", "14", "Mac-827FAC58A8FDFA22", "00000000000000000", release=2023),
    MacOSVersion("macOS Ventura (13)", "13", "Mac-B4831CEBD52A0C4C", "00000000000000000", release=2022),
    MacOSVersion("macOS Monterey (12)", "12", "Mac-E43C1C25D4880AD6", "00000000000000000", release=2021),
    MacOSVersion("macOS Big Sur (11)", "11", "Mac-2BD1B31983FE1663", "00000000000000000", release=2020),
    MacOSVersion("macOS Catalina (10.15)", "10.15", "Mac-CFF7D910A743CAAF", "00000000000PHCD00", release=2019),
    MacOSVersion("macOS Mojave (10.14)", "10.14", "Mac-7BA5B2DFE22DDD8C", "00000000000KXPG00", release=2018),
    MacOSVersion("macOS High Sierra (10.13)", "10.13", "Mac-7BA5B2D9E42DDD94", "00000000000J80300", release=2017),
]


def macos_version_by_name(name: str) -> Optional[MacOSVersion]:
    """Ищет MacOSVersion по имени или marketing-версии."""
    name = (name or "").strip()
    for v in MACOS_VERSIONS:
        if name.lower() in v.name.lower() or name == v.version:
            return v
    return None


def macrecovery_args(version: MacOSVersion, outdir: Optional[Path] = None) -> list:
    args = ["-b", version.board_id, "-m", version.mlb]
    if version.os_flag:
        args.extend(version.os_flag.split())
    args.append("download")
    if outdir is not None:
        args.extend(["--outdir", str(outdir)])
    return args


def _macrecovery_path() -> Path:
    """Куда класть macrecovery.py: рядом с модулем, а в EXE — в кэш пользователя.

    В замороженной сборке ``_MEIPASS`` — временный каталог, который PyInstaller
    удаляет после выхода, поэтому скрипт скачивался при каждом запуске.
    """
    if getattr(sys, "frozen", False):
        from .cache_manager import cache_dir
        return cache_dir() / "macrecovery.py"
    return Path(__file__).parent / "macrecovery.py"


MACRECOVERY_PATH = _macrecovery_path()


def _validate_script(data: bytes) -> bool:
    """Проверяет скачанный macrecovery.py перед запуском.

    Хеш закрепить нельзя (скрипт берётся из master), поэтому минимум проверяем,
    что это компилируемый Python и что в нём есть ожидаемые элементы CLI.
    """
    if not data or len(data) < 1024:
        return False
    try:
        text = data.decode("utf-8")
        compile(text, "macrecovery.py", "exec")
    except Exception:
        return False
    return "board-id" in text or "-b" in text


def ensure_macrecovery() -> Path:
    """Возвращает путь к macrecovery.py (скачивает при необходимости)."""
    if MACRECOVERY_PATH.exists() and MACRECOVERY_PATH.stat().st_size > 1024:
        return MACRECOVERY_PATH
    import ssl
    import urllib.request

    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    req = urllib.request.Request(MACRECOVERY_URL, headers={"User-Agent": "HackicLab/1.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=20) as r:
        data = r.read()
    if not _validate_script(data):
        raise RuntimeError(
            "Скачанный macrecovery.py не похож на оригинальный скрипт — запуск отменён."
        )
    MACRECOVERY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MACRECOVERY_PATH.write_bytes(data)
    return MACRECOVERY_PATH


def _ensure_cert_bundle_env() -> None:
    """Как в hackmate: на Windows (особенно в замороженном EXE) urllib может
    не достучаться до системного хранилища сертификатов — подскажем certifi."""
    if sys.platform != "win32":
        return
    import os
    if os.environ.get("SSL_CERT_FILE"):
        return
    try:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
    except Exception:
        pass


def cached_recovery_files(version: MacOSVersion) -> list:
    cache = RECOVERY_CACHE_DIR / version.cache_key
    if not cache.exists():
        return []
    files = list(cache.glob("*.dmg")) + list(cache.glob("*.chunklist")) + list(cache.glob("com.apple.*"))
    return [f for f in files if f.is_file()]


class _LineWriter:
    """Пишет вывод macrecovery построчно в callback (без второго окна)."""

    def __init__(self, cb):
        self.cb = cb
        self.buf = ""

    def write(self, text):
        self.buf += text
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            line = line.strip()
            if line and self.cb:
                self.cb(line)

    def flush(self):
        line = self.buf.strip()
        self.buf = ""
        if line and self.cb:
            self.cb(line)


def _run_macrecovery_inprocess(script: Path, args: list, dest: Path,
                               progress_cb=None) -> int:
    """Запускает macrecovery.py в текущем процессе: без второго экземпляра EXE."""
    import contextlib
    import runpy

    old_argv = sys.argv[:]
    old_cwd = os.getcwd()
    writer = _LineWriter(progress_cb)
    code = 0
    try:
        sys.argv = [str(script), *list(args)]
        os.chdir(str(dest))
        with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
            runpy.run_path(str(script), run_name="__main__")
    except SystemExit as e:
        try:
            code = int(e.code or 0)
        except Exception:
            code = 1
    except Exception as e:
        writer.write(f"{e}\n")
        code = 1
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
    return code


def download_recovery(version: MacOSVersion, dest: Path, progress_cb=None) -> tuple[bool, str]:
    """Скачивает recovery macOS в dest (папка com.apple.recovery.boot). Возвращает (ok, msg)."""
    last_result = (False, "")
    for attempt in range(3):
        ok, msg = _download_recovery_once(version, dest, progress_cb=progress_cb)
        if ok:
            return ok, msg
        last_result = (ok, msg)
        if attempt < 2 and progress_cb:
            progress_cb(f"Повторная попытка (загрузка {attempt + 2}/3)…")
            import time
            time.sleep(3)
    return last_result


def _download_recovery_once(version: MacOSVersion, dest: Path, progress_cb=None) -> tuple[bool, str]:
    _ensure_cert_bundle_env()

    # кэш
    cached = cached_recovery_files(version)
    if cached:
        if progress_cb:
            progress_cb(f"Использую кэшированный recovery ({len(cached)} файлов)…")
        dest.mkdir(parents=True, exist_ok=True)
        for f in cached:
            shutil.copy2(f, dest / f.name)
        return True, f"Скопировано {len(cached)} файлов из кэша"

    try:
        script = ensure_macrecovery()
    except Exception as e:
        return False, f"Не удалось получить macrecovery.py: {e}"

    dest.mkdir(parents=True, exist_ok=True)
    script_args = macrecovery_args(version, dest)

    if progress_cb:
        progress_cb("Подключение к серверам Apple…")

    if getattr(sys, "frozen", False):
        # в EXE нельзя запускать sys.executable — это снова HackicLab.exe
        try:
            code = _run_macrecovery_inprocess(script, script_args, dest, progress_cb)
        except Exception as e:
            return False, f"Ошибка загрузки: {e}"
        if code != 0:
            return False, f"macrecovery завершился с кодом {code}"
    else:
        STALL_TIMEOUT = 120
        cmd = [sys.executable, str(script), *script_args]

        last_lines: list = []
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )

            import queue as _queue
            import threading as _th
            line_q = _queue.Queue()

            def _reader():
                for line in proc.stdout:
                    line_q.put(line)
                line_q.put(None)

            _th.Thread(target=_reader, daemon=True).start()

            last_msg = ""
            while True:
                try:
                    line = line_q.get(timeout=STALL_TIMEOUT)
                except _queue.Empty:
                    proc.kill()
                    return False, (
                        f"Загрузка recovery зависла (нет ответа {STALL_TIMEOUT}с) — "
                        "серверы Apple могут быть недоступны. Повторите позже."
                    )
                if line is None:
                    break
                line = line.strip()
                if line and line != last_msg:
                    last_msg = line
                    last_lines.append(line)
                    del last_lines[:-5]
                    if progress_cb:
                        progress_cb(line)
            proc.wait()
            if proc.returncode != 0:
                detail = " | ".join(last_lines) if last_lines else "нет вывода"
                return False, f"macrecovery завершился с кодом {proc.returncode}: {detail}"
        except Exception as e:
            return False, f"Ошибка загрузки: {e}"

    files = list(dest.glob("*.dmg")) + list(dest.glob("*.chunklist")) + list(dest.glob("com.apple.*"))
    if not files:
        return False, "После загрузки файлы recovery не найдены"

    # кэшируем
    try:
        cache = RECOVERY_CACHE_DIR / version.cache_key
        cache.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy2(f, cache / f.name)
    except Exception:
        pass

    return True, f"Скачано {len(files)} файлов в {dest}"
