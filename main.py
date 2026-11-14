"""Точка входа в приложение HackicLab."""

import sys
from pathlib import Path

# Гарантируем, что корень пакета доступен
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hackiclab.ui import run_app  # noqa: E402


if __name__ == "__main__":
    sys.exit(run_app())