"""Сканирование железа на Windows через WMI/PnP/PowerShell.

Логика сканирования адаптирована и усовершенствована из hackmate
(hardware.py) и опирается на практики OpCore-Simplify / HackOS.
"""

from __future__ import annotations

import re
from typing import Optional

from .models import (
    HardwareProfile, CPUInfo, GPUInfo, AudioInfo, NetInfo, StorageInfo,
)
from .powershell import ps
from .classify import (
    INTEL_IGPU_GENERATIONS, parse_intel_model, infer_intel_gen,
    detect_amd_gen, cpu_brand, ALC_LAYOUTS,
)


# ALC codec по HD audio device-id (subsystem)
_ALC_BY_ID: dict[str, str] = {
    "10ec:0295": "ALC295",
    "10ec:0256": "ALC256",
    "10ec:0255": "ALC255",
    "10ec:0289": "ALC289",
    "10ec:0294": "ALC294",
    "10ec:0298": "ALC298",
    "10ec:0269": "ALC269",
    "10ec:0282": "ALC282",
    "10ec:0283": "ALC283",
    "10ec:1220": "ALC1220",
    "10ec:0887": "ALC887",
    "10ec:0892": "ALC892",
    "10ec:0897": "ALC897",
}

_VIRTUAL_GPU = ("microsoft", "virtual", "remote", "parsec", "displaylink",
                "spacedesk", "vmware", "virtualbox", "citrix", "teamviewer",
                "idd", "meta")


class WindowsScanner:
    """Собирает HardwareProfile текущего Windows-хоста."""

    def scan(self) -> HardwareProfile:
        p = HardwareProfile(host_os="windows")
        self._detect_system(p)
        self._detect_cpu(p)
        self._detect_gpus(p)
        self._detect_audio(p)
        self._detect_network(p)
        self._detect_storage(p)
        self._detect_peripherals(p)
        self._disable_gpu_for_vm(p)
        return p

    # --- system ---
    def _detect_system(self, p: HardwareProfile):
        if ps.run_json('Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,HypervisorPresent'):
            try:
                info = ps.run_json('Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model | ConvertTo-Json -Compress')
            except Exception:
                info = None
        env = ps.run(
            '(Get-CimInstance Win32_SystemEnclosure).ChassisTypes | ForEach-Object { $_.ToString() }'
        )
        laptop = {"8", "9", "10", "11", "12", "14"}
        desktop = {"3", "4", "5", "6", "7", "13", "15", "16", "17", "23"}
        chassis = re.findall(r"\d+", env)
        if any(t in laptop for t in chassis):
            p.platform = "laptop"
        elif any(t in desktop for t in chassis):
            p.platform = "desktop"
        else:
            # фолбэк по батарее (с фильтром UPS)
            batt = ps.run("(Get-CimInstance Win32_Battery).Name")
            p.platform = "laptop" if batt.strip() and "ups" not in batt.lower() else "desktop"

        board = ps.run_json(
            '(Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer,Product | Select-Object -First 1) '
            '| ConvertTo-Json -Compress'
        )
        if isinstance(board, dict):
            p.board_vendor = str(board.get("Manufacturer") or "")
            p.board_name = str(board.get("Product") or "")
        bios = ps.run_json(
            '(Get-CimInstance Win32_BIOS | Select-Object SMBIOSBIOSVersion | Select-Object -First 1) '
            '| ConvertTo-Json -Compress'
        )
        if isinstance(bios, dict):
            p.bios_version = str(bios.get("SMBIOSBIOSVersion") or "")

        comp = ps.run_json(
            '(Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,HypervisorPresent) '
            '| ConvertTo-Json -Compress'
        )
        if isinstance(comp, dict):
            h = bool(comp.get("HypervisorPresent"))
            if h:
                p.virtual_machine = "hypervisor"

    # --- CPU ---
    def _detect_cpu(self, p: HardwareProfile):
        raw = ps.run_json(
            '(Get-CimInstance Win32_Processor | Select-Object -First 1 '
            '-Property Name,NumberOfCores,NumberOfLogicalProcessors,VirtualizationFirmwareEnabled) '
            '| ConvertTo-Json -Compress'
        )
        if not isinstance(raw, dict):
            return
        name = str(raw.get("Name") or "").strip()
        p.cpu.name = name
        low = name.lower()
        p.cpu.vendor = "intel" if "intel" in low else ("amd" if "amd" in low else "")
        try:
            p.cpu.core_count = int(raw.get("NumberOfCores") or 0)
            p.cpu.thread_count = int(raw.get("NumberOfLogicalProcessors") or 0)
        except (TypeError, ValueError):
            pass
        p.cpu.brand = cpu_brand(name)

        mnum = re.search(r"(?:ryzen|core |xeon |athlon )[\w\s\-]*?(\d{3,5}[a-z]*|ultra\s+?\d+[a-z]*)", name, re.I)
        if mnum:
            p.cpu.model_number = mnum.group(1).strip()

        if p.cpu.vendor == "intel":
            gen, codename = parse_intel_model(name)
            p.cpu.generation, p.cpu.codename = gen, codename
            # GPU dev-id — иногда точнее, чем название
            if p.igpu and p.igpu.device_id.lower() in INTEL_IGPU_GENERATIONS:
                g, c, oc = INTEL_IGPU_GENERATIONS[p.igpu.device_id.lower()]
                p.cpu.generation, p.cpu.codename, p.cpu.oc_platform = g, c, oc
            if not p.cpu.generation:
                g, c, oc = infer_intel_gen(name)
                if g:
                    p.cpu.generation, p.cpu.codename, p.cpu.oc_platform = g, c, oc
            if not p.cpu.oc_platform:
                p.cpu.oc_platform = p.cpu.codename
        elif p.cpu.vendor == "amd":
            fam, cn, oc = detect_amd_gen(name)
            p.cpu.generation, p.cpu.codename, p.cpu.oc_platform = fam, cn, oc

    # --- GPU ---
    def _detect_gpus(self, p: HardwareProfile):
        raw = ps.run_json(
            '(Get-CimInstance Win32_VideoController | '
            'Select-Object Name,PNPDeviceID,AdapterRAM) | ConvertTo-Json -Compress'
        )
        controllers = []
        if isinstance(raw, dict):
            controllers = [raw]
        elif isinstance(raw, list):
            controllers = raw

        entries = []
        for c in controllers:
            if not isinstance(c, dict):
                continue
            name = str(c.get("Name") or "").strip()
            pnp = str(c.get("PNPDeviceID") or "")
            if not name and pnp:
                m = re.search(r"VEN_([0-9A-Fa-f]{4})&DEV_([0-9A-Fa-f]{4})", pnp)
                if m:
                    name = f"PCI Device {m.group(1)}:{m.group(2)}"
            entries.append({
                "name": name,
                "pnp": pnp,
                "vram": c.get("AdapterRAM") or 0,
            })

        igpu, dgpu = self._classify_gpus(entries)
        p.igpu, p.dgpu = igpu, dgpu

    def _classify_gpus(self, entries: list[dict]):
        igpu = dgpu = None
        for e in entries:
            name = e["name"]
            dev = e["pnp"]
            low = name.lower()
            if any(k in low for k in _VIRTUAL_GPU):
                continue
            ven = re.search(r"VEN_([0-9A-Fa-f]{4})", dev)
            vid = ven.group(1).lower() if ven else ""
            di = re.search(r"DEV_([0-9A-Fa-f]{4})", dev)
            did = di.group(1).lower() if di else ""
            try:
                vram = int(e["vram"] // (1024 * 1024)) if e["vram"] else 0
            except Exception:
                vram = 0

            if "intel" in low or vid == "8086":
                if igpu is None:
                    igpu = GPUInfo(name=name, vendor="intel", device_id=did,
                                   is_integrated=True, vram_mb=vram)
            elif vid == "1002" or "radeon" in low or "amd" in low:
                if dgpu is None and ("x" in low or "radeon" in low or "vega" in low or re.search(r"\brx\b", low)):
                    dgpu = GPUInfo(name=name, vendor="amd", device_id=did,
                                   is_integrated=False, vram_mb=vram)
                elif igpu is None and ("amd" in low or "radeon" in low):
                    igpu = GPUInfo(name=name, vendor="amd", device_id=did,
                                   is_integrated=True, vram_mb=vram)
            elif vid in ("10de", "10b4") or "nvidia" in low or "geforce" in low:
                if dgpu is None:
                    dgpu = GPUInfo(name=name, vendor="nvidia", device_id=did,
                                   is_integrated=False, vram_mb=vram)
        return igpu, dgpu

    # --- audio ---
    def _detect_audio(self, p: HardwareProfile):
        raw = ps.run(
            "(Get-CimInstance Win32_SoundDevice | ForEach-Object { $_.Name }) -join '||'"
        )
        devices = [d.strip() for d in raw.split("||") if d.strip()]
        if not devices:
            return
        _NOT = ("nvidia", "steam", "virtual", "usb", "bluetooth", "hdmi",
                "displayport", "display audio", "streaming", "focusrite",
                "webcam", "camera", "monitor", "dp audio", "smart sound")
        best = next((d for d in devices if re.search(r"ALC\d{3,4}", d, re.I)), "")
        if not best:
            best = next((d for d in devices if "realtek" in d.lower()), "")
        if not best:
            best = next((d for d in devices if not any(k in d.lower() for k in _NOT)), "")
        if not best:
            best = devices[0]

        p.audio.name = best
        m = re.search(r"ALC(\d{3,4})", best.upper())
        codec = f"ALC{m.group(1)}" if m else ""
        if not codec:
            codec = self._hda_codec_windows()
        if not codec and "realtek" in best.lower():
            codec = "Realtek"
        p.audio.codec = codec
        if codec in ALC_LAYOUTS:
            p.audio.layout_candidates = ALC_LAYOUTS[codec]
            p.audio.layout_id = p.audio.layout_candidates[0]

    def _hda_codec_windows(self) -> str:
        raw = ps.run(
            "(Get-PnpDevice | Where-Object { $_.InstanceId -match 'HDAUDIO.*VEN_10EC' } | "
            "Select-Object -ExpandProperty InstanceId) -join '||'"
        )
        for iid in raw.split("||"):
            m = re.search(r"VEN_10EC&DEV_([0-9A-Fa-f]{4})", iid)
            if m:
                model = m.group(1).lstrip("0") or "0"
                return f"ALC{model}"
        return ""

    # --- network ---
    def _detect_network(self, p: HardwareProfile):
        raw = ps.run("""
            $nic = Get-NetAdapter -Physical -ErrorAction SilentlyContinue | Where-Object {
                $_.InterfaceDescription -notmatch 'Wi-Fi|Wireless|WiFi|802.11|Bluetooth'
            } | Select-Object -First 1
            $nic.InterfaceDescription
        """)
        eth = raw.strip()
        p.net.eth_name = eth
        el = eth.lower()
        if "i219" in el: p.net.eth_chipset = "i219"
        elif "i218" in el: p.net.eth_chipset = "i218"
        elif "i217" in el: p.net.eth_chipset = "i217"
        elif "i225" in el: p.net.eth_chipset = "i225"
        elif "i226" in el: p.net.eth_chipset = "i226"
        elif "rtl8125" in el: p.net.eth_chipset = "rtl8125"
        elif "rtl8111" in el or "rtl8168" in el: p.net.eth_chipset = "rtl8111"
        elif "realtek" in el: p.net.eth_chipset = "realtek"
        elif "intel" in el: p.net.eth_chipset = "intel"

        wifi = ps.run("""
            $nic = Get-CimInstance Win32_NetworkAdapter | Where-Object {
                $_.Name -match 'Wi-Fi|Wireless|WiFi|802.11'
            } | Select-Object -First 1
            $nic.Name
        """)
        w = wifi.strip()
        p.net.wifi_name = w
        wl = w.lower()
        if "intel" in wl: p.net.wifi_chipset = "intel"
        elif "broadcom" in wl or "bcm" in wl: p.net.wifi_chipset = "broadcom"
        elif "atheros" in wl or "qualcomm" in wl: p.net.wifi_chipset = "atheros"
        elif "realtek" in wl: p.net.wifi_chipset = "realtek"
        elif "mediatek" in wl: p.net.wifi_chipset = "mediatek"
        else:
            # fallback: intel wifi по известным DEV-вентам
            ids = "0070|0074|4070|2723|2725|0094"
            fallback = ps.run(
                f"(Get-PnpDevice -PresentOnly | Where-Object {{ $_.InstanceId -match 'PCI\\\\VEN_8086&DEV_({ids})' }} | Select-Object -First 1).InstanceId"
            )
            if fallback.strip():
                p.net.wifi_chipset = "intel"
                p.net.wifi_name = p.net.wifi_name or "Intel WiFi (без драйвера)"

        # Bluetooth
        bt = ps.run("(Get-PnpDevice | Where-Object { $_.Class -eq 'Bluetooth' } | Measure-Object).Count")
        try:
            p.net.has_bt = int(bt.strip() or 0) > 0
        except Exception:
            p.net.has_bt = False

    # --- storage ---
    def _detect_storage(self, p: HardwareProfile):
        raw = ps.run("(Get-PhysicalDisk | Where-Object { $_.BusType -eq 'NVMe' } | Measure-Object).Count")
        try:
            p.storage.nvme_present = int(raw.strip() or 0) > 0
        except Exception:
            p.storage.nvme_present = False

    # --- peripherals (touchpad, thunderbolt) ---
    def _detect_peripherals(self, p: HardwareProfile):
        if p.platform == "desktop":
            p.has_touchpad = False
            p.touchpad_type = "none"
        else:
            tb = ps.run("(Get-PnpDevice | Where-Object { $_.Class -eq 'System' -and $_.FriendlyName -match 'Thunderbolt' } | Measure-Object).Count")
            try:
                p.has_thunderbolt = int(tb.strip() or 0) > 0
            except Exception:
                p.has_thunderbolt = False
            i2c = ps.run("(Get-PnpDevice | Where-Object { $_.Class -eq 'HIDClass' -and $_.InstanceId -match 'I2C' } | Measure-Object).Count")
            try:
                p.has_touchpad = int(i2c.strip() or 0) > 0
                p.touchpad_type = "i2c" if p.has_touchpad else "ps2"
            except Exception:
                pass

    def _disable_gpu_for_vm(self, p: HardwareProfile):
        if p.virtual_machine:
            p.igpu = None
            p.dgpu = None


def scan_hardware() -> HardwareProfile:
    """Главная точка входа: сканирует текущий хост и возвращает профиль."""
    return WindowsScanner().scan()