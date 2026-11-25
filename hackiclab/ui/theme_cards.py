"""Карточки тем OpenCanopy: превью из реальных иконок варианта.

Пользователь выбирает один вариант (он станет PickerVariant) или несколько —
тогда в EFI попадут все отмеченные, и их можно переключать в самом меню.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..knowledge import themes

_PREVIEW_W = 168
_PREVIEW_H = 96
_ICON = 40


class _Card(QWidget):
    """Карточка варианта: чекбокс, превью и подпись."""

    def __init__(self, variant: str, parent=None):
        super().__init__(parent)
        self.variant = variant
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(4)
        self.preview = QLabel()
        self.preview.setFixedSize(_PREVIEW_W, _PREVIEW_H)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet(
            "border:1px solid #3a3f4b;border-radius:8px;background:#14161c;")
        v.addWidget(self.preview)
        self.check = QCheckBox(themes.variant_label(variant, tr.current))
        self.check.setToolTip(themes.picker_variant(variant))
        v.addWidget(self.check)
        self.set_preview([])

    def set_preview(self, pngs: list[bytes]):
        """Собирает превью из PNG-иконок темы; без иконок — заглушка."""
        canvas = QPixmap(_PREVIEW_W, _PREVIEW_H)
        canvas.fill(QColor("#14161c"))
        from PySide6.QtGui import QPainter

        painter = QPainter(canvas)
        if pngs:
            step = _PREVIEW_W // (len(pngs[:4]) + 1)
            for i, data in enumerate(pngs[:4], start=1):
                pix = QPixmap()
                if not pix.loadFromData(data):
                    continue
                scaled = pix.scaled(_ICON, _ICON, Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
                painter.drawPixmap(
                    step * i - scaled.width() // 2,
                    (_PREVIEW_H - scaled.height()) // 2, scaled)
        painter.end()
        self.preview.setPixmap(canvas)


class ThemeCards(QWidget):
    """Сетка карточек тем с выбором одной, нескольких или всех."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, _Card] = {}
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        head = QHBoxLayout()
        head.addWidget(QLabel(tr.t("themes.title")))
        head.addStretch()
        self.all_btn = QPushButton(tr.t("themes.select_all"))
        self.all_btn.setObjectName("ghost")
        self.all_btn.clicked.connect(self.select_all)
        head.addWidget(self.all_btn)
        v.addLayout(head)

        grid = QGridLayout(); grid.setSpacing(8)
        for index, (name, _ru, _en) in enumerate(themes.VARIANTS):
            variant = f"{themes.THEME_NAME}\\{name}"
            card = _Card(variant, self)
            card.check.toggled.connect(lambda _on: self.changed.emit())
            self._cards[variant] = card
            grid.addWidget(card, index // 3, index % 3)
        v.addLayout(grid)

    # --- данные ---

    def selection(self) -> set[str]:
        return {variant for variant, card in self._cards.items()
                if card.check.isChecked()}

    def set_selection(self, variants) -> None:
        chosen = set(variants or ())
        for variant, card in self._cards.items():
            card.check.blockSignals(True)
            card.check.setChecked(variant in chosen)
            card.check.blockSignals(False)
        self.changed.emit()

    def select_all(self) -> None:
        self.set_selection(self._cards.keys())

    def set_resources(self, resources: Optional[Path]) -> None:
        """Подтягивает превью из реальных иконок скачанных Resources."""
        for variant, card in self._cards.items():
            pngs = themes.preview_pngs(resources, variant) if resources else []
            card.set_preview(pngs)
