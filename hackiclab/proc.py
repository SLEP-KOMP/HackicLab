"""Запуск внешних процессов без всплывающих консольных окон.

Приложение собрано как GUI (``console=False``), поэтому дочерние консольные
процессы — PowerShell, diskpart, ocvalidate, usbdump — получали собственное
окно консоли. ``CREATE_NO_WINDOW`` и ``STARTUPINFO`` с ``SW_HIDE`` убирают это
окно, не меняя поведение и вывод самого процесса.
"""

from __future__ import annotations

import subprocess
import sys

_WINDOWS = sys.platform == "win32"

#: Флаг «без окна консоли»: CREATE_NO_WINDOW в Windows, 0 в остальных системах.
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if _WINDOWS else 0


def startupinfo():
    """STARTUPINFO с полностью скрытым окном (None вне Windows)."""
    if not _WINDOWS:
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = subprocess.SW_HIDE
    return info


def hidden_kwargs() -> dict:
    """Аргументы subprocess, скрывающие окно консоли."""
    if not _WINDOWS:
        return {}
    return {"creationflags": CREATE_NO_WINDOW, "startupinfo": startupinfo()}


def run(args, **kwargs):
    """``subprocess.run`` без окна консоли."""
    for key, value in hidden_kwargs().items():
        kwargs.setdefault(key, value)
    return subprocess.run(args, **kwargs)


def popen(args, **kwargs):
    """``subprocess.Popen`` без окна консоли."""
    for key, value in hidden_kwargs().items():
        kwargs.setdefault(key, value)
    return subprocess.Popen(args, **kwargs)
