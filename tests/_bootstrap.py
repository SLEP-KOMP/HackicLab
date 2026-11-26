"""Общие настройки тестов: делают корень проекта импортируемым."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("HACKICLAB_NO_UPDATES", "1")
# Тесты не должны видеть реальный (в т.ч. сетевой) кэш пользователя:
# иначе результаты зависят от того, что уже скачано на его машине.
os.environ.setdefault("HACKICLAB_CACHE",
                      str(Path(tempfile.mkdtemp(prefix="hackiclab-test-cache-"))))

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
