"""Безопасная правка готового config.plist (без ProperTree).

Слой поверх plistlib: точечные get/set по dot-пути, boot-args, SIP, Timeout,
SecureBootModel, SMBIOS-модель и подсказки ig-platform-id. Перед любой
записью делается резервная копия ``config.plist.bak``, а после дампа файл
проверяется обратным чтением — сломанный plist не сохранится.

Значения приводятся к типу исходного ключа: data остаётся data, bool — bool,
int — int (риск из плана «битые типы» закрыт).
"""

from __future__ import annotations

import plistlib
import shutil
from pathlib import Path
from typing import Any

from ..scanner.models import HardwareProfile
from .config_gen import IG_PLATFORM_IDS

NVRAM_KEY = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
IGPU_PATH = "PciRoot(0x0)/Pci(0x2,0x0)"

#: Значения SecureBootModel, которые OpenCore точно понимает.
SECURE_BOOT_MODELS = ("Default", "Disabled", "j160", "x86legacy")


# --- чтение и запись файла ------------------------------------------------

def load_config(path: Path) -> dict:
    """Читает config.plist в dict."""
    data = plistlib.loads(Path(path).read_bytes())
    if not isinstance(data, dict):
        raise ValueError("config.plist не является словарём")
    return data


def save_config(path: Path, cfg: dict) -> Path:
    """Пишет config.plist с резервной копией и проверкой результата.

    Возвращает путь к резервной копии (она создаётся всегда, если был файл).
    """
    path = Path(path)
    backup = path.with_suffix(".plist.bak")
    if path.exists():
        shutil.copy2(str(path), str(backup))
    blob = plistlib.dumps(cfg, fmt=plistlib.FMT_XML, sort_keys=False)
    try:
        check = plistlib.loads(blob)
        if not isinstance(check, dict):
            raise ValueError("результат не словарь")
    except Exception as e:
        raise RuntimeError(f"Не удалось сериализовать config.plist: {e}") from e
    path.write_bytes(blob)
    return backup


# --- универсальные get/set ------------------------------------------------

def _resolve_path(cfg: dict, path: str) -> tuple[dict, str]:
    parts = path.split(".")
    node: Any = cfg
    for part in parts[:-1]:
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"Ключ '{part}' не найден в {path}")
        node = node[part]
    if not isinstance(node, dict):
        raise KeyError(f"{path}: родитель не словарь")
    return node, parts[-1]


def get_value(cfg: dict, path: str, default: Any = None) -> Any:
    try:
        node, key = _resolve_path(cfg, path)
        return node.get(key, default)
    except KeyError:
        return default


def set_value(cfg: dict, path: str, value: Any) -> None:
    node, key = _resolve_path(cfg, path)
    node[key] = value


def coerce_like(existing: Any, raw: Any) -> Any:
    """Приводит новое значение к типу существующего (data/bool/int/str)."""
    if isinstance(raw, type(existing)) and not isinstance(existing, bool):
        return raw
    if isinstance(existing, bool):
        if isinstance(raw, str):
            return raw.strip().lower() in ("1", "true", "yes", "on", "вкл")
        return bool(raw)
    if isinstance(existing, bytes):
        if isinstance(raw, bytes):
            return raw
        text = str(raw).replace(" ", "").replace(":", "")
        return bytes.fromhex(text)
    if isinstance(existing, int) and not isinstance(existing, bool):
        try:
            return int(str(raw), 0)
        except ValueError:
            return int(raw)
    return str(raw)


def set_typed_value(cfg: dict, path: str, raw: Any) -> None:
    """set с сохранением типа существующего ключа."""
    existing = get_value(cfg, path)
    set_value(cfg, path, coerce_like(existing, raw) if existing is not None else raw)


# --- boot-args ------------------------------------------------------------

def parse_boot_args(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for token in (text or "").split():
        if "=" in token:
            key, value = token.split("=", 1)
            result[key] = value
        else:
            result[token] = True
    return result


def serialize_boot_args(args: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in args.items():
        if value is True:
            parts.append(key)
        elif value is not False and value not in ("", None):
            parts.append(f"{key}={value}")
    return " ".join(parts)


#: Готовые наборы флагов: одна кнопка — нужное сочетание.
BOOT_ARG_PRESETS: dict[str, tuple[str, ...]] = {
    "verbose": ("-v", "debug=0x100", "keepsyms=1"),
    "no_egpu": ("-wegnoegpu",),
    "safe": ("-x",),
}


def add_boot_args(text: str, *flags: str) -> str:
    """Добавляет флаги в строку boot-args без дублей."""
    args = parse_boot_args(text)
    for flag in flags:
        if "=" in flag:
            key, value = flag.split("=", 1)
            args[key] = value
        else:
            args[flag] = True
    return serialize_boot_args(args)


def suggest_audio_layouts(codec: str, limit: int = 3) -> tuple[int, ...]:
    """Первые варианты layout-id для кодека из базы AppleALC."""
    from ..knowledge.audio_layouts import layouts_for

    return layouts_for(codec)[:limit]


def _nvram_dict(cfg: dict) -> dict:
    nvram = cfg.setdefault("NVRAM", {})
    add = nvram.setdefault("Add", {})
    return add.setdefault(NVRAM_KEY, {})


def get_boot_args(cfg: dict) -> str:
    raw = _nvram_dict(cfg).get("boot-args", "")
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return str(raw)


def set_boot_args(cfg: dict, text: str) -> None:
    section = _nvram_dict(cfg)
    existing = section.get("boot-args", "")
    section["boot-args"] = coerce_like(existing, text) if existing != "" else str(text)


# --- SIP ------------------------------------------------------------------

def decode_csr(raw: Any) -> int:
    if isinstance(raw, bytes):
        return int.from_bytes(raw[:4].ljust(4, b"\x00"), "little")
    if isinstance(raw, int):
        return raw
    return 0


def get_sip_enabled(cfg: dict) -> bool:
    """SIP включён, если csr-active-config нулевой (или его нет)."""
    return decode_csr(_nvram_dict(cfg).get("csr-active-config", b"")) == 0


def set_sip(cfg: dict, enabled: bool) -> None:
    """0x0 — SIP включён; 0x67 — ослаблен (как в config_gen.disable_sip)."""
    section = _nvram_dict(cfg)
    section["csr-active-config"] = bytes(4) if enabled else bytes([0x67, 0x00, 0x00, 0x00])


# --- Timeout / SecureBootModel / SMBIOS -----------------------------------

def get_timeout(cfg: dict) -> int:
    try:
        return int(get_value(cfg, "Misc.Boot.Timeout", 5))
    except (TypeError, ValueError):
        return 5


def set_timeout(cfg: dict, seconds: int) -> None:
    cfg.setdefault("Misc", {}).setdefault("Boot", {})["Timeout"] = max(0, int(seconds))


def get_secure_boot_model(cfg: dict) -> str:
    return str(get_value(cfg, "Misc.Security.SecureBootModel", "Disabled"))


def set_secure_boot_model(cfg: dict, model: str) -> None:
    if model not in SECURE_BOOT_MODELS:
        raise ValueError(f"Недопустимое значение SecureBootModel: {model}")
    cfg.setdefault("Misc", {}).setdefault("Security", {})["SecureBootModel"] = model


def get_smbios(cfg: dict) -> str:
    return str(get_value(cfg, "PlatformInfo.Generic.SystemProductName", ""))


def set_smbios(cfg: dict, model: str) -> None:
    cfg.setdefault("PlatformInfo", {}).setdefault("Generic", {})["SystemProductName"] = model


# --- iGPU подсказки -------------------------------------------------------

_FB_LABELS = {
    "snb_mobile": "Sandy Bridge — ноутбук",
    "snb_desktop": "Sandy Bridge — десктоп",
    "snb_headless": "Sandy Bridge — без монитора",
    "ivb_mobile": "Ivy Bridge — ноутбук",
    "ivb_desktop": "Ivy Bridge — десктоп",
    "hsw_mobile": "Haswell — ноутбук",
    "hsw_desktop": "Haswell — десктоп",
    "skl_mobile": "Skylake — ноутбук",
    "skl_desktop": "Skylake — десктоп",
    "hd620": "Kaby Lake — ноутбук (HD 620)",
    "hd630_dt": "Kaby Lake — десктоп (HD 630)",
    "hd630_mb": "Kaby Lake — ноутбук (HD 630)",
    "uhd630_dt": "Coffee Lake — десктоп (UHD 630)",
    "uhd630_mb": "Coffee Lake — ноутбук (UHD 630)",
    "iris_ice": "Ice Lake — ноутбук (Iris Plus)",
}

_FB_KEYS_BY_GEN = {
    2: ("snb_mobile", "snb_desktop", "snb_headless"),
    3: ("ivb_mobile", "ivb_desktop"),
    4: ("hsw_mobile", "hsw_desktop"),
    6: ("skl_mobile", "skl_desktop"),
    7: ("hd620", "hd630_dt", "hd630_mb"),
    8: ("uhd630_dt", "uhd630_mb"),
    9: ("uhd630_dt", "uhd630_mb"),
    10: ("hd620", "hd630_dt"),
}


def suggest_framebuffers(profile: HardwareProfile) -> list[tuple[str, str]]:
    """Варианты ig-platform-id для iGPU профиля: [(0x…, подпись), …]."""
    out: list[tuple[str, str]] = []
    for key in _FB_KEYS_BY_GEN.get(profile.cpu.generation, ()):
        raw = IG_PLATFORM_IDS.get(key)
        if not raw:
            continue
        value = int.from_bytes(raw, "little")
        out.append((f"0x{value:08X}", str(_FB_LABELS.get(key) or key)))
    return out


def get_igpu_platform_id(cfg: dict) -> str:
    props = get_value(cfg, f"DeviceProperties.Add.{IGPU_PATH}", None)
    if not isinstance(props, dict):
        return ""
    raw = props.get("AAPL,ig-platform-id", props.get("AAPL,snb-platform-id"))
    return decode_csr(raw).to_bytes(4, "little").hex() if isinstance(raw, bytes) else ""
