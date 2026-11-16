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
    """Список SSDT, нужных данному профилю."""
    specs = list(SSDT_DB)
    # Логика отбора не влияет на сам список при текущей простоте модели — все идут,
    # финальное решение о применении принимает сборщик по DSDT/условиям.
    return specs
