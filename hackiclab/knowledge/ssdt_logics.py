"""Логика требуемых SSDT-таблиц и шаблонов патчей ACPI.

SSDT = таблицы ACPI, генерируемые из реального DSDT либо из встроенных шаблонов.
Логика выбора адаптирована из SSDTTime и hackmate (ssdt.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..scanner.models import HardwareProfile


@dataclass
class SSDTSpec:
    name: str
    label: str
    desc: str
    template: bool = True        # можно собрать из DSL-шаблона (иначе нужен SSDTTime/DSDT)
    bundled: bool = True         # есть встроенный .aml фолбэк
    conditions: str = ""         # текстовое описание условия применения


SSDT_DB: list[SSDTSpec] = [
    SSDTSpec("SSDT-PLUG", "Power management (plugin-type)", "Включает CPU power management — нужен почти всем Intel.", template=True, bundled=True),
    SSDTSpec("SSDT-PLUG-AMD", "Power management (AMD)", "Plugin-type для Ryzen: собирается из DSL-шаблона, готового .aml нет.", template=True, bundled=False),
    SSDTSpec("SSDT-GPRW", "Sleep fix (GPRW)", "Патч GPRW/PRW — сон и пробуждение ноутбуков.", template=False, bundled=True),
    SSDTSpec("SSDT-IMEI", "IMEI device", "Добавляет IMEI на платах без него (Sandy/Ivy Bridge).", template=False, bundled=True),
    SSDTSpec("SSDT-EC", "Fake EC (desktop)", "Фейковый Embedded Controller для desktop — обязателен.", template=True, bundled=True),
    SSDTSpec("SSDT-EC-USBX", "Fake EC + USB power (laptop)", "Фейковый EC + силы USB для ноутбуков.", template=True, bundled=True),
    SSDTSpec("SSDT-PNLF", "Backlight (laptop)", "Управление яркостью экрана — только для ноутбуков.", template=True, bundled=True),
    SSDTSpec("SSDT-AWAC", "AWAC → RTC", "Переключение AWAC-часов на RTC (обычно 300-серия и новее).", template=True, bundled=True),
    SSDTSpec("SSDT-XOSI", "_OSI compatibility", "Возвращает 'Windows'-ответы для ACPI-совместимости.", template=True, bundled=True),
    SSDTSpec("SSDT-HPET", "Fix IRQ conflicts", "Убирает IRQ-конфликты HPET — часто нужен на ноутбуках.", template=True, bundled=True),
    SSDTSpec("SSDT-PMC", "PMCR (300-series)", "Добавляет устройство PMCR для нативной NVRAM на 300-серии.", template=True, bundled=True),
    SSDTSpec("SSDT-USBX", "USB power properties", "Базовые свойства питания USB.", template=True, bundled=True),
    SSDTSpec("SSDT-GPI0", "GPIO (laptop)", "Разблокирует GPIO для I2C-тачпадов.", template=True, bundled=True),
]


def required_ssdts(profile: HardwareProfile) -> list[SSDTSpec]:
    """Список SSDT, нужных данному профилю.

    В EFI попадают только применимые таблицы: PMC — Intel 300-серии,
    GPI0/PNLF — ноутбуки, PLUG — только Intel. Лишние .aml в ACPI
    сбивают с толку и не регистрируются в config.plist.
    """
    amd = (profile.cpu.vendor or "").lower() == "amd"
    laptop = profile.platform == "laptop"

    names: list[str] = ["SSDT-PLUG-AMD" if amd else "SSDT-PLUG"]
    if laptop:
        names += ["SSDT-EC-USBX", "SSDT-PNLF", "SSDT-HPET", "SSDT-XOSI", "SSDT-GPI0"]
    else:
        names += ["SSDT-EC", "SSDT-USBX"]
        if not amd:
            names.append("SSDT-AWAC")
            if profile.platform in ("desktop", "workstation", "mini"):
                names.append("SSDT-PMC")
    by_name = {s.name: s for s in SSDT_DB}
    return [by_name[n] for n in names if n in by_name]
