"""Какие SSDT-таблицы нужны профилю и откуда их брать.

SSDT — таблицы ACPI: часть собирается из DSL-шаблона, часть кладётся готовым
`.aml` из `assets/ssdt`, а что-то строится SSDTTime по DSDT конкретной платы.
В EFI попадают только применимые таблицы: лишний `.aml` без записи в
`ACPI > Add` лишь мешает, а запись без файла ломает загрузку.
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
    SSDTSpec("SSDT-PLUG", "Power management (plugin-type)",
             "Включает CPU power management — нужен почти всем Intel."),
    SSDTSpec("SSDT-PLUG-AMD", "Power management (AMD)",
             "Plugin-type для Ryzen: собирается из DSL-шаблона, готового .aml нет.",
             template=True, bundled=False),
    SSDTSpec("SSDT-GPRW", "Sleep fix (GPRW)",
             "Патч GPRW/PRW — сон и пробуждение ноутбуков.", template=False),
    SSDTSpec("SSDT-IMEI", "IMEI device",
             "Добавляет IMEI на платах без него (Sandy/Ivy Bridge).", template=False),
    SSDTSpec("SSDT-EC", "Fake EC (desktop)",
             "Фейковый Embedded Controller для desktop — обязателен."),
    SSDTSpec("SSDT-EC-USBX", "Fake EC + USB power (laptop)",
             "Фейковый EC + силы USB для ноутбуков."),
    SSDTSpec("SSDT-PNLF", "Backlight (laptop)",
             "Управление яркостью экрана — только для ноутбуков."),
    SSDTSpec("SSDT-AWAC", "AWAC → RTC",
             "Переключение AWAC-часов на RTC (обычно 300-серия и новее)."),
    SSDTSpec("SSDT-XOSI", "_OSI compatibility",
             "Возвращает 'Windows'-ответы для ACPI-совместимости."),
    SSDTSpec("SSDT-HPET", "Fix IRQ conflicts",
             "Убирает IRQ-конфликты HPET — часто нужен на ноутбуках."),
    SSDTSpec("SSDT-PMC", "PMCR (300-series)",
             "Добавляет устройство PMCR для нативной NVRAM на 300-серии."),
    SSDTSpec("SSDT-USBX", "USB power properties",
             "Базовые свойства питания USB."),
    SSDTSpec("SSDT-GPI0", "GPIO (laptop)",
             "Разблокирует GPIO для I2C-тачпадов."),
    SSDTSpec("SSDT-USB-Reset", "USB reset (RHUB)",
             "Гасит корневой хаб RHUB, чтобы macOS поднял порты заново; "
             "собирается по DSDT, готового .aml нет.",
             template=True, bundled=False,
             conditions="В DSDT есть Device (RHUB) — обычно Intel Skylake и новее."),
]

_BY_NAME = {spec.name: spec for spec in SSDT_DB}


def required_ssdts(profile: HardwareProfile) -> list[SSDTSpec]:
    """Применимые к профилю таблицы в порядке загрузки.

    Ноутбукам нужен EC-USBX вместо EC и добавляются PNLF, HPET, XOSI, GPI0;
    десктопам — EC и USBX, у Intel ещё AWAC, а на 300-серии и PMCR.
    AMD получает PLUG-AMD без AWAC: часов AWAC на этих платах нет.
    """
    amd = (profile.cpu.vendor or "").lower() == "amd"
    laptop = profile.platform == "laptop"

    names = ["SSDT-PLUG-AMD"] if amd else ["SSDT-PLUG"]
    if laptop:
        names.extend(("SSDT-EC-USBX", "SSDT-PNLF", "SSDT-HPET", "SSDT-XOSI", "SSDT-GPI0"))
    else:
        names.extend(("SSDT-EC", "SSDT-USBX"))
        if not amd:
            names.append("SSDT-AWAC")
            if profile.platform in ("desktop", "workstation", "mini"):
                names.append("SSDT-PMC")

    # Собирается только при наличии RHUB в DSDT: без него генератор вернёт
    # пустоту, и таблица просто не попадёт в ACPI.
    names.append("SSDT-USB-Reset")

    return [_BY_NAME[name] for name in names if name in _BY_NAME]
