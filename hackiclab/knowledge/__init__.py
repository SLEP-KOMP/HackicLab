"""Модуль базы знаний: кексты, OpenCore-платформы, SSDT, патчи."""

from .kexts import KextEntry, KEXT_DB, select_kexts, kext_sources_ok
from .oc_platforms import OC_PLATFORMS
from .ssdt_logics import SSDT_DB, required_ssdts

__all__ = [
    "KextEntry",
    "KEXT_DB",
    "select_kexts",
    "kext_sources_ok",
    "OC_PLATFORMS",
    "SSDT_DB",
    "required_ssdts",
]