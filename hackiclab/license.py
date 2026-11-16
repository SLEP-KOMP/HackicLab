"""Лицензирование и монетизация HackicLab.

Модель: «сначала бесплатно, потом платно».
- Free: полное сканирование железа, ручная сборка структуры EFI,
  анализ своих файлов, рекомендации.
- Premium (задел): автоматическая загрузка OpenCore/kext по профилю,
  полный поток «одной кнопкой», авто-обновления, cloud-профили.

Ключ лицензии (если есть) хранится в ~/.hackiclab/license.json и определяет
выпуск. Механика intentionally локальная и прозрачная — на первом этапе всё
доступно бесплатно (trial), флаги готовят будущую монетизацию.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass, field
from enum import Enum

from .builder.cache_manager import app_home


class Edition(Enum):
    FREE = "free"
    PREMIUM = "premium"


@dataclass
class License:
    edition: Edition = Edition.FREE
    key: str = ""
    device_id: str = ""
    activated: bool = False
    features: set = field(default_factory=set)
    meta: dict = field(default_factory=dict)

    @property
    def is_premium(self) -> bool:
        return self.edition == Edition.PREMIUM and self.activated

    def can(self, feature: str) -> bool:
        """Проверка доступности функции.

        Free-выпуск по умолчанию пробует все функции (первый этап бесплатен),
        но 'autodownload' и 'autobuild_full' помечены как premium-кандидаты.
        """
        if self.is_premium:
            return True
        # задел под будущую монетизацию
        return feature not in ("autodownload", "autobuild_full", "cloud")


PREMIUM_FEATURES = {
    "autodownload": "Автозагрузка OpenCore и kext по профилю",
    "autobuild_full": "Полная сборка EFI одной кнопкой",
    "cloud": "Облачные профили и синхронизация",
    "ocvalidate": "Валидация config.plist через ocvalidate",
}


def _device_id() -> str:
    """Стабильный идентификатор устройства (без сбора PII).

    hash() от строк в Python рандомизирован между процессами (PYTHONHASHSEED),
    поэтому раньше идентификатор менялся при каждом запуске. Здесь только
    детерминированные данные: имя машины, архитектура и MAC узла.
    """
    try:
        import platform
        import uuid
        node = platform.node()
        machine = platform.machine()
        mac = uuid.getnode()
        h = hashlib.sha256(f"{node}:{machine}:{mac}".encode()).hexdigest()[:24]
        return h
    except Exception:
        return secrets.token_hex(12)


class LicenseManager:
    """Управляет локальной лицензией."""

    def __init__(self):
        self.file = app_home() / "license.json"
        self.license = self._load()

    def _load(self) -> License:
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
            lic = License(
                edition=Edition(data.get("edition", "free")),
                key=data.get("key", ""),
                device_id=data.get("device_id", "") or _device_id(),
                activated=bool(data.get("activated")),
                features=set(data.get("features", [])),
                meta=data.get("meta", {}),
            )
            if not lic.device_id:
                lic.device_id = _device_id()
            return lic
        except Exception:
            lic = License(device_id=_device_id())
            self._save(lic)
            return lic

    def _save(self, lic: License):
        data = {
            "edition": lic.edition.value,
            "key": lic.key,
            "device_id": lic.device_id,
            "activated": lic.activated,
            "features": sorted(lic.features),
            "meta": lic.meta,
        }
        try:
            self.file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def activate_premium(self, key: str) -> tuple[bool, str]:
        """Активация премиум по ключу (заглушка).

        В будущем здесь будет валидация через сервер (подпись ключа + device_id).
        Сейчас принимает ключ формата HILC-XXXX-XXXX-XXXX.
        """
        key = (key or "").strip()
        if not key:
            return False, "empty"
        # простая локальная валидация формата (демо)
        if len(key) >= 16 and key.startswith("HILC"):
            self.license.edition = Edition.PREMIUM
            self.license.key = key
            self.license.activated = True
            self.license.features = set(PREMIUM_FEATURES)
            self._save(self.license)
            return True, "ok"
        return False, "invalid"

    def status(self) -> dict:
        return {
            "edition": self.license.edition.value,
            "is_premium": self.license.is_premium,
            "device_id": self.license.device_id,
            "features": sorted(self.license.features),
            "licensed_features": list(PREMIUM_FEATURES),
        }

    def can(self, feature: str) -> bool:
        """Проверка доступности функции (делегирует в License)."""
        return self.license.can(feature)


# Глобальный синглтон
license_manager = LicenseManager()
