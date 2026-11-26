"""Сбор отчётов о сборках: локальная база и отправка в наш трекер.

Каждая сборка — удачная или нет — сохраняется локально в
``~/.hackiclab/community`` одним JSON-файлом: железо, целевая macOS, набор
кекстов, итог и ошибки. Из записи можно открыть страницу нового issue в нашем
репозитории с уже заполненным телом — так отчёты попадают в GitHub без токенов
и ключей в приложении.

Формат записи фиксирован (``SCHEMA``), чтобы старые отчёты читались после
обновлений.
"""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import webbrowser
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..scanner.models import HardwareProfile

SCHEMA = 1
REPO = "SLEP-KOMP/HackicLab"
LABEL = "community-report"
TITLE_LIMIT = 120
BODY_LIMIT = 2200
JSON_LIMIT = 1500


def store_dir() -> Path:
    """Папка локальной базы отчётов (создаётся при первом обращении)."""
    from ..builder.cache_manager import app_home

    folder = app_home() / "community"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _profile_digest(profile: "HardwareProfile") -> str:
    raw = json.dumps(_hardware(profile), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _hardware(profile: "HardwareProfile") -> dict:
    """Только то, что нужно для разбора: без серийников и путей пользователя."""
    def g(obj, *names):
        for name in names:
            value = getattr(obj, name, None)
            if value not in (None, "", -1):
                return value
        return ""

    cpu = getattr(profile, "cpu", None)
    audio = getattr(profile, "audio", None)
    net = getattr(profile, "net", None)
    dgpu = getattr(profile, "dgpu", None)
    igpu = getattr(profile, "igpu", None)
    storage = getattr(profile, "storage", None)
    return {
        "platform": getattr(profile, "platform", ""),
        "board": " ".join(part for part in (getattr(profile, "board_vendor", ""),
                                            getattr(profile, "board_name", "")) if part),
        "cpu": g(cpu, "name"),
        "cpu_vendor": g(cpu, "vendor"),
        "cpu_generation": g(cpu, "generation"),
        "cpu_codename": g(cpu, "codename"),
        "igpu": g(igpu, "name"),
        "dgpu": g(dgpu, "name"),
        "audio_codec": g(audio, "codec"),
        "audio_layout": g(audio, "layout_id"),
        "ethernet": g(net, "eth_chipset"),
        "ethernet_name": g(net, "eth_name"),
        "wifi": g(net, "wifi_chipset"),
        "wifi_name": g(net, "wifi_name"),
        "bluetooth": g(net, "bt_chipset"),
        "nvme": bool(getattr(storage, "nvme_present", False)),
        "touchpad": getattr(profile, "touchpad_type", ""),
    }


def _notes(profile: "HardwareProfile") -> list[dict]:
    """Замечания анализатора по железу.

    ``ok`` означает «файлы собрались», а не «система поедет», поэтому в отчёт
    попадают и проблемы совместимости — иначе отчёт читается как успех.
    """
    from ..analyzer.engine import analyze_profile

    try:
        issues = analyze_profile(profile)
    except Exception:
        return []
    return [{"severity": i.sev_label, "code": i.code, "title": i.title}
            for i in issues][:10]


def _kext_notes(kexts: Optional[list]) -> list[dict]:
    """Конфликтующие кексты в самой сборке — по общему списку из analyzer.models."""
    from ..analyzer.models import KEXT_CONFLICTS

    names = {Path(str(k)).stem for k in (kexts or [])}
    notes = []
    for first, second, _ in KEXT_CONFLICTS:
        if first in names and second in names:
            notes.append({
                "severity": "error",
                "code": f"kext_conflict_{first.lower()}_{second.lower()}",
                "title": f"Конфликт кекстов: {first} и {second}",
            })
    return notes


def make_record(profile: "HardwareProfile", options=None, result=None,
                kexts: Optional[list] = None, config: bytes = b"",
                feature: str = "full", created: Optional[str] = None) -> dict:
    """Запись о сборке: железо, выбор, итог и отпечаток config.plist."""
    errors = [str(e) for e in (getattr(result, "errors", []) or [])]
    return {
        "schema": SCHEMA,
        "created": created or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "feature": feature,
        "macos": str(getattr(options, "target_macos", "") or ""),
        "ok": bool(getattr(result, "ok", False)),
        "errors": errors[:20],
        "warnings": [str(w) for w in (getattr(result, "warnings", []) or [])][:20],
        "notes": (_notes(profile) + _kext_notes(kexts))[:10],
        "kexts": sorted(str(k) for k in (kexts or [])),
        "config_sha256": hashlib.sha256(config).hexdigest() if config else "",
        "hardware": _hardware(profile),
    }


def save_record(record: dict) -> Path:
    """Кладёт запись в локальную базу и возвращает путь к файлу."""
    digest = hashlib.sha256(
        json.dumps(record.get("hardware", {}), sort_keys=True).encode("utf-8")
    ).hexdigest()[:8]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    path = store_dir() / f"{stamp}-{digest}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def all_records() -> list[dict]:
    """Все локальные отчёты, свежие первыми."""
    items = []
    for file in sorted(store_dir().glob("*.json"), reverse=True):
        try:
            items.append(load(file))
        except (OSError, ValueError):
            continue
    return items


def stats() -> dict:
    records = all_records()
    return {
        "total": len(records),
        "ok": sum(1 for r in records if r.get("ok")),
        "failed": sum(1 for r in records if not r.get("ok")),
        "hardware": len({_profile_digest_from(r) for r in records}),
    }


def _profile_digest_from(record: dict) -> str:
    raw = json.dumps(record.get("hardware", {}), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _blocker_word(count: int) -> str:
    """Русское согласование: 1 замечание, 2 замечания, 5 замечаний."""
    if count % 10 == 1 and count % 100 != 11:
        return "блокирующее замечание"
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return "блокирующих замечания"
    return "блокирующих замечаний"


def issue_url(record: dict, repo: str = REPO) -> str:
    """Ссылка на новую задачу GitHub с заполненным отчётом."""
    hw = record.get("hardware", {})
    verdict = "ok" if record.get("ok") else "fail"
    title = f"[{verdict}] {hw.get('cpu', 'CPU')} · {hw.get('dgpu') or hw.get('igpu') or 'GPU'}"
    if record.get("macos"):
        title += f" · {record['macos']}"
    title = title[:TITLE_LIMIT]

    notes = record.get("notes") or []
    blockers = [n for n in notes if n.get("severity") == "error"]
    verdict_line = "сборка прошла" if record.get("ok") else "сборка не удалась"
    if record.get("ok") and blockers:
        count = len(blockers)
        verdict_line += (f", но железо не заработает: "
                         f"{count} {_blocker_word(count)}")
    marks = {"error": "✖", "warning": "⚠", "info": "·"}
    note_lines = [f"- {marks.get(n.get('severity'), '·')} {n.get('title', '')}"
                  for n in notes]

    body = "\n".join((
        "Отчёт HackicLab (сформирован автоматически).",
        "",
        f"- Итог: {verdict_line}",
        *note_lines,
        f"- macOS: {record.get('macos') or '—'}",
        f"- Платформа: {hw.get('platform') or '—'}",
        f"- Плата: {hw.get('board') or '—'}",
        f"- CPU: {hw.get('cpu') or '—'} ({hw.get('cpu_codename') or '—'})",
        f"- GPU: {hw.get('dgpu') or hw.get('igpu') or '—'}",
        f"- Аудио: {hw.get('audio_codec') or '—'} (layout {hw.get('audio_layout') or '—'})",
        f"- Ethernet: {hw.get('ethernet_name') or hw.get('ethernet') or '—'}",
        f"- Wi-Fi: {hw.get('wifi_name') or hw.get('wifi') or '—'}",
        f"- Кексты: {', '.join(record.get('kexts', [])[:40]) or '—'}",
        "",
        "```json",
        json.dumps(record, ensure_ascii=False, indent=1)[:JSON_LIMIT],
        "```",
    ))
    body = body[:BODY_LIMIT]
    query = urllib.parse.urlencode({"title": title, "body": body, "labels": LABEL})
    return f"https://github.com/{repo}/issues/new?{query}"


def open_issue(record: dict) -> bool:
    """Открывает браузер на странице новой задачи с отчётом."""
    try:
        return bool(webbrowser.open(issue_url(record)))
    except Exception:
        return False


def record_from_result(profile: "HardwareProfile", options=None, result=None,
                       kexts: Optional[list] = None, config: bytes = b"",
                       feature: str = "full") -> Path:
    """Собирает и сохраняет запись за один вызов."""
    return save_record(make_record(profile, options=options, result=result,
                                   kexts=kexts, config=config, feature=feature))


def parse_issue_body(body: str) -> Optional[dict]:
    """Достаёт JSON-отчёт из тела задачи (между ```json и ```)."""
    start = body.find("```json")
    if start < 0:
        return None
    start = body.find("\n", start) + 1
    end = body.find("```", start)
    if end < 0:
        return None
    try:
        data = json.loads(body[start:end])
    except ValueError:
        return None
    return data if isinstance(data, dict) and "hardware" in data else None


def parse_issues(payload: str) -> list[dict]:
    """Разбирает ответ API со списком задач в записи о сборках."""
    try:
        issues = json.loads(payload)
    except ValueError:
        return []
    if not isinstance(issues, list):
        return []
    records = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        record = parse_issue_body(str(issue.get("body") or ""))
        if record:
            record["issue"] = issue.get("number")
            record["issue_url"] = issue.get("html_url", "")
            record["issue_title"] = issue.get("title", "")
            records.append(record)
    return records


def fetch_reports(repo: str = REPO, limit: int = 50) -> list[dict]:
    """Читает отчёты из трекера (задачи с меткой) — для разбора и базы."""
    from ..builder.fetcher import download_bytes

    url = (f"https://api.github.com/repos/{repo}/issues"
           f"?labels={LABEL}&state=all&per_page={max(1, min(limit, 100))}")
    try:
        payload = download_bytes(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "HackicLab"}).decode("utf-8")
    except Exception:
        return []
    return parse_issues(payload)


def as_plain(record: dict) -> dict:
    """Копия записи для интерфейса (без служебных полей)."""
    plain = dict(record)
    plain.pop("config_sha256", None)
    return {k: (asdict(v) if hasattr(v, "__dataclass_fields__") else v)
            for k, v in plain.items()}
