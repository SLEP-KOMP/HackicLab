"""Thunderbolt: какие контроллеры macOS знает и что для них нужно.

Официального списка Apple не публикует, поэтому модели собраны по PCI ID
(репозиторий pci-ids, отчёты lspci) и community-таблицам совместимости.
Правило: «работает» — Alpine Ridge и Titan Ridge; Maple Ridge (TB4) — только
холодная загрузка; TB5/USB4 v2 не подтверждены.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThunderboltModel:
    key: str
    ids: tuple[str, ...]
    name: str
    status: str      # "native" | "cold" | "unknown"
    ru: str
    en: str


CONTROLLERS: tuple[ThunderboltModel, ...] = (
    ThunderboltModel(
        "titan-ridge", ("15ea", "15eb", "15ef", "15f0"),
        "Titan Ridge (JHL7540 / JHL7440)",
        "native",
        "Titan Ridge работает в macOS; для hot-plug нужен SSDT под root port. "
        "Для видео нужен кабель DP → «DP IN» карты.",
        "Titan Ridge works in macOS; hot-plug needs an SSDT for the root port. "
        "Video requires a DP cable into the card's DP IN.",
    ),
    ThunderboltModel(
        "alpine-ridge", ("15d2", "15d3", "15d4", "15d9"),
        "Alpine Ridge (JHL6540 / JHL6340)",
        "native",
        "Alpine Ridge работает; hot-plug также требует SSDT. Без SSDT "
        "устройства видны только при загрузке с подключённым устройством.",
        "Alpine Ridge works; hot-plug also needs an SSDT. Without it devices "
        "are visible only when attached at boot.",
    ),
    ThunderboltModel(
        "maple-ridge", ("1136", "1137", "1138"),
        "Maple Ridge (JHL8540, Thunderbolt 4)",
        "cold",
        "Thunderbolt 4 в macOS: работает холодная загрузка с подключённым "
        "устройством, hot-plug обычно нет. Дерево шины требует правки прошивки карты.",
        "Thunderbolt 4 in macOS: cold boot with the device attached works, "
        "hot-plug usually not. Full bus tree needs modified card firmware.",
    ),
    ThunderboltModel(
        "goshen-ridge", ("15c0", "15c1"),
        "Goshen Ridge (JHL8440, TB4 hub)",
        "unknown",
        "Goshen Ridge как хост не встречается; поддержка не подтверждена.",
        "Goshen Ridge is not used as a host; support is unconfirmed.",
    ),
)


_BY_ID = {pid: model for model in CONTROLLERS for pid in model.ids}


def find_controller(ids) -> ThunderboltModel | None:
    """Контроллер по списку PCI device id (строки вида '15ea')."""
    for raw in ids or ():
        key = str(raw).strip().lower().replace("0x", "")
        if key.startswith("dev_"):
            key = key[4:]
        model = _BY_ID.get(key)
        if model is not None:
            return model
    return None


def model_name(model: ThunderboltModel | None) -> str:
    return model.name if model is not None else ""


def status_for(model: ThunderboltModel | None) -> str:
    return model.status if model is not None else "unknown"


def supported_models() -> tuple[ThunderboltModel, ...]:
    return tuple(m for m in CONTROLLERS if m.status in ("native", "cold"))
