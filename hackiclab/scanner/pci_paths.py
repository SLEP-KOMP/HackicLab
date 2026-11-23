"""UEFI-пути PCI-устройств через PnP: PciRoot(0x0)/Pci(dev,func)/…

OpenCore адресует устройства путём UEFI, а не именем в Windows. Собираем его
из дерева PnP: у каждого PCI-устройства берём адрес (device<<16 | function)
и родителя, затем идём к корню. Так получается тот же путь, который видит
прошивка: ``PciRoot(0x0)/Pci(0x8,0x1)/Pci(0x0,0x4)``.
"""

from __future__ import annotations

import json
import subprocess
from typing import Optional

_PS_SCRIPT = r"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$out = @()
Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like 'PCI\*' } | ForEach-Object {
  $id = $_.InstanceId
  $addr = (Get-PnpDeviceProperty -InstanceId $id -KeyName 'DEVPKEY_Device_Address' -ErrorAction SilentlyContinue).Data
  $par = (Get-PnpDeviceProperty -InstanceId $id -KeyName 'DEVPKEY_Device_Parent' -ErrorAction SilentlyContinue).Data
  $out += [pscustomobject]@{ id = $id; addr = $addr; parent = $par; name = $_.FriendlyName }
}
$out | ConvertTo-Json -Compress
"""


def _run_ps() -> str:
    from ..proc import run  # локальный импорт: модуль не должен тянуть Qt

    done = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_SCRIPT],
               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return done.stdout or ""


def collect() -> list[dict]:
    """Список PCI-устройств с адресом и родителем (пусто при сбое)."""
    try:
        raw = _run_ps()
        data = json.loads(raw) if raw and raw.strip() else []
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    if isinstance(data, dict):
        data = [data]
    return [item for item in data if isinstance(item, dict) and item.get("id")]


def compose_path(instance: str, table: dict[str, dict], limit: int = 8) -> str:
    """UEFI-путь устройства по таблице PnP; пустая строка, если цепочка рвётся."""
    chain: list[tuple[int, int]] = []
    cur = table.get((instance or "").lower())
    steps = 0
    while cur and steps < limit:
        raw = cur.get("addr")
        try:
            addr = int(raw)
        except (TypeError, ValueError):
            addr = 0
        chain.append((addr >> 16, addr & 0xFFFF))
        cur = table.get(str(cur.get("parent") or "").lower())
        steps += 1
    if not chain or chain == [(0, 0)]:
        # одинокий адрес 0x0,0x0 — адрес не прочитался, путь бесполезен
        return ""
    chain.reverse()
    return "PciRoot(0x0)" + "".join(f"/Pci(0x{d:x},0x{f:x})" for d, f in chain)


def table(items: Optional[list[dict]] = None) -> dict[str, dict]:
    """Таблица PnP по ключу instance (в нижнем регистре)."""
    rows = collect() if items is None else items
    return {str(row.get("id", "")).lower(): row for row in rows}


def paths(items: Optional[list[dict]] = None) -> dict[str, str]:
    """Пути для всех устройств: instance -> PciRoot-путь."""
    rows = collect() if items is None else items
    lookup = table(rows)
    result = {}
    for row in rows:
        instance = str(row.get("id", ""))
        path = compose_path(instance, lookup)
        if path:
            result[instance.lower()] = path
    return result
