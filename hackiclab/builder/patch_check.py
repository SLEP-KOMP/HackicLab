"""Проверка набора Kernel/Patch перед записью в config.plist.

AMD_Vanilla содержит несколько независимых патчей одной функции ядра
(_cpuid_set_generic_info правится в разных местах) — это нормально. Опасен
другой случай: два варианта ОДНОЙ И ТОЙ ЖЕ операции с пересекающимися
диапазонами ядра. Тогда OpenCore применит оба, и второй может испортить уже
пропатченный код.

«Операцию» берём из комментария: `автор | функция | что делает | версия`.
Сравниваем функцию и описание, а не только функцию.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_VERSION = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def _parts(value: str) -> tuple[int, ...]:
    match = _VERSION.match(str(value or "").strip())
    if not match:
        return (0,)
    return tuple(int(x) if x is not None else 99 for x in match.groups())


def _ranges_overlap(left: dict, right: dict) -> bool:
    l_lo, l_hi = _parts(left.get("MinKernel", "")), _parts(left.get("MaxKernel", ""))
    r_lo, r_hi = _parts(right.get("MinKernel", "")), _parts(right.get("MaxKernel", ""))
    return l_lo <= r_hi and r_lo <= l_hi


def _operation(patch: dict) -> tuple[str, str]:
    """(функция, описание операции) из комментария «автор | функция | описание»."""
    parts = [p.strip().lower() for p in str(patch.get("Comment", "")).split("|")]
    function = parts[1] if len(parts) > 1 else ""
    description = parts[2] if len(parts) > 2 else ""
    return function, description


@dataclass(frozen=True)
class PatchConflict:
    left: str
    right: str
    range_left: str
    range_right: str

    def describe(self) -> str:
        return (f"два варианта одной операции перекрываются: «{self.left}» "
                f"({self.range_left}) и «{self.right}» ({self.range_right})")


def find_conflicts(patches: list) -> list[PatchConflict]:
    """Пары включённых патчей одной операции с пересекающимися диапазонами."""
    enabled = [p for p in (patches or []) if p.get("Enabled", True)]
    conflicts: list[PatchConflict] = []
    for index, left in enumerate(enabled):
        for right in enabled[index + 1:]:
            if left.get("Identifier") != right.get("Identifier"):
                continue
            l_func, l_desc = _operation(left)
            r_func, r_desc = _operation(right)
            if not l_func or (l_func, l_desc) != (r_func, r_desc):
                continue
            if not _ranges_overlap(left, right):
                continue
            conflicts.append(PatchConflict(
                left=str(left.get("Comment", ""))[:90],
                right=str(right.get("Comment", ""))[:90],
                range_left=f"{left.get('MinKernel', '')}..{left.get('MaxKernel', '')}",
                range_right=f"{right.get('MinKernel', '')}..{right.get('MaxKernel', '')}",
            ))
    return conflicts
