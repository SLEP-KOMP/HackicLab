"""Консольный аудит OpenCore EFI.

Запуск:

    python tools/efi_doctor.py "Y:\\EFI"
    python tools/efi_doctor.py            # найдёт единственный смонтированный EFI

Код возврата: 0 — замечаний-ошибок нет, 1 — есть ошибки, 2 — не найдена цель.
Только чтение, права администратора не нужны.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hackiclab.analyzer.efi_health import main

if __name__ == "__main__":
    sys.exit(main())
