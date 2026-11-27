"""Thunderbolt в macOS: контроллеры, требования и ограничения.

Опирается на Dortania (Hardware Limitations → Thunderbolt USB-C ports и
Fixing Sleep → Fixing Thunderbolt), треды tonymacx86 про Maple Ridge и опыт
сборок на ASUS Z790. Коротко: устройства на шине видны, но горячее
подключение и сон уживаются плохо — это ограничение macOS, а не сборки.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Controller:
    """Контроллер Thunderbolt и что с ним в macOS."""

    key: str            # подстрока в названии устройства
    name: str           # человеческое имя
    standard: str       # TB3 / TB4
    macos_min: str      # с какой macOS работает (по сообществу)
    ru: str
    en: str
    extra: tuple[str, ...] = ()   # другие обозначения в названии (номер чипа и т. п.)


CONTROLLERS: tuple[Controller, ...] = (
    Controller(
        "maple ridge", "Intel JHL8540 Maple Ridge (Thunderbolt 4)", "TB4", "Big Sur",
        "Устройства на шине работают, но горячее подключение требует SSDT с "
        "принудительным питанием и Notify (метод osy): без него — только холодная "
        "загрузка с уже подключённым устройством. Сон и TB вместе, как правило, "
        "не уживаются.",
        "Bus devices work, but hot-plug needs an SSDT with forced power and "
        "Notify (the osy method): without it only a cold boot with the device "
        "already attached. Sleep and TB usually do not coexist.",
        extra=("jhl8540", "8540"),
    ),
    Controller(
        "titan ridge", "Intel JHL7540 Titan Ridge (Thunderbolt 3)", "TB3", "Catalina",
        "Самый предсказуемый в macOS: карта расширения с прошивкой под Mac "
        "(например, GC-Titan Ridge с прошивкой 50) даёт и устройства, и hot-plug.",
        "The most predictable in macOS: an add-in card with Mac firmware (e.g. "
        "GC-Titan Ridge with firmware 50) gives both devices and hot-plug.",
        extra=("jhl7540", "7540"),
    ),
    Controller(
        "alpine ridge", "Intel JHL6540 Alpine Ridge (Thunderbolt 3)", "TB3",
        "High Sierra",
        "Старый контроллер: работает частично, hot-plug и DisplayPort-выход "
        "нестабильны — для рабочих задач его лучше не брать.",
        "An old controller: works partially, hot-plug and DisplayPort output are "
        "unstable — not the pick for real work.",
        extra=("jhl6540", "6540"),
    ),
)

#: Что нужно включить, чтобы AppleVTD заработал (без него TB-устройства не видят PCIe).
REQUIREMENTS: tuple[tuple[str, str], ...] = (
    ("BIOS: VT-d включён (Intel Virtualization Technology for Directed I/O)",
     "BIOS: VT-d enabled (Intel Virtualization Technology for Directed I/O)"),
    ("OpenCore: Kernel → Quirks → DisableIoMapper = false (AppleVTD вместо обхода)",
     "OpenCore: Kernel → Quirks → DisableIoMapper = false (AppleVTD instead of bypass)"),
    ("OpenCore: SSDT-DTBT или SSDT-TB3 для питания и hot-plug (иначе — холодная загрузка)",
     "OpenCore: SSDT-DTBT or SSDT-TB3 for power and hot-plug (else cold boot only)"),
    ("Память больше 16 ГБ: при проблемах с TB/сетью — патченный DMAR и DisableIoMapperMapping",
     "More than 16 GB RAM: on TB/network trouble — patched DMAR and DisableIoMapperMapping"),
)

#: Ограничения, о которых стоит предупредить сразу.
LIMITS: tuple[tuple[str, str], ...] = (
    ("Сон вместе с Thunderbolt часто ломается: паника или отвал USB-C после пробуждения.",
     "Sleep with Thunderbolt often breaks: kernel panic or USB-C dying after wake."),
    ("Распаянный на плате контроллер не заменить на Titan Ridge — только этот чип.",
     "An on-board controller cannot be swapped for a Titan Ridge — you get this chip only."),
    ("eGPU на TB в macOS не поддерживается штатно даже на поддерживаемых картах.",
     "TB eGPUs are not supported in macOS out of the box, even with supported cards."),
)


def controller_for(name: str) -> Controller | None:
    """Ищет контроллер по названию устройства из сканирования."""
    low = (name or "").lower()
    for controller in CONTROLLERS:
        if controller.key in low or any(alias in low for alias in controller.extra):
            return controller
    return None


def note_for(name: str) -> dict[str, str]:
    """Заметка о контроллере: {'ru': ..., 'en': ...} или пусто."""
    controller = controller_for(name)
    if controller is None:
        return {}
    return {
        "ru": f"{controller.name}: {controller.ru}",
        "en": f"{controller.name}: {controller.en}",
    }


def is_apple_vtd_required() -> bool:
    """AppleVTD нужен для любой работы Thunderbolt в macOS."""
    return True
