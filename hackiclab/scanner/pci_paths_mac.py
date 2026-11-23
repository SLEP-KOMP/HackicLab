"""UEFI-пути PCI на macOS из IORegistry.

Прошивка адресует устройства путём UEFI, а macOS отдаёт его же в свойстве
``device-path`` узлов IODeviceTree — в виде последовательности UEFI-узлов
(ACPI PciRoot и PCI). Переводим её в привычную строку
``PciRoot(0x0)/Pci(0x8,0x1)/Pci(0x0,0x4)`` — ту же, что нужна DeviceProperties.
"""

from __future__ import annotations

import plistlib
import re
from typing import Optional

# Имена узлов IORegistry, под которыми обычно живут нужные контроллеры.
AUDIO_NODES = ("HDEF", "HDAS", "AZAL")
ETHERNET_NODES = ("GIGE", "ETH0", "ETH1", "PXSX")
WIFI_NODES = ("ARPT", "WL1", "WLAN", "WIFI", "PXSX")


def uefi_path_from_hex(raw: str) -> str:
    """Переводит hex-строку device-path в текст UEFI; пусто, если не разобрать."""
    try:
        data = bytes.fromhex(re.sub(r"[\s<>]", "", raw))
    except ValueError:
        return ""
    parts: list[str] = []
    pos = 0
    while pos + 4 <= len(data):
        node_type, _subtype = data[pos], data[pos + 1]
        length = int.from_bytes(data[pos + 2:pos + 4], "little")
        if node_type == 0x7F or length < 4 or pos + length > len(data):
            break
        body = data[pos + 4:pos + length]
        if node_type == 0x02 and len(body) >= 8:          # ACPI: PciRoot(UID)
            uid = int.from_bytes(body[4:8], "little")
            parts.append(f"PciRoot(0x{uid:x})")
        elif node_type == 0x01 and len(body) >= 2:        # PCI: function, device
            function, device = body[0], body[1]
            parts.append(f"Pci(0x{device:x},0x{function:x})")
        pos += length
    return "/".join(parts)


def parse_nodes(nodes: list) -> dict[str, str]:
    """Собирает имя узла -> UEFI-путь из вывода ``ioreg -a``."""
    result: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        name = str(node.get("IORegistryEntryName") or "")
        raw = node.get("device-path")
        if not name or not isinstance(raw, (bytes, bytearray)):
            continue
        path = uefi_path_from_hex(raw.hex())
        if path:
            result.setdefault(name, path)
    return result


def pick(paths: dict[str, str], prefixes: tuple[str, ...]) -> str:
    """Первый путь, чьё имя узла начинается с одного из префиксов."""
    for prefix in prefixes:
        for name, path in paths.items():
            if name.upper().startswith(prefix):
                return path
    return ""


def paths() -> dict[str, str]:
    """Читает IODeviceTree через ioreg и возвращает карту путей."""
    from ..proc import run

    try:
        done = run(["ioreg", "-a", "-p", "IODeviceTree", "-l", "-w0"],
                   capture_output=True, timeout=60)
        if done.returncode != 0:
            return {}
        payload = plistlib.loads(done.stdout.encode("utf-8", "replace"))
    except Exception:
        return {}
    if not isinstance(payload, list):
        return {}
    return parse_nodes(payload)


def device_paths() -> tuple[str, str, str]:
    """Пути аудио, Ethernet и Wi-Fi (пустая строка, если не нашли)."""
    table = paths()
    return (
        pick(table, AUDIO_NODES),
        pick(table, ETHERNET_NODES),
        pick(table, WIFI_NODES),
    )


def find_node(nodes: list, name_prefix: str) -> Optional[dict]:
    """Узел по началу имени — вспомогательное для отладки и тестов."""
    for node in nodes:
        if isinstance(node, dict) and str(node.get("IORegistryEntryName") or "") \
                .upper().startswith(name_prefix):
            return node
    return None
