"""Локальный реестр просканированного железа.

Зачем: каталог конфигураций не может покрыть всё. Когда пользователь сканирует
железо, которого в каталоге нет, HackicLab запоминает обезличенный отпечаток
(CPU, поколение, платформа, GPU, плата) в ``~/.hackiclab/hardware_registry.json``.
Из этого списка можно одним нажатием предложить конфигурацию в каталог через
GitHub Issues — без серийников, MAC-адресов и прочих персональных данных.

Реестр только локальный: приложение ничего не отправляет само.
"""

from __future__ import annotations

import hashlib
import json
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from ..builder.cache_manager import app_home
from .configs import all_configs, similar_configs

ISSUES_NEW = "https://github.com/SLEP-KOMP/HackicLab/issues/new"
MAX_RECORDS = 500


def _file() -> Path:
    return app_home() / "hardware_registry.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fingerprint(profile) -> str:
    """Стабильный отпечаток без персональных данных."""
    cpu = getattr(profile, "cpu", None)
    parts = [
        str(getattr(profile, "platform", "") or ""),
        str(getattr(cpu, "vendor", "") or ""),
        str(getattr(cpu, "generation", "") or ""),
        str(getattr(cpu, "name", "") or "").strip().lower(),
    ]
    for attr in ("igpu", "dgpu"):
        gpu = getattr(profile, attr, None)
        if gpu is not None:
            parts.append(f"{attr}:{getattr(gpu, 'vendor', '')}:{getattr(gpu, 'device_id', '')}")
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _cpu_name(profile) -> str:
    cpu = getattr(profile, "cpu", None)
    return str(getattr(cpu, "name", "") or "").strip()


def _gpu_line(profile) -> str:
    names = []
    for attr in ("igpu", "dgpu"):
        gpu = getattr(profile, attr, None)
        if gpu is not None and getattr(gpu, "name", ""):
            names.append(str(gpu.name))
    return " + ".join(names)


def best_match(profile):
    """Запись каталога, если железо совпадает по вендору и поколению.

    Поколение должно совпадать точно: соседние поколения (Tiger Lake и Comet
    Lake, Zen и Zen 2) требуют разных патчей и SMBIOS, поэтому «похоже» здесь
    недостаточно для отметки «конфигурация известна».
    """
    cpu = getattr(profile, "cpu", None)
    vendor = str(getattr(cpu, "vendor", "") or "").lower()
    generation = int(getattr(cpu, "generation", 0) or 0)
    # Поколение 0 — «не определили». Иначе такое железо ложно совпадёт с
    # любой записью каталога, у которой поколение тоже 0 (например Core 2 Duo).
    if generation <= 0:
        return None
    for cfg in similar_configs(profile, limit=12):
        same_vendor = str(getattr(cfg, "vendor", "")).lower() == vendor
        same_gen = int(getattr(cfg, "generation", 0) or 0) == generation
        if same_vendor and same_gen:
            return cfg
    return None


def _record(profile, matched: str = "") -> dict:
    cpu = getattr(profile, "cpu", None)
    return {
        "fingerprint": fingerprint(profile),
        "cpu": _cpu_name(profile),
        "vendor": str(getattr(cpu, "vendor", "") or ""),
        "generation": int(getattr(cpu, "generation", 0) or 0),
        "platform": str(getattr(profile, "platform", "") or ""),
        "gpu": _gpu_line(profile),
        "board": " ".join(
            part for part in (
                str(getattr(profile, "board_vendor", "") or ""),
                str(getattr(profile, "board_name", "") or ""),
            ) if part
        ).strip(),
        "matched": matched,
    }


def load() -> dict[str, dict]:
    try:
        raw = json.loads(_file().read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if isinstance(v, dict)}


def _save(data: dict[str, dict]) -> None:
    try:
        _file().parent.mkdir(parents=True, exist_ok=True)
        _file().write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def register(profile) -> dict:
    """Записывает железо в реестр и возвращает его запись."""
    data = load()
    stamp = fingerprint(profile)
    match = best_match(profile)
    record = _record(profile, match.key if match else "")
    now = _now()
    old = data.get(stamp)
    if old:
        record["first_seen"] = old.get("first_seen") or now
        record["count"] = int(old.get("count") or 1) + 1
    else:
        record["first_seen"] = now
        record["count"] = 1
    record["last_seen"] = now
    data[stamp] = record
    if len(data) > MAX_RECORDS:
        # оставляем самые свежие записи
        ordered = sorted(data.items(), key=lambda kv: kv[1].get("last_seen", ""),
                         reverse=True)[:MAX_RECORDS]
        data = dict(ordered)
    _save(data)
    return record


def find(profile) -> dict | None:
    """Запись реестра для этого железа, если оно уже встречалось."""
    return load().get(fingerprint(profile))


def unknown() -> list[dict]:
    """Записи, для которых в каталоге не нашлось пары."""
    items = [rec for rec in load().values() if not rec.get("matched")]
    items.sort(key=lambda rec: rec.get("last_seen", ""), reverse=True)
    return items


def known_count() -> int:
    return sum(1 for rec in load().values() if rec.get("matched"))


def export_json(path: Path | None = None) -> Path:
    """Сохраняет реестр отдельным файлом (для отправки вручную)."""
    target = Path(path) if path else app_home() / "hardware_registry_export.json"
    target.write_text(
        json.dumps(load(), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _catalog_keys() -> list[str]:
    return [cfg.key for cfg in all_configs()]


def issue_url(record: dict | None = None, extra: str = "") -> str:
    """Ссылка на создание issue с обезличенным описанием конфигурации."""
    rec = record or (unknown()[0] if unknown() else {})
    title = "Каталог: добавить конфигурацию"
    if rec.get("cpu"):
        title = f"Каталог: {rec.get('cpu')}"
    lines = [
        "### Конфигурация",
        f"- CPU: {rec.get('cpu') or '—'} ({rec.get('vendor') or '?'}, "
        f"поколение {rec.get('generation') or '?'})",
        f"- Платформа: {rec.get('platform') or '—'}",
        f"- GPU: {rec.get('gpu') or '—'}",
        f"- Плата: {rec.get('board') or '—'}",
        "",
        "### Что работает",
        "- macOS: ",
        "- kext: ",
        "- SSDT: ",
        "- quirks: ",
        "",
        "### Примечания",
        "Отпечаток: " + str(rec.get("fingerprint") or "—"),
        extra.strip(),
        "",
        "_Данные обезличены: серийники и MAC не передаются._",
    ]
    body = quote("\n".join(lines))[:5000]
    return f"{ISSUES_NEW}?title={quote(title)}&body={body}&labels=hardware-catalog"


def open_issue(record: dict | None = None, extra: str = "") -> bool:
    try:
        return bool(webbrowser.open(issue_url(record, extra)))
    except Exception:
        return False


def catalog_keys() -> list[str]:
    return _catalog_keys()
