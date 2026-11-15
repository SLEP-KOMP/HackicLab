"""Автоматическое построение карты USB-портов (UTBMap.kext).

Порты берутся из двух независимых источников (по порядку):
  1) DSDT из прошивки — каждый физический порт объявлен в ACPI устройствами
     с _ADR (индекс порта) и _UPC (подключаемость + тип коннектора).
     Разбираем декомпилированный через iasl DSL: работает без живой загрузки
     macOS, без прав администратора и без подключённых устройств.
  2) usbdump.exe из USBToolBox (Windows) — топология корневых хабов, если
     DSDT не дал пригодного результата.

Результат — Info.plist карты (plist-only бандл UTBMap.kext), который кладётся
в EFI/OC/Kexts. Логика адаптирована из hackmate (auto_usb_map.py, MIT).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Optional

MAP_BUNDLE_IDENTIFIER = "com.dhinakg.USBToolBox.map"
DRIVER_BUNDLE_IDENTIFIER = "com.dhinakg.USBToolBox.kext"
MAX_PORTS_PER_CONTROLLER = 15  # размер таблицы персон AppleUSBXHCI

TYPE_USB_A = 0
TYPE_INTERNAL = 255

_INFO_PLIST_TEMPLATE = {
    "CFBundleDevelopmentRegion": "English",
    "CFBundleGetInfoString": "v1.1",
    "CFBundleIdentifier": MAP_BUNDLE_IDENTIFIER,
    "CFBundleInfoDictionaryVersion": "6.0",
    "CFBundleName": "UTBMap",
    "CFBundlePackageType": "KEXT",
    "CFBundleShortVersionString": "1.1",
    "CFBundleSignature": "????",
    "CFBundleVersion": "1.1",
    "IOKitPersonalities": {},
    "OSBundleRequired": "Root",
}

_DEVICE_OPEN_RE = re.compile(r"Device\s*\(([A-Za-z0-9_^\\.]{1,10})\)\s*\{")
_ADR_NAME_RE = re.compile(r"Name\s*\(_ADR,\s*([^,\)]+)\)")
_ADR_METHOD_RETURN_RE = re.compile(r"Method\s*\(_ADR\b.*?Return\s*\(([^)]+)\)", re.DOTALL)
_UPC_PRESENT_RE = re.compile(r"(?:Name|Method)\s*\(_UPC\b")
_UPC_NAME_PKG_RE = re.compile(r"Name\s*\(_UPC,\s*Package\s*\([^)]*\)\s*\{(.*?)\}", re.DOTALL)

_HUB_WRAPPER_NAMES = {"RHUB", "RHB", "HUBN", "HUB0", "HUB1", "HUBP"}


# ---------------------------------------------------------------------------
# Разбор ACPI
# ---------------------------------------------------------------------------

def _acpi_int(raw: str) -> Optional[int]:
    raw = raw.strip().rstrip(",").strip()
    low = raw.lower()
    if low == "zero":
        return 0
    if low == "one":
        return 1
    try:
        return int(raw, 0)
    except ValueError:
        return None


def _iter_device_blocks(text: str) -> list:
    """Все блоки `Device (NAME) { ... }` в декомпилированном ASL.

    Возвращает dict-и с путём устройства (кортеж предков) и телом блока.
    """
    device_starts = {m.end() - 1: m.group(1) for m in _DEVICE_OPEN_RE.finditer(text)}
    open_stack = []  # (индекс открывающей скобки, имя устройства или None)
    path_stack = []
    blocks = []
    for i, ch in enumerate(text):
        if ch == "{":
            name = device_starts.get(i)
            open_stack.append((i, name))
            if name:
                path_stack.append(name)
        elif ch == "}":
            if not open_stack:
                continue
            start_i, name = open_stack.pop()
            if name:
                blocks.append({"name": name, "path": tuple(path_stack),
                               "body": text[start_i + 1:i]})
                path_stack.pop()
    return blocks


def _leaf_port_blocks(blocks: list) -> list:
    """Листовые блоки (без вложенных Device), объявляющие _UPC.

    Так отсекаются контроллеры/хабы, у которых _ADR — это PCI-адрес, а не
    индекс порта, и посторонние устройства с _ADR (слоты, GPIO).
    """
    container_paths = {b["path"][:-1] for b in blocks if len(b["path"]) > 1}
    return [b for b in blocks
            if b["path"] not in container_paths and _UPC_PRESENT_RE.search(b["body"])]


def _port_index(body: str) -> Optional[int]:
    m = _ADR_NAME_RE.search(body)
    if m:
        return _acpi_int(m.group(1))
    m = _ADR_METHOD_RETURN_RE.search(body)
    if m:
        return _acpi_int(m.group(1))
    return None


def _port_connector_type(body: str) -> Optional[int]:
    """Тип коннектора из статического `Name (_UPC, Package {...})`.

    `Method (_UPC, ...)` может считать значение в рантайме — такие порты
    всё равно попадут в карту, но с типом USB-A по умолчанию.
    """
    m = _UPC_NAME_PKG_RE.search(body)
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).split(",") if p.strip()]
    if len(parts) < 2:
        return None
    return _acpi_int(parts[1])


def parse_dsdt_ports(dsl_text: str) -> dict:
    """Текст DSL -> {имя контроллера: [описание портов]}."""
    blocks = _iter_device_blocks(dsl_text)
    ports_by_parent: dict = {}

    for block in _leaf_port_blocks(blocks):
        index = _port_index(block["body"])
        if index is None or index <= 0:
            continue
        parent_path = block["path"][:-1]
        if not parent_path:
            continue
        controller_name = parent_path[-1]
        if controller_name in _HUB_WRAPPER_NAMES and len(parent_path) > 1:
            controller_name = parent_path[-2]
        ports_by_parent.setdefault(controller_name, []).append({
            "index": index,
            "class": "Unknown",
            "type": _port_connector_type(block["body"]),
            "guessed": None,
        })

    return ports_by_parent


# ---------------------------------------------------------------------------
# Дамп и декомпиляция DSDT
# ---------------------------------------------------------------------------

def _dump_dsdt_api(tmp_dir: Path) -> Optional[Path]:
    """DSDT через GetSystemFirmwareTable (без прав администратора)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes

        provider = int.from_bytes(b"ACPI", "big")
        table_id = int.from_bytes(b"DSDT", "big")
        k32 = ctypes.windll.kernel32
        k32.GetSystemFirmwareTable.restype = ctypes.c_uint32
        k32.GetSystemFirmwareTable.argtypes = [
            ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
        ]
        size = k32.GetSystemFirmwareTable(provider, table_id, None, 0)
        if not size:
            return None
        buf = ctypes.create_string_buffer(size)
        read = k32.GetSystemFirmwareTable(provider, table_id, buf, size)
        if not read:
            return None
        dst = Path(tmp_dir) / "DSDT.aml"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(bytes(buf[:read]))
        return dst
    except Exception:
        return None


def _dump_dsdt_registry(tmp_dir: Path) -> Optional[Path]:
    """Фолбэк: Windows кэширует DSDT в HKLM\\HARDWARE\\ACPI\\DSDT."""
    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\ACPI\DSDT") as dsdt_key:
            vendor = winreg.EnumKey(dsdt_key, 0)
            with winreg.OpenKey(dsdt_key, vendor) as vendor_key:
                oem = winreg.EnumKey(vendor_key, 0)
                with winreg.OpenKey(vendor_key, oem) as oem_key:
                    revision = winreg.EnumKey(oem_key, 0)
                    with winreg.OpenKey(oem_key, revision) as rev_key:
                        data, _ = winreg.QueryValueEx(rev_key, "00000000")
                        dst = Path(tmp_dir) / "DSDT.aml"
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        dst.write_bytes(bytes(data))
                        return dst
    except Exception:
        return None


def dump_dsdt(tmp_dir: Path) -> Optional[Path]:
    """Сохраняет DSDT системы в ``tmp_dir/DSDT.aml`` (API, затем реестр)."""
    return _dump_dsdt_api(tmp_dir) or _dump_dsdt_registry(tmp_dir)


def decompile_dsdt(dsdt_path: Path, work_dir: Path, log=None) -> Optional[str]:
    """Декомпилирует DSDT в DSL через iasl (скачивает компилятор при нужде)."""
    def _log(msg, level="info"):
        if log:
            log(msg)

    from .ssdt_factory import find_iasl

    if not dsdt_path or not Path(dsdt_path).exists():
        return None
    iasl = find_iasl(ensure=True)
    if not iasl:
        _log("Для разбора DSDT нужен iasl — скачать не удалось", "warn")
        return None

    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    local_aml = work / "DSDT.aml"
    try:
        if Path(dsdt_path).resolve() != local_aml.resolve():
            shutil.copy2(str(dsdt_path), str(local_aml))
    except Exception:
        local_aml = Path(dsdt_path)

    try:
        subprocess.run([str(iasl), "-d", str(local_aml)],
                       cwd=str(work), capture_output=True, timeout=60)
    except Exception:
        return None

    dsl = local_aml.with_suffix(".dsl")
    if not dsl.exists():
        candidates = list(work.glob("*.dsl")) + list(Path(local_aml).parent.glob("*.dsl"))
        if not candidates:
            return None
        dsl = candidates[0]
    try:
        return dsl.read_text(errors="replace")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Сборка карты из DSDT
# ---------------------------------------------------------------------------

def _speed_prefix(ports: list) -> str:
    """Префикс имени порта (косметика: IOKit матчит по индексу, не по имени)."""
    classes = {p["class"] for p in ports}
    if "SuperSpeed" in classes:
        return "SS"
    if "HighSpeed" in classes or "FullSpeed" in classes:
        return "HS"
    return "PRT"


def generate_dsdt_map(tmp_dir: Path, log=None) -> Optional[dict]:
    """DSDT -> Info.plist карты UTBMap (или None, если портов не нашли)."""
    def _log(msg, level="info"):
        if log:
            log(msg)

    work = Path(tmp_dir)
    _log("Ищу DSDT в прошивке…")
    dsdt = dump_dsdt(work)
    if not dsdt:
        _log("DSDT недоступен — карту из ACPI не построить", "warn")
        return None

    _log("Декомпилирую DSDT (iasl)…")
    dsl_text = decompile_dsdt(dsdt, work, log=_log)
    if not dsl_text:
        _log("Не удалось декомпилировать DSDT", "warn")
        return None

    ports_by_controller = parse_dsdt_ports(dsl_text)
    if not ports_by_controller:
        _log("В DSDT не найдено USB-портов с _UPC", "warn")
        return None

    personalities = {}
    for controller_name, ports in ports_by_controller.items():
        selected = sorted(ports, key=lambda p: p["index"])[:MAX_PORTS_PER_CONTROLLER]
        prefix = _speed_prefix(selected)
        entry_ports = {}
        highest_index = 0
        for i, port in enumerate(selected, start=1):
            highest_index = max(highest_index, port["index"])
            connector = port["type"] if port["type"] is not None else TYPE_USB_A
            port_name = f"{prefix}{str(i).zfill(max(1, 4 - len(prefix)))}"
            entry_ports[port_name] = {
                "port": port["index"].to_bytes(4, byteorder="little"),
                "UsbConnector": connector,
            }
        if not entry_ports:
            continue
        personalities[controller_name] = {
            "CFBundleIdentifier": DRIVER_BUNDLE_IDENTIFIER,
            "IOClass": "USBToolBox",
            "IOProviderClass": "IOPCIDevice",
            "IOMatchCategory": "USBToolBox",
            "IONameMatch": controller_name,
            "IOProviderMergeProperties": {
                "ports": entry_ports,
                "port-count": highest_index.to_bytes(4, byteorder="little"),
            },
        }

    if not personalities:
        return None

    total_ports = sum(
        len(p["IOProviderMergeProperties"]["ports"]) for p in personalities.values())
    _log(f"Карта из DSDT: {total_ports} порт(ов) в {len(personalities)} контроллере(ах)", "ok")

    template = dict(_INFO_PLIST_TEMPLATE)
    template["IOKitPersonalities"] = personalities
    return template


# ---------------------------------------------------------------------------
# Второй источник: usbdump.exe из USBToolBox
# ---------------------------------------------------------------------------

def download_usbtoolbox_zip(dest_dir: Path, log=None) -> Optional[Path]:
    """Скачивает Windows-сборку USBToolBox и возвращает путь к zip."""
    from .fetcher import download_bytes

    def _log(msg, level="info"):
        if log:
            log(msg)

    _log("Ищу USBToolBox на GitHub…")
    try:
        raw = download_bytes(
            "https://api.github.com/repos/USBToolBox/Tool/releases?per_page=10",
            headers={"User-Agent": "HackicLab/0.1",
                     "Accept": "application/vnd.github+json"},
            timeout=30,
        )
        releases = json.loads(raw.decode("utf-8"))
    except Exception:
        _log("Не удалось получить список релизов USBToolBox", "warn")
        return None

    asset = None
    for release in (releases or []):
        for a in release.get("assets") or []:
            name = (a.get("name") or "").lower()
            if "windows" in name and name.endswith(".zip"):
                asset = a
                break
        if asset:
            break
    if not asset:
        _log("В релизах USBToolBox нет Windows-архива", "warn")
        return None

    out_dir = Path(dest_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (asset.get("name") or "USBToolBox-Windows.zip")
    size = asset.get("size") or 0
    if out.exists() and out.stat().st_size > 0 and (
            not size or abs(out.stat().st_size - size) <= 1024):
        return out
    try:
        _log(f"Скачиваю {out.name}…")
        data = download_bytes(asset["browser_download_url"], timeout=180)
        out.write_bytes(data)
        return out
    except Exception:
        _log("Не удалось скачать USBToolBox", "warn")
        return None


def extract_usbdump(zip_path: Path, dest_dir: Path) -> Optional[Path]:
    """Достаёт Resources/usbdump.exe из архива USBToolBox."""
    try:
        with zipfile.ZipFile(str(zip_path)) as z:
            candidates = [n for n in z.namelist()
                          if n.lower().replace("\\", "/").endswith("resources/usbdump.exe")]
            if not candidates:
                return None
            dest = Path(dest_dir)
            dest.mkdir(parents=True, exist_ok=True)
            out = dest / "usbdump.exe"
            with z.open(candidates[0]) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst)
            return out
    except Exception:
        return None


def _run_usbdump(usbdump_exe: Path) -> Optional[list]:
    try:
        result = subprocess.run([str(usbdump_exe)], capture_output=True, timeout=30)
        return json.loads(result.stdout.decode(errors="replace"))
    except Exception:
        return None


def _hex_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _port_speed_class(port: dict) -> str:
    """SuperSpeed/HighSpeed/FullSpeed/Unknown по флагам протокола."""
    v2 = port.get("ConnectionInfoV2")
    if not v2 or not v2.get("SupportedUsbProtocols"):
        return "Unknown"
    protocols = v2["SupportedUsbProtocols"]
    if protocols.get("Usb300"):
        return "SuperSpeed"
    if protocols.get("Usb200") and protocols.get("Usb110"):
        return "HighSpeed"
    if protocols.get("Usb110"):
        return "FullSpeed"
    return "Unknown"


def _serialize_hub(hub: dict) -> dict:
    """Сырые HubPorts корневого хаба -> список портов."""
    hub_info = {"ports": []}
    hub_ports = hub.get("HubPorts") or []
    for i, port in enumerate(hub_ports):
        if not port:
            continue
        conn = port.get("ConnectionInfo") or {}
        index = (
            (port.get("PortConnectorProps") or {}).get("ConnectionIndex")
            or conn.get("ConnectionIndex")
            or (port.get("ConnectionInfoV2") or {}).get("ConnectionIndex")
            or i + 1
        )
        status = conn.get("ConnectionStatus") or ""
        port_info = {
            "index": _hex_int(index),
            "status": status,
            "class": "Unknown",
            "type": None,
            "guessed": None,
            "type_c": False,
            "user_connectable": True,
        }
        if str(status) == "DeviceConnected":
            port_info["class"] = _port_speed_class(port)
            props = (port.get("PortConnectorProps") or {}).get("UsbPortProperties") or {}
            port_info["type_c"] = bool(props.get("PortConnectorIsTypeC", False))
            port_info["user_connectable"] = bool(props.get("PortIsUserConnectable", True))
        hub_info["ports"].append(port_info)

    hub_info["ports"].sort(key=lambda p: p["index"])
    return hub_info


def _guess_port_type(port: dict) -> Optional[int]:
    """Оценка типа коннектора по данным usbdump (без companion-портов)."""
    if not str(port["status"]).endswith("DeviceConnected"):
        return None
    if port["type_c"]:
        return 9  # USB3 Type-C с переключателем
    if not port["user_connectable"]:
        return TYPE_INTERNAL
    if port["class"] == "SuperSpeed":
        return 3  # USB3 Type-A
    return TYPE_USB_A


def dump_controllers(usbdump_exe: Path) -> list:
    """JSON usbdump.exe -> список контроллеров с реальными портами."""
    raw = _run_usbdump(usbdump_exe)
    if not raw:
        return []

    controllers = []
    for controller in raw:
        root_hub = controller.get("RootHub")
        if not root_hub:
            continue
        identifiers = {}
        if controller.get("BusDeviceFunctionValid"):
            identifiers["bdf"] = [
                _hex_int(controller.get("BusNumber")),
                _hex_int(controller.get("BusDevice")),
                _hex_int(controller.get("BusFunction")),
            ]
        hub_info = _serialize_hub(root_hub)
        for port in hub_info["ports"]:
            port["guessed"] = _guess_port_type(port)
        controllers.append({"identifiers": identifiers, "ports": hub_info["ports"]})
    return controllers


def _controller_match(controller: dict) -> Optional[tuple]:
    bdf = controller["identifiers"].get("bdf")
    if not bdf or len(bdf) != 3:
        return None
    name = "-".join(str(i) for i in bdf)
    return name, {"pcidebug": ":".join(str(i) for i in bdf)}


def build_map_plist(controllers: list) -> Optional[dict]:
    """Контроллеры usbdump -> Info.plist карты UTBMap."""
    personalities = {}
    for controller in controllers:
        match = _controller_match(controller)
        ports = controller.get("ports") or []
        if match is None or not ports:
            continue
        personality_name, property_match = match
        prefix = _speed_prefix(ports)
        selected = sorted(ports, key=lambda p: p["index"])[:MAX_PORTS_PER_CONTROLLER]

        entry_ports = {}
        highest_index = 0
        for i, port in enumerate(selected, start=1):
            highest_index = max(highest_index, port["index"])
            connector = port["type"] if port["type"] is not None else port["guessed"]
            if connector is None:
                connector = TYPE_USB_A
            port_name = f"{prefix}{str(i).zfill(max(1, 4 - len(prefix)))}"
            entry_ports[port_name] = {
                "port": port["index"].to_bytes(4, byteorder="little"),
                "UsbConnector": connector,
            }
        if not entry_ports:
            continue
        personalities[personality_name] = {
            "CFBundleIdentifier": DRIVER_BUNDLE_IDENTIFIER,
            "IOClass": "USBToolBox",
            "IOProviderClass": "IOPCIDevice",
            "IOMatchCategory": "USBToolBox",
            "IOPropertyMatch": property_match,
            "IOProviderMergeProperties": {
                "ports": entry_ports,
                "port-count": highest_index.to_bytes(4, byteorder="little"),
            },
        }

    if not personalities:
        return None
    template = dict(_INFO_PLIST_TEMPLATE)
    template["IOKitPersonalities"] = personalities
    return template


def generate_auto_map(tmp_dir: Path, log=None) -> Optional[dict]:
    """Полный конвейер: DSDT -> usbdump.exe. None, если ничего не вышло."""
    from .cache_manager import cache_dir

    def _log(msg, level="info"):
        if log:
            log(msg)

    dsdt_plist = generate_dsdt_map(tmp_dir, log=_log)
    if dsdt_plist:
        return dsdt_plist

    cache = cache_dir() / "usbmap"
    zip_path = download_usbtoolbox_zip(cache, log=_log)
    if not zip_path:
        return None
    exe = extract_usbdump(zip_path, cache_dir() / "tools")
    if not exe:
        _log("В архиве USBToolBox нет usbdump.exe", "warn")
        return None

    _log("Снимаю топологию USB через usbdump…")
    controllers = dump_controllers(exe)
    if not controllers:
        _log("usbdump не нашёл контроллеров", "warn")
        return None

    plist = build_map_plist(controllers)
    if plist is None:
        _log("usbdump не дал пригодных портов", "warn")
        return None

    total_ports = sum(
        len(p["IOProviderMergeProperties"]["ports"])
        for p in plist["IOKitPersonalities"].values())
    _log(f"Карта из usbdump: {total_ports} порт(ов) в "
         f"{len(plist['IOKitPersonalities'])} контроллере(ах)", "ok")
    return plist


# ---------------------------------------------------------------------------
# Запись в EFI
# ---------------------------------------------------------------------------

def write_map_kext(plist: dict, kexts_dir: Path) -> Path:
    """Пишет карту как ``UTBMap.kext`` (только Info.plist, без бинарника)."""
    import plistlib

    kext_dir = Path(kexts_dir) / "UTBMap.kext" / "Contents"
    kext_dir.mkdir(parents=True, exist_ok=True)
    with open(kext_dir / "Info.plist", "wb") as f:
        plistlib.dump(plist, f)
    return kext_dir.parent


def summarise(plist: Optional[dict]) -> dict:
    """Краткая сводка карты для интерфейса."""
    if not plist:
        return {"controllers": 0, "ports": 0}
    personalities = plist.get("IOKitPersonalities") or {}
    ports = sum(len((p.get("IOProviderMergeProperties") or {}).get("ports") or {})
                for p in personalities.values())
    return {"controllers": len(personalities), "ports": ports}
