"""Сканирование железа на macOS через system_profiler.

Парсеры чистые: принимают JSON-ответ ``system_profiler`` и не трогают систему,
поэтому их можно тестировать на любой ОС. Сам сканер вызывает system_profiler
и собирает из ответов ``HardwareProfile`` — тот же, что отдаёт Windows-сканер,
значит сборка EFI, SMBIOS и отчёты работают без изменений.

Что недоступно на macOS: UEFI-пути PCI (в IORegistry они другие) и таблица
DSDT через Windows API — поля остаются пустыми, и config.plist просто обходится
без соответствующих записей.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Optional

from .classify import (
    cpu_brand,
    detect_amd_gen,
    eth_chipset_from_name,
    infer_intel_gen,
    parse_intel_model,
)
from .models import (
    AudioInfo,
    CPUInfo,
    GPUInfo,
    HardwareProfile,
    NetInfo,
    StorageInfo,
)

_APPLE_SILICON = re.compile(r"\bapple\s+m\d", re.IGNORECASE)
_CODEC = re.compile(r"\b(?:ALC|CX|CS|AD|IDT|VT|STAC)\s?(\d{3,4})\b", re.IGNORECASE)
_VRAM_GB = re.compile(r"(\d+)\s*(GB|MB)", re.IGNORECASE)


# ---------- чистые парсеры ----------
def parse_hardware(payload: dict) -> dict:
    """Основное: модель, процессор, ядра, память, класс машины."""
    items = (payload.get("SPHardwareDataType") or [{}])
    row = items[0] if items else {}
    model = str(row.get("machine_model") or row.get("model_name") or "")
    chip = str(row.get("chip_type") or "")
    cpu_name = str(row.get("processor_name") or chip or "")

    cores = 0
    raw_cores = str(row.get("number_processors") or "")
    match = re.search(r"proc\s+(\d+)", raw_cores)
    if match:
        cores = int(match.group(1))

    memory_gb = 0
    raw_mem = str(row.get("physical_memory") or "")
    if raw_mem:
        memory_gb = int(re.sub(r"\D", "", raw_mem) or 0)
        if "GB" not in raw_mem.upper():
            memory_gb = 0

    return {
        "model": model,
        "cpu_name": cpu_name,
        "cores": cores,
        "memory_gb": memory_gb,
        "is_apple_silicon": bool(_APPLE_SILICON.search(cpu_name or chip)),
        "is_laptop": "macbook" in model.lower(),
    }


def classify_cpu(name: str, is_apple_silicon: bool = False) -> CPUInfo:
    """Поколение, кодовое имя и платформа OpenCore по названию процессора."""
    info = CPUInfo(name=name, brand=cpu_brand(name))
    if is_apple_silicon:
        info.vendor = "apple"
        info.is_apple_silicon = True
        info.oc_platform = "Apple Silicon"
        return info
    lowered = name.lower()
    if "amd" in lowered:
        info.vendor = "amd"
        info.generation, info.codename, info.oc_platform = detect_amd_gen(name)
    elif "intel" in lowered:
        info.vendor = "intel"
        # На macOS процессор приходит полным названием («Core i7-9750H»),
        # поэтому сначала пробуем разобрать номер модели: он точнее ключевых слов.
        generation, codename = parse_intel_model(name)
        if generation:
            info.generation = generation
            info.codename = codename
            info.oc_platform = infer_intel_gen(codename)[2] or codename
        else:
            info.generation, info.codename, info.oc_platform = infer_intel_gen(name)
    return info


def _vram_mb(text: str) -> int:
    match = _VRAM_GB.search(text or "")
    if not match:
        return 0
    value = int(match.group(1))
    return value * 1024 if match.group(2).upper() == "GB" else value


def parse_gpus(payload: dict) -> tuple[Optional[GPUInfo], Optional[GPUInfo]]:
    """Встроенная и дискретная графика: возвращает (igpu, dgpu)."""
    items = payload.get("SPDisplaysDataType") or []
    igpu: Optional[GPUInfo] = None
    dgpu: Optional[GPUInfo] = None
    for row in items:
        name = str(row.get("sppci_model") or row.get("_name") or "")
        if not name or "display" in name.lower():
            continue
        vendor_text = str(row.get("spdisplays_vendor") or "")
        lowered = f"{vendor_text} {name}".lower()
        if "intel" in lowered:
            vendor = "intel"
        elif "amd" in lowered or "ati" in lowered:
            vendor = "amd"
        elif "nvidia" in lowered:
            vendor = "nvidia"
        else:
            vendor = ""
        gpu = GPUInfo(name=name, vendor=vendor,
                      vram_mb=_vram_mb(str(row.get("spdisplays_vram") or "")))
        gpu.is_integrated = vendor == "intel" or "integrated" in lowered
        device = str(row.get("spdisplays_device-id") or "")
        if device:
            gpu.device_id = device.split(":")[-1].strip().lower()
        if gpu.is_integrated and igpu is None:
            igpu = gpu
        elif dgpu is None:
            dgpu = gpu
    return igpu, dgpu


def parse_audio(payload: dict) -> AudioInfo:
    """Кодек и рабочий layout-id из списка аудиоустройств."""
    names: list[str] = []
    for row in payload.get("SPAudioDataType") or []:
        names.append(str(row.get("_name") or ""))
        for child in row.get("_items") or []:
            names.append(str(child.get("_name") or ""))
    joined = " ".join(names)
    match = _CODEC.search(joined)
    codec = ""
    if match:
        codec = f"ALC{match.group(1)}" if "alc" in match.group(0).lower() else match.group(0).upper()
    audio = AudioInfo(name=names[0] if names else "", codec=codec)
    if codec:
        from ..knowledge.audio_layouts import layouts_for, recommended
        audio.layout_candidates = list(layouts_for(codec))
        audio.layout_id = recommended(codec)
    return audio


def parse_network(payload: dict) -> NetInfo:
    """Ethernet и Wi-Fi по типу интерфейса из SPNetworkDataType."""
    net = NetInfo()
    for row in payload.get("SPNetworkDataType") or []:
        name = str(row.get("_name") or "")
        kind = str(row.get("type") or "").lower()
        lowered = f"{name} {kind}".lower()
        if "ethernet" in lowered and not net.eth_name:
            net.eth_name = name
            net.eth_chipset = eth_chipset_from_name(name)
        elif ("airport" in lowered or "wi-fi" in lowered or "wifi" in lowered) and not net.wifi_name:
            net.wifi_name = name
            net.wifi_chipset = _wifi_vendor(name)
    return net


def _wifi_vendor(name: str) -> str:
    lowered = name.lower()
    for vendor in ("broadcom", "intel", "atheros", "realtek", "mediatek"):
        if vendor in lowered:
            return vendor
    return ""


def parse_storage(payload: dict) -> StorageInfo:
    """NVMe-накопитель определяется по типу устройства."""
    nvme = False
    sata = False
    for row in payload.get("SPNVMeDataType") or []:
        if row.get("_items"):
            nvme = True
    for row in payload.get("SPSerialAType") or payload.get("SPSerialATADataType") or []:
        if row.get("_items"):
            sata = True
    return StorageInfo(nvme_present=nvme, sata_present=sata or not nvme)


# ---------- сам сканер ----------
def _profiler(*types: str) -> dict:
    from ..proc import run

    done = run(["system_profiler", "-json", *types],
               capture_output=True, text=True, timeout=120)
    if done.returncode != 0 or not done.stdout.strip():
        return {}
    try:
        return json.loads(done.stdout)
    except ValueError:
        return {}


class MacOSScanner:
    """Собирает HardwareProfile на macOS. Только чтение."""

    def scan(self) -> HardwareProfile:
        if sys.platform != "darwin":
            raise RuntimeError("MacOSScanner работает только на macOS")
        hardware = parse_hardware(_profiler("SPHardwareDataType"))
        profile = HardwareProfile(host_os="macos")
        profile.platform = "laptop" if hardware["is_laptop"] else "desktop"
        profile.cpu = classify_cpu(hardware["cpu_name"], hardware["is_apple_silicon"])
        profile.cpu.core_count = hardware["cores"]
        profile.cpu.thread_count = hardware["cores"]

        profile.igpu, profile.dgpu = parse_gpus(_profiler("SPDisplaysDataType"))
        profile.audio = parse_audio(_profiler("SPAudioDataType"))
        profile.net = parse_network(_profiler("SPNetworkDataType"))
        profile.storage = parse_storage(_profiler("SPNVMeDataType", "SPSerialATADataType"))

        board = hardware["model"]
        profile.board_name = board
        if "macbook" in board.lower() or "imac" in board.lower():
            profile.board_vendor = "Apple"

        # UEFI-пути для DeviceProperties: layout-id аудио и built-in для сети.
        try:
            from .pci_paths_mac import device_paths
            audio_path, eth_path, wifi_path = device_paths()
            if audio_path:
                profile.audio.pci_path = audio_path
            if eth_path:
                profile.net.eth_pci_path = eth_path
            if wifi_path:
                profile.net.wifi_pci_path = wifi_path
        except Exception:
            pass
        return profile


def scan_hardware() -> HardwareProfile:
    """Точка входа на macOS: сканирует текущий Mac."""
    return MacOSScanner().scan()
