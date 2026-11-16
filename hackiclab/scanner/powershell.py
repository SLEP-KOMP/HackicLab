"""ООП-обёртка над PowerShell для быстрых WMI/PnP/CIM-запросов на Windows."""

from __future__ import annotations

import json
import subprocess


class PowerShell:
    """Инкапсулирует выполнение PowerShell с UTF-8 выводом и JSON-парсингом."""

    def __init__(self):
        self._cache: dict = {}

    @staticmethod
    def run(script: str, timeout: int = 15) -> str:
        """Выполняет PowerShell-скрипт, возвращает stdout как текст (UTF-8)."""
        wrapped = "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $ProgressPreference='SilentlyContinue'; " + script
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", wrapped],
                capture_output=True, timeout=timeout,
            )
            return r.stdout.decode("utf-8", errors="replace").strip()
        except Exception:
            return ""

    @staticmethod
    def run_json(script: str, timeout: int = 20):
        """Выполняет скрипт и возвращает распарсенный JSON (список/словарь/None).

        handleScript должен сам выполнить ConvertTo-Json, если нужен объект.
        Исправлена проблема двойного кодирования: раньше к скрипту приклеивался
        ещё один ConvertTo-Json, и результат представлял JSON-строку внутри JSON.
        """
        out = PowerShell.run(script, timeout=timeout)
        if not out:
            return None
        # Если JSON приехал "строкой внутри строки", разворачиваем до реального объекта
        try:
            parsed = json.loads(out)
        except Exception:
            return None
        depth = 0
        while isinstance(parsed, str) and depth < 3:
            try:
                parsed = json.loads(parsed)
            except Exception:
                break
            depth += 1
        return parsed

    def cached(self, key: str, script: str, timeout: int = 20) -> str:
        """Выполняет скрипт с кэшем по ключу: повторные вызовы бесплатны.

        Кэш принадлежит экземпляру, поэтому ``clear_cache`` действительно его
        очищает (раньше вызывался несуществующий ``run.cached.cache_clear``).
        """
        if key in self._cache:
            return str(self._cache[key])
        value = PowerShell.run(script, timeout=timeout)
        self._cache[key] = value
        return value

    def clear_cache(self) -> None:
        self._cache.clear()


ps = PowerShell()
