"""Генерация SMBIOS-данных: Serial, MLB, SystemUUID, ROM.

Логика форматов адаптирована из hackmate (smbios.py) и GenSMBIOS/macserial.
"""

from __future__ import annotations

import random
import string
import uuid
from dataclasses import dataclass
from pathlib import Path

from .cache_manager import app_home


@dataclass
class SMBIOSData:
    serial: str = ""
    mlb: str = ""
    system_uuid: str = ""
    rom: str = ""            # 6-байтовый MAC-like hex
    model: str = ""          # MacPro7,1 и т.д.


# 3-4 буквенных префикса MLB на модель (для реалистичности)
MLB_PREFIXES = {
    "MacBookPro": ["C02", "CO7", "C1M", "C1Q", "C2FL", "C2G7"],
    "MacBookAir": ["C02", "COV", "C1X", "C22", "C2JZ"],
    "iMac":       ["C02", "C02JK", "C02N4", "C03K", "C04Z"],
    "MacPro":     ["C02", "C07", "C0XM", "C1ZX", "C2QN"],
    "Macmini":    ["C02", "C07N", "C0XW", "C1X6"],
}

_ALPHA = "ABCDEFGHJKLMNPQRSTUVWXYZ"   # без I, O — как Apple
_DIGITS = "0123456789"
_MIXED = _ALPHA + _DIGITS


def _serial_for(model: str) -> str:
    """Серийник Apple: 11-12 символов, формат региональный+сборка."""
    # Формат: XXY ZZZZ Z // префикс + год-неделя (2) + код завода (1) + рандом
    prefix = "C02" if model.startswith(("Mac", "iMac")) else "C02"
    year_week = random.choice(string.digits) + random.choice(string.digits + _ALPHA)
    line = random.choice("ABCDEFGHJKMNP")
    mid = "".join(random.choice(_MIXED) for _ in range(4))
    return f"{prefix}{year_week}{line}{mid}"


def _mlb_for(model: str, serial: str) -> str:
    """MLB: 17 символов, формат: заводской префикс + серийник + контрольные символы."""
    pre = random.choice(MLB_PREFIXES.get(model.split(",")[0], MLB_PREFIXES["MacPro"]))
    # Строим MLB так, чтобы по длине совпадал с ожидаемым для модели
    budget = 17 - len(pre)
    if budget < 8:
        pre = pre[: max(4, 17 - 8)]
        budget = 17 - len(pre)
    tail = serial[:budget]
    extra = "".join(random.choice(_MIXED) for _ in range(max(0, budget - len(tail))))
    return (pre + tail + extra)[:17]


def generate_smbios(model: str) -> SMBIOSData:
    """Генерирует полный набор SMBIOS для данной модели Mac."""
    d = SMBIOSData(model=model)
    d.serial = _serial_for(model)
    d.mlb = _mlb_for(model, d.serial)
    d.system_uuid = str(uuid.uuid4()).upper()
    # ROM — 6 байт, первый байт принудительно чётный (unicast MAC)
    rom_bytes = bytes([random.randrange(0, 255, 2)]) + bytes(random.getrandbits(8) for _ in range(5))
    d.rom = rom_bytes.hex()
    return d