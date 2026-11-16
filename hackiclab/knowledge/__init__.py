"""Модуль базы знаний: кексты, OpenCore-платформы, SSDT, патчи."""

from .kexts import KEXT_DB, KextEntry, kext_sources_ok, select_kexts
from .oc_platforms import OC_PLATFORMS
from .ssdt_logics import SSDT_DB, required_ssdts

__all__ = [
    "KEXT_DB",
    "OC_PLATFORMS",
    "SSDT_DB",
    "KextEntry",
    "kext_sources_ok",
    "required_ssdts",
    "select_kexts",
]
