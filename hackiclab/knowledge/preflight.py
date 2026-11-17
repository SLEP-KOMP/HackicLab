"""Предполётная проверка BIOS/UEFI — перенос этапа «Before Using EFI» из OpCore-Simplify.

Смысл: до записи EFI показать пользователю, что нужно включить или выключить
в прошивке, чтобы OpenCore вообще стартовал.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..scanner.models import HardwareProfile


@dataclass
class BiosState:
    firmware: str = "Unknown"      # UEFI / Legacy / Unknown
    secure_boot: str = "Unknown"   # Enabled / Disabled / Unsupported / Unknown
    above_4g: str = "Unknown"      # детект невозможен без прошивки
    resizable_bar: str = "Unknown"


@dataclass
class PreflightReport:
    firmware: str = "Unknown"
    secure_boot: str = "Unknown"
    requirements: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.requirements


def detect_bios_state() -> BiosState:
    """Считывает режим прошивки и Secure Boot через PowerShell."""
    from ..scanner.powershell import ps

    state = BiosState()
    raw = ps.run("(Get-ComputerInfo).BiosFirmwareType")
    value = (raw or "").strip().lower()
    if "uefi" in value:
        state.firmware = "UEFI"
    elif "bios" in value or "legacy" in value:
        state.firmware = "Legacy"

    secure = ps.run(
        "try { if (Confirm-SecureBootUEFI -ErrorAction Stop) { 'Enabled' } else { 'Disabled' } } "
        "catch { 'Unsupported' }"
    )
    answer = (secure or "").strip().lower()
    if answer in ("enabled", "disabled"):
        state.secure_boot = answer.capitalize()
    elif "unsupported" in answer:
        state.secure_boot = "Unsupported"
    return state


def bios_requirements(profile: HardwareProfile, state: BiosState | None = None) -> PreflightReport:
    """Список действий в BIOS по состоянию железа и прошивки.

    Формулировки совпадают с рекомендациями OpCore-Simplify, но проверяем
    только то, что реально можем определить из Windows.
    """
    state = state or BiosState()
    report = PreflightReport(firmware=state.firmware, secure_boot=state.secure_boot)

    if state.firmware != "UEFI":
        report.requirements.append("bios.uefi")
    if state.secure_boot != "Disabled":
        report.requirements.append("bios.secure_boot")

    cpu_generation = int(getattr(profile.cpu, "generation", 0) or 0)
    modern_intel = profile.cpu.vendor == "intel" and cpu_generation >= 11
    if profile.platform == "desktop" and modern_intel:
        report.requirements.append("bios.above4g")
        report.requirements.append("bios.rebar")

    # VT-d и CFG Lock чаще всего мешают старту, даже если их не видно из Windows
    report.requirements.append("bios.vtd")
    report.requirements.append("bios.cfg_lock")
    return report
