"""Реальные загрузки компонентов EFI по профилю железа.

- OpenCorePkg: скачивается архив по тегу (redirect, без GitHub API rate-limit).
- Кексты: скачиваются по шаблону имени с парсингом HTML-страницы релиза
  (избегая API-лимита), распаковываются и раскладываются по EFI/OC/Kexts.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Optional

from ..knowledge.kexts import KextEntry
from .cache_manager import cache_dir
from .fetcher import GitHubFetcher, download_bytes


class Downloader:
    """Высокоуровневые загрузки компонентов."""

    def __init__(self, client_name: str = "HackicLab"):
        self.client = client_name
        self.log: list[str] = []

    def _log(self, msg: str):
        self.log.append(msg)

    # --- OpenCore ---
    def download_open_core(self, dest_dir: Path) -> Optional[Path]:
        """Скачивает бинарный релиз OpenCorePkg (OpenCore-<tag>-RELEASE.zip).

        В релизе лежит готовый OpenCore.efi + EFI-структура. Возвращает путь к zip.
        """
        tag = GitHubFetcher.latest_tag("acidanthera/OpenCorePkg")
        if not tag:
            self._log("Не удалось определить версию OpenCore")
            return None
        # имя бинарного ассета: OpenCore-<tag>-RELEASE.zip (берём со страницы тега)
        html = self._fetch_release_html("acidanthera/OpenCorePkg", tag)
        asset = ""
        if html:
            names = self._extract_assets(html, "OpenCore-")
            rel = [n for n in names if n.lower().startswith("opencore-") and "release" in n.lower() and n.endswith(".zip")]
            rel.sort(key=len, reverse=True)
            if rel:
                asset = rel[0]
        if not asset:
            asset = f"OpenCore-{tag}-RELEASE.zip"
        url = f"https://github.com/acidanthera/OpenCorePkg/releases/download/{tag}/{asset}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / asset
        self._log(f"Скачиваю OpenCore {tag} ({asset}) …")
        data = download_bytes(url, headers={"User-Agent": self.client}, timeout=180)
        out.write_bytes(data)
        self._log(f"OpenCore сохранён: {out.name} ({len(data)//1024} КБ)")
        return out

    # --- Keхts ---
    def kext_release_file(self, entry: KextEntry, tag: str, fallback_asset: str = "") -> str:
        """Находит реальное имя файла-релиза для kext.

        Достаёт имена assets со страницы /releases/tag/<tag> (стабильный HTML,
        не зависит от JS binaries-page). При неудаче ищет .zip по форме
        '<pattern><tag>-RELEASE.zip'.
        """
        if fallback_asset:
            return fallback_asset
        if not entry.repo:
            return entry.name
        # 1) со страницы тега
        html = self._fetch_release_html(entry.repo, tag)
        if html:
            names = self._extract_assets(html, entry.asset_pattern)
            if names:
                # предпочитаем RELEASE (не DEBUG), затем самый длинный
                rel = [n for n in names if "release" in n.lower()]
                pool = rel or names
                pool.sort(key=len, reverse=True)
                return pool[0]
        # 2) стандартные формы имён acidanthera/большинства kext
        for cand in (f"{entry.asset_pattern.strip('-')}-{tag}-RELEASE.zip",
                     f"{entry.asset_pattern}{tag}-RELEASE.zip",
                     f"{entry.asset_pattern}-{tag}.zip",
                     f"{entry.asset_pattern}.zip",
                     f"{entry.asset_pattern}RELEASE.zip"):
            if cand.endswith(".zip"):
                return cand
        return f"{entry.asset_pattern}.zip" if entry.asset_pattern else entry.name

    def _fetch_release_html(self, repo: str, tag: str) -> str:
        """Возвращает список имён ассетов релиза.

        Использует fragment /releases/expanded_assets/<tag> — GitHub отдаёт его
        как HTML без JS и без API rate-limit. При неудаче фолбэк на страницу тега.
        """
        urls = [
            f"https://github.com/{repo}/releases/expanded_assets/{tag}",
            f"https://github.com/{repo}/releases/tag/{tag}",
        ]
        for url in urls:
            try:
                return download_bytes(url, headers={"User-Agent": self.client}, timeout=40).decode("utf-8", errors="replace")
            except Exception:
                continue
        return ""

    def _extract_assets(self, html: str, pattern: str) -> list[str]:
        """Имена файлов assets со страницы релиза (из ссылок /releases/download/)."""
        pat = re.compile(r'/releases/download/[^"/\s>]+/([^"<>&\s]+)')
        names = {m.group(1) for m in pat.finditer(html)}
        if pattern:
            names = {n for n in names if pattern in n}
        return sorted(names)

    def download_kext(self, entry: KextEntry, dest_dir: Path) -> Optional[Path]:
        """Скачивает архив kext и распаковывает его в dest_dir (папка Kexts).

        Возвращает путь к распакованной папке kext (если она .kext),
        или корень распаковки, если архив содержит несколько kext.
        """
        tag = GitHubFetcher.latest_tag(entry.repo)
        # Если тег резолвится в страницу /releases (нереведённый проект),
        # пропускаем с предупреждением — не блокируем сборку.
        if not tag or tag.lower() == "releases":
            self._log(f"{entry.name}: тег релиза не определён (пропуск)")
            return None
        base = f"https://github.com/{entry.repo}/releases/download/{tag}/"
        asset_name = self.kext_release_file(entry, tag)
        url = base + asset_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        # архив и распаковка — в кэше; в EFI/OC/Kexts попадают только .kext
        work = cache_dir() / "kexts" / entry.name
        work.mkdir(parents=True, exist_ok=True)
        try:
            data = download_bytes(url, headers={"User-Agent": self.client}, timeout=120)
        except Exception as e:
            self._log(f"{entry.name}: не скачалось ({e})")
            return None
        zpath = work / asset_name
        zpath.write_bytes(data)
        self._log(f"{entry.name}: скачано {asset_name}")

        # распаковка
        extract_dir = work / "unzip"
        if extract_dir.exists():
            import shutil as _sh
            _sh.rmtree(str(extract_dir), ignore_errors=True)
        extract_dir.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(str(zpath)) as z:
                for member in z.namelist():
                    low = member.lower()
                    if "__macosx" in low or ".dsym" in low:
                        continue
                    target = (extract_dir / member).resolve()
                    if target != extract_dir and extract_dir not in target.parents:
                        continue
                    z.extract(member, str(extract_dir))
            kext_dirs = [p for p in extract_dir.rglob("*.kext") if p.is_dir()]
            import shutil
            for kd in kext_dirs:
                dst = dest_dir / kd.name
                if not dst.exists():
                    shutil.copytree(str(kd), str(dst))
                    self._log(f"  → {dst.name}")
            return extract_dir
        except Exception as e:
            self._log(f"{entry.name}: распаковка не удалась ({e})")
            return None
