"""Генерация SMBIOS-полей: Serial, MLB, SystemUUID, ROM под выбранную модель.

Формат серийного номера — 12 символов нового образца: место сборки (3),
год (1), неделя (1), линия (3), код продукта (4). Год и неделя согласованы:
первая половина года даёт недели 1–26, вторая — 27–53. Используется base34
без букв I и O, как в серийных номерах Apple.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass


@dataclass
class SMBIOSData:
    serial: str = ""
    mlb: str = ""
    system_uuid: str = ""
    rom: str = ""            # 6-байтовый MAC-like hex
    model: str = ""          # MacPro7,1 и т.д.


# Правдоподобные заводские префиксы по семейству модели.
PLANT_PREFIXES = {
    "MacBookPro": ("C02", "CO7", "C1M", "C1Q", "C2FL", "C2G7"),
    "MacBookAir": ("C02", "COV", "C1X", "C22", "C2JZ"),
    "iMac": ("C02", "C02JK", "C02N4", "C03K", "C04Z"),
    "MacPro": ("C02", "C07", "C0XM", "C1ZX", "C2QN"),
    "Macmini": ("C02", "C07N", "C0XW", "C1X6"),
}

_BASE34 = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ"

# Год в новом формате: пара символов — первая и вторая половина года.
_YEAR_HALVES = {
    2010: ("C", "D"), 2011: ("F", "G"), 2012: ("H", "J"), 2013: ("K", "L"),
    2014: ("M", "N"), 2015: ("P", "Q"), 2016: ("R", "S"), 2017: ("T", "V"),
    2018: ("W", "X"), 2019: ("Y", "Z"), 2020: ("C", "D"), 2021: ("F", "G"),
}

# Неделя: символ базы 34, первая половина года — 1–26, вторая — 27–53.
_WEEK_FIRST = "123456789" + "CDFGHJKLMNPQRTVWX"
_WEEK_SECOND = "123456789" + "CDFGHJKLMNPQRTVWXY"

_SERIAL_LEN = 12
_MLB_LEN = 17


def _plant(model: str) -> str:
    family = model.split(",")[0].strip()
    return random.choice(PLANT_PREFIXES.get(family, PLANT_PREFIXES["MacPro"]))


def _year_week(year: int | None = None) -> tuple[str, str]:
    """Символ года и согласованный символ недели."""
    year = year or random.choice(sorted(_YEAR_HALVES))
    first, second = _YEAR_HALVES[year]
    if random.random() < 0.5:
        return first, random.choice(_WEEK_FIRST)
    return second, random.choice(_WEEK_SECOND)


def _code(length: int) -> str:
    return "".join(random.choice(_BASE34) for _ in range(length))


def _serial(model: str) -> str:
    year_char, week_char = _year_week()
    return f"{_plant(model)}{year_char}{week_char}{_code(3)}{_code(4)}"[:_SERIAL_LEN]


def _mlb(model: str, serial: str) -> str:
    plant = _plant(model)
    need = _MLB_LEN - len(plant)
    body = (serial * 2)[:need]
    if len(body) < need:
        body += _code(need - len(body))
    return plant + body


def _rom() -> str:
    first = random.randrange(0, 254, 2)          # чётный старший байт — unicast
    rest = bytes(random.getrandbits(8) for _ in range(5))
    return (bytes([first]) + rest).hex()


def generate_smbios(model: str) -> SMBIOSData:
    """Полный набор SMBIOS для указанной модели Mac."""
    serial = _serial(model)
    return SMBIOSData(
        serial=serial,
        mlb=_mlb(model, serial),
        system_uuid=str(uuid.uuid4()).upper(),
        rom=_rom(),
        model=model,
    )
