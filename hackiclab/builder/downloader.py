"""Реальные загрузки компонентов EFI по профилю железа.

- OpenCorePkg: скачивается архив по тегу (redirect, без GitHub API rate-limit).
- Кексты: скачиваются по шаблону имени с парсингом HTML-страницы релиза
  (избегая API-лимита), распаковываются и раскладываются по EFI/OC/Kexts.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Optional

from ..knowledge.kexts import KextEntry, asset_variant
from .cache_manager import cache_dir
from .fetcher import GitHubFetcher, download_bytes

_VERSIONED_BUNDLE = re.compile(r"^(?P<base>.+?)-\d+(?:\.\d+)*$")


def _valid_cached_zip(path: Path) -> bool:
    """Готовый архив в кэше: не обрезан и действительно zip."""
    try:
        return (path.is_file() and path.stat().st_size > 512
                and zipfile.is_zipfile(str(path)))
    except OSError:
        return False


def canonical_kext_name(name: str) -> str:
    """Имя бандла без версии: ``AppleIGB-5.11.8.kext`` → ``AppleIGB.kext``.

    В архивах релизов часть проектов называет папку с версией
    (AppleIGB, AirportItlwm и др.). Если оставить её как есть,
    запись в config.plist и фильтр по выбранным кекстам расходятся,
    и драйвер молча удаляется из готового EFI.
    """
    stem = name[:-5] if name.lower().endswith(".kext") else name
    match = _VERSIONED_BUNDLE.match(stem)
    return f"{match.group('base') if match else stem}.kext"


class Downloader:
    """Высокоуровневые загрузки компонентов."""

    def __init__(self, client_name: str = "HackicLab"):
        self.client = client_name
        self.log: list[str] = []

    def _log(self, msg: str):
        self.log.append(msg)

    # --- HeliPort ---
    def download_heliport(self, dest_dir: Path) -> Optional[Path]:
        """Скачивает HeliPort.dmg — приложение Wi-Fi для режима itlwm.

        Без HeliPort у пользователя нет меню Wi-Fi в macOS, хотя интернет
        работает. Кладём dmg рядом с EFI, чтобы его можно было поставить
        уже на первой загрузке.
        """
        try:
            release = GitHubFetcher.latest_release("OpenIntelWireless/HeliPort")
        except Exception as exc:
            self._log(f"HeliPort: релиз не получен ({exc})")
            return None
        if not release:
            return None
        asset = GitHubFetcher.find_asset(release, "HeliPort.dmg")
        if not asset or not asset.get("browser_download_url"):
            self._log("HeliPort: в релизе нет HeliPort.dmg")
            return None
        try:
            data = download_bytes(str(asset["browser_download_url"]), timeout=180)
        except Exception as exc:
            self._log(f"HeliPort: не скачалось ({exc})")
            return None
        # dmg весит ~8 МБ: обрезанный файл или страница ошибки сюда не пройдут
        if len(data) < 1_000_000:
            self._log(f"HeliPort: подозрительно маленький файл ({len(data)} байт)")
            return None
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / "HeliPort.dmg"
        out.write_bytes(data)
        return out

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
    def kext_release_file(self, entry: KextEntry, tag: str, fallback_asset: str = "",
                          target_macos: str = "") -> str:
        """Находит реальное имя файла-релиза для kext.

        Достаёт имена assets со страницы /releases/tag/<tag> (стабильный HTML,
        не зависит от JS binaries-page). Если у кекста есть версии-специфичные
        сборки (AirportItlwm), берётся файл под целевую macOS — иначе в EFI
        попадала сборка под другую систему.
        """
        if fallback_asset:
            return fallback_asset
        if not entry.repo:
            return entry.name
        variant = asset_variant(entry, target_macos)
        # 1) со страницы тега
        html = self._fetch_release_html(entry.repo, tag)
        if html:
            names = self._extract_assets(html, entry.asset_pattern)
            if variant and names:
                matching = [n for n in names if variant.lower() in n.lower()]
                if matching:
                    names = matching
                else:
                    self._log(f"{entry.name}: сборки под {target_macos} нет — беру общую")
            if names:
                # предпочитаем RELEASE (не DEBUG), затем самую свежую сборку
                rel = [n for n in names if "release" in n.lower()]
                pool = rel or names
                if variant:
                    pool.sort()
                    return pool[-1]
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
            # Имена ассетов бывают в верхнем регистре (1.2.6.RELEASE.zip),
            # поэтому сравнение без учёта регистра — иначе кекст «не находится».
            names = {n for n in names if pattern.lower() in n.lower()}
        return sorted(names)

    def download_kext(self, entry: KextEntry, dest_dir: Path,
                      target_macos: str = "") -> Optional[Path]:
        """Скачивает архив kext и распаковывает его в dest_dir (папка Kexts).

        Возвращает путь к распакованной папке kext (если она .kext),
        или корень распаковки, если архив содержит несколько kext.
        """
        if entry.url:
            # Прямая ссылка (payloads OCLP): тег и имя ассета не нужны.
            asset_name = entry.url.rstrip("/").split("/")[-1] or f"{entry.name}.zip"
            url = entry.url
        else:
            tag = GitHubFetcher.latest_tag(entry.repo)
            # Если тег резолвится в страницу /releases (нереведённый проект),
            # пропускаем с предупреждением — не блокируем сборку.
            if not tag or tag.lower() == "releases":
                self._log(f"{entry.name}: тег релиза не определён (пропуск)")
                return None
            base = f"https://github.com/{entry.repo}/releases/download/{tag}/"
            asset_name = self.kext_release_file(entry, tag, target_macos=target_macos)
            url = base + asset_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        # архив и распаковка — в кэше; в EFI/OC/Kexts попадают только .kext
        work = cache_dir() / "kexts" / entry.name
        work.mkdir(parents=True, exist_ok=True)
        zpath = work / asset_name
        if _valid_cached_zip(zpath):
            # Уже скачанный архив (возможно, с сетевого кэша) — не тратим лимит GitHub.
            self._log(f"{entry.name}: из кэша {asset_name}")
        else:
            try:
                data = download_bytes(url, headers={"User-Agent": self.client}, timeout=120)
            except Exception as e:
                self._log(f"{entry.name}: не скачалось ({e})")
                return None
            # Проверяем архив до записи: страница ошибки вместо zip и обрезанный
            # файл не должны попадать в кэш как «скачанный кекст».
            if len(data) < 512 or not zipfile.is_zipfile(io.BytesIO(data)):
                self._log(f"{entry.name}: {asset_name} повреждён или это не архив "
                          f"({len(data)} байт) — пропуск")
                return None
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
                dst = dest_dir / canonical_kext_name(kd.name)
                if not dst.exists():
                    shutil.copytree(str(kd), str(dst))
                    self._log(f"  → {dst.name}")
            return extract_dir
        except Exception as e:
            self._log(f"{entry.name}: распаковка не удалась ({e})")
            return None
