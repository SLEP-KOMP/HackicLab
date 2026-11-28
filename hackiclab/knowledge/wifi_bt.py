"""Совместимость Wi-Fi/Bluetooth: чипсет -> кексты и ограничения."""

from __future__ import annotations

#: (подстрока в названии, Wi-Fi, Bluetooth, заметка RU, заметка EN)
CHIPSETS: tuple[tuple[str, str, str, str, str], ...] = (
    ("ax211", "itlwm / AirportItlwm", "IntelBluetoothFirmware",
     "AX211 (CNVi): Wi-Fi через itlwm; AirportItlwm на Sequoia и Tahoe — сборка "
     "с OCLP-патчем. BT (USB 8087:0033) через IntelBluetoothFirmware + "
     "IntelBTPatcher + BlueToolFixup. AirDrop не будет; в тот же слот M.2 "
     "встаёт BCM94360NG, если нужен нативный Wi-Fi.",
     "AX211 (CNVi): Wi-Fi via itlwm; AirportItlwm on Sequoia and Tahoe needs an "
     "OCLP-patched build. BT (USB 8087:0033) via IntelBluetoothFirmware + "
     "IntelBTPatcher + BlueToolFixup. No AirDrop; BCM94360NG fits the same M.2 "
     "slot if you want native Wi-Fi."),
    ("ax210", "itlwm / AirportItlwm", "IntelBluetoothFirmware",
     "AX210 работает через itlwm (или нативный AirportItlwm), BT — IntelBluetoothFirmware.",
     "AX210 works via itlwm (or native AirportItlwm), BT via IntelBluetoothFirmware."),
    ("ax200", "itlwm / AirportItlwm", "IntelBluetoothFirmware",
     "AX200: Wi-Fi через itlwm, BT через IntelBluetoothFirmware.",
     "AX200: Wi-Fi via itlwm, BT via IntelBluetoothFirmware."),
    ("9560", "itlwm / AirportItlwm", "IntelBluetoothFirmware",
     "9560: Wi-Fi и BT через кексты OpenIntelWireless.",
     "9560: Wi-Fi and BT via OpenIntelWireless kexts."),
    ("8265", "itlwm / AirportItlwm", "IntelBluetoothFirmware",
     "8265: рабочий вариант, нужен HeliPort для itlwm.",
     "8265: known working, HeliPort needed for itlwm."),
    ("7260", "itlwm / AirportItlwm", "IntelBluetoothFirmware",
     "7260: Wi-Fi через itlwm, BT часто без прошивки — проверяйте.",
     "7260: Wi-Fi via itlwm, BT often lacks firmware — verify."),
    ("bcm94360", "AirportBrcmFixup", "BrcmPatchRAM3",
     "BCM94360 нативно до Ventura; с Sonoma 14+ нужен набор OCLP (IOSkywalk).",
     "BCM94360 native up to Ventura; Sonoma 14+ needs the OCLP set (IOSkywalk)."),
    ("bcm94352", "AirportBrcmFixup", "BrcmPatchRAM3",
     "BCM94352: AirportBrcmFixup + BrcmPatchRAM для BT.",
     "BCM94352: AirportBrcmFixup + BrcmPatchRAM for BT."),
    ("ar928", "ATH9KFixup", "—",
     "Atheros AR928x: только Wi-Fi, BT нет.",
     "Atheros AR928x: Wi-Fi only, no BT."),
    ("mt792", "—", "—",
     "MediaTek MT792x не поддерживается macOS.",
     "MediaTek MT792x is unsupported by macOS."),
)


#: Чипсеты, для которых в macOS нет драйвера ни в каком виде.
UNSUPPORTED_CHIPSETS = frozenset({"mediatek", "realtek"})


def has_driver(chipset: str, name: str = "") -> bool:
    """Есть ли шанс завести этот Wi-Fi в macOS (по чипсету из сканера)."""
    chip = (chipset or "").strip().lower()
    if not chip:
        return True
    return chip not in UNSUPPORTED_CHIPSETS


def is_unsupported(chipset: str, name: str = "") -> bool:
    """Обратная проверка для интерфейса: «поддержки нет»."""
    return not has_driver(chipset, name)


def note_for(name: str) -> dict[str, str]:
    """Заметка по названию адаптера: {'ru': ..., 'en': ...} или пусто."""
    low = (name or "").lower()
    for key, wifi, bt, ru, en in CHIPSETS:
        if key in low:
            return {"ru": f"Wi-Fi: {wifi}; BT: {bt}. {ru}",
                    "en": f"Wi-Fi: {wifi}; BT: {bt}. {en}"}
    return {}


def all_chipsets() -> tuple[tuple[str, str, str], ...]:
    """Короткая таблица для отчётов: (чипсет, Wi-Fi, BT)."""
    return tuple((key.upper(), wifi, bt) for key, wifi, bt, _, _ in CHIPSETS)
