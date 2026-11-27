"""Готовые строки карточки железа для интерфейса.

Отдельный модуль, потому что одинаковые строки нужны и на вкладке
«Сканирование», и в мастере быстрой сборки: подпись, значение и пояснение.
"""

from __future__ import annotations

import re
from typing import Optional

from ..i18n import tr
from ..scanner.models import HardwareProfile

_PLATFORM = {"laptop": "hw.platform.laptop", "desktop": "hw.platform.desktop",
             "mini": "hw.platform.mini", "workstation": "hw.platform.workstation"}

_VENDOR = {"intel": "Intel", "broadcom": "Broadcom", "atheros": "Atheros/Qualcomm",
           "realtek": "Realtek", "mediatek": "MediaTek", "amd": "AMD", "nvidia": "NVIDIA"}


def wifi_model(name: str, chipset: str = "") -> str:
    """Модель Wi-Fi из имени устройства: «MT7925» вместо общего «mediatek».

    Windows отдаёт полное имя адаптера («MediaTek Wi-Fi 7 MT7925 Wireless LAN
    Card»), поэтому модель вытаскиваем регуляркой, а вендора — из имени.
    """
    text = (name or "").strip()
    match = re.search(r"\b(MT\d{3,4}|AX\d{3,4}|AC\d{3,4}|BE\d{3,4}|BCM\d{4,5}|"
                      r"QCA\d{4}|RTL\d{4,5}|AR\d{4})\b", text, re.I)
    if match:
        return match.group(1).upper()
    low = text.lower()
    vendor = ""
    for key, label in _VENDOR.items():
        if key in low:
            vendor = label
            break
    if not vendor and chipset:
        vendor = _VENDOR.get(chipset.lower(), chipset.capitalize())
    return vendor


def _cpu_line(profile: HardwareProfile) -> tuple[str, str]:
    cpu = profile.cpu
    if not cpu or not cpu.name:
        return "—", ""
    bits = []
    if cpu.core_count:
        bits.append(f"{cpu.core_count}C/{cpu.thread_count or cpu.core_count}T")
    if cpu.generation:
        bits.append(f"gen {cpu.generation}")
    return cpu.name, " · ".join([b for b in bits if b])


def _gpu_line(profile: HardwareProfile) -> tuple[str, str]:
    parts = []
    for gpu in (profile.igpu, profile.dgpu):
        if gpu and gpu.name:
            label = gpu.name
            if gpu.device_id:
                label += f" [{gpu.device_id.upper()}]"
            parts.append(label)
    return ", ".join(parts) or "—", ""


def _audio_line(profile: HardwareProfile) -> tuple[str, str]:
    audio = profile.audio
    if not audio or not (audio.name or audio.codec):
        return "—", ""
    name = audio.name or audio.codec
    note = ""
    if audio.codec and audio.codec.lower() not in name.lower():
        note = audio.codec
    if audio.layout_id:
        note = (note + " · " if note else "") + f"layout {audio.layout_id}"
    return name, note


def _ethernet_line(profile: HardwareProfile) -> tuple[str, str]:
    net = profile.net
    name = net.eth_name or (net.eth_chipset.upper() if net.eth_chipset else "")
    if not name:
        return "—", ""
    note = net.eth_chipset if net.eth_name and net.eth_chipset else ""
    return name, note


def _wifi_line(profile: HardwareProfile) -> tuple[str, str]:
    net = profile.net
    model = wifi_model(net.wifi_name, net.wifi_chipset)
    name = net.wifi_name or model
    if not name:
        return "—", ""
    vendor = _VENDOR.get(net.wifi_chipset.lower(), net.wifi_chipset) if net.wifi_chipset else ""
    note = ""
    if vendor and vendor.lower() not in (net.wifi_name or "").lower():
        note = vendor
    if model and model.lower() not in (net.wifi_name or "").lower():
        note = f"{model} · {note}" if note else model
    ignored = [item for item in (net.ignored_wifi or []) if item]
    if ignored:
        extra = tr.t("hw.wifi.inactive") + ": " + ", ".join(ignored[:2])
        note = f"{note} · {extra}" if note else extra
    return name, note


def _bt_line(profile: HardwareProfile) -> tuple[str, str]:
    net = profile.net
    if not net.has_bt and not net.bt_chipset:
        return "—", ""
    if net.bt_native_apple:
        return net.bt_chipset or "Apple", "hw.bt.native"
    return net.bt_chipset or "—", ""


def _storage_line(profile: HardwareProfile) -> tuple[str, str]:
    storage = profile.storage
    kinds = []
    if storage.nvme_present:
        kinds.append("NVMe")
    if storage.sata_present:
        kinds.append("SATA")
    return " + ".join(kinds) or "—", ""


def hardware_rows(profile: Optional[HardwareProfile],
                  macos_target: str = "") -> list[dict]:
    """Строки карточки: ключ подписи, значение и пояснение."""
    if profile is None:
        return []
    rows: list[dict] = []

    def add(key: str, value: str, note: str = ""):
        if value:
            rows.append({"key": key, "value": value, "note": note})

    cpu_value, cpu_note = _cpu_line(profile)
    add("hw.cpu", cpu_value, cpu_note)
    gpu_value, gpu_note = _gpu_line(profile)
    add("hw.gpu", gpu_value, gpu_note)
    audio_value, audio_note = _audio_line(profile)
    add("hw.audio", audio_value, audio_note)
    eth_value, eth_note = _ethernet_line(profile)
    add("hw.ethernet", eth_value, eth_note)
    wifi_value, wifi_note = _wifi_line(profile)
    add("hw.wifi", wifi_value, wifi_note)
    bt_value, bt_note = _bt_line(profile)
    add("hw.bluetooth", bt_value, bt_note)
    storage_value, storage_note = _storage_line(profile)
    add("hw.storage", storage_value, storage_note)
    platform_key = _PLATFORM.get((profile.platform or "").lower(), "")
    if platform_key:
        add("hw.platform", tr_key(platform_key))
    board = f"{profile.board_vendor} {profile.board_name}".strip()
    if getattr(profile, "board_spoofed", False):
        add("hw.board", tr_key("hw.board.unknown"), tr_key("hw.board.spoofed"))
    else:
        add("hw.board", board or "—")
    try:
        from ..knowledge.kexts import smbios_model_for
        model = smbios_model_for(profile, macos_target)
    except Exception:
        model = ""
    if model:
        add("hw.smbios", model)
    return rows


def tr_key(key: str) -> str:
    """Перевод ключа интерфейса (ленивый импорт, чтобы модуль был лёгким)."""
    from ..i18n import tr
    return tr.t(key)
