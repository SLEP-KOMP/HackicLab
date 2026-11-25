"""Wi-Fi-профили Windows → WiFiConfig.plist для кекста itlwm.

itlwm без меню Wi-Fi (режим itlwm + HeliPort) подключается к сети сам, если
рядом с кекстом лежит ``Contents/WiFiConfig.plist`` с SSID и паролем. Профили
берём у Windows: ``netsh wlan show profiles`` + ``netsh wlan export profile``.
"""

from __future__ import annotations

import plistlib
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

#: Сколько профилей максимум выгружаем (защита от огромного списка).
MAX_PROFILES = 20


def parse_profile(xml_text: str) -> tuple[str, str] | None:
    """SSID и пароль из XML-профиля WLAN (``netsh wlan export``)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    # Профиль приходит с default-namespace, поэтому ищем по локальному имени.
    ssid = ""
    password = ""
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "SSID":
            for child in el:
                if child.tag.rsplit("}", 1)[-1] == "name" and (child.text or "").strip():
                    ssid = child.text.strip()
        elif tag == "keyMaterial":
            password = el.text or ""
    return (ssid, password) if ssid else None


def build_plist(entries: list[tuple[str, str]]) -> bytes:
    """Двоичный plist в формате itlwm: массив словарей ssid/password."""
    data = [{"ssid": ssid, "password": password} for ssid, password in entries]
    return plistlib.dumps(data, fmt=plistlib.FMT_XML, sort_keys=False)


def export_windows_profiles(timeout: int = 20) -> list[tuple[str, str]]:
    """Экспортирует профили текущего пользователя Windows и читает пароли."""
    out: list[tuple[str, str]] = []
    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run(
                ["netsh", "wlan", "export", "profile", "key", "clear", f"folder={tmp}"],
                capture_output=True, timeout=timeout, check=False)
        except (OSError, subprocess.SubprocessError):
            return out
        for path in sorted(Path(tmp).glob("*.xml"))[:MAX_PROFILES]:
            try:
                parsed = parse_profile(path.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
            if parsed and parsed[0] not in {ssid for ssid, _ in out}:
                out.append(parsed)
    return out


def write_wifi_config(kext_dir: Path, entries: list[tuple[str, str]]) -> Path | None:
    """Кладёт WiFiConfig.plist внутрь itlwm.kext; без профилей ничего не делает."""
    if not entries:
        return None
    contents = Path(kext_dir) / "Contents"
    if not contents.is_dir():
        return None
    target = contents / "WiFiConfig.plist"
    try:
        target.write_bytes(build_plist(entries))
    except OSError:
        return None
    return target
