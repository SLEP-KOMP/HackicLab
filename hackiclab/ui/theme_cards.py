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

    def __init__(self, variant: str, label: str = "", parent=None):
        super().__init__(parent)
        self.variant = variant
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(4)
        self.preview = QLabel()
        self.preview.setFixedSize(_PREVIEW_W, _PREVIEW_H)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet(
            "border:1px solid #3a3f4b;border-radius:8px;background:#14161c;")
        v.addWidget(self.preview)
        self.check = QCheckBox(label or themes.variant_label(variant, tr.current))
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
        self.custom_dirs: dict[str, Path] = {}
        self._grid = QGridLayout(); self._grid.setSpacing(8)
        self._next_index = 0
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(6)
        head = QHBoxLayout()
        head.addWidget(QLabel(tr.t("themes.title")))
        head.addStretch()
        self.previews_btn = QPushButton(tr.t("themes.previews"))
        self.previews_btn.setObjectName("ghost")
        self.previews_btn.setToolTip(tr.t("themes.previews_hint"))
        self.previews_btn.clicked.connect(self.load_previews)
        head.addWidget(self.previews_btn)
        self.import_btn = QPushButton(tr.t("themes.import"))
        self.import_btn.setObjectName("ghost")
        self.import_btn.setToolTip(tr.t("themes.import_hint"))
        self.import_btn.clicked.connect(self.import_theme)
        head.addWidget(self.import_btn)
        self.all_btn = QPushButton(tr.t("themes.select_all"))
        self.all_btn.setObjectName("ghost")
        self.all_btn.clicked.connect(self.select_all)
        head.addWidget(self.all_btn)
        v.addLayout(head)

        for name, _ru, _en in themes.VARIANTS:
            variant = f"{themes.THEME_NAME}\\{name}"
            self._add_card(variant, themes.variant_label(variant, tr.current),
                           themes.variant_dir(self._resources_root(), variant))
        v.addLayout(self._grid)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        self._restore_cached_resources()

    def _add_card(self, variant: str, label: str, folder: Optional[Path]) -> _Card:
        card = _Card(variant, label, self)
        card.check.toggled.connect(lambda _on: self.changed.emit())
        self._cards[variant] = card
        self._grid.addWidget(card, self._next_index // 3, self._next_index % 3)
        self._next_index += 1
        if folder and Path(folder).is_dir():
            card.set_preview(themes.preview_pngs_from_dir(Path(folder)))
            if themes.is_custom(variant):
                self.custom_dirs[variant] = Path(folder)
        return card

    def import_theme(self) -> None:
        """Сторонняя тема из папки: добавляется карточкой и копируется в EFI."""
        from PySide6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(self, tr.t("themes.import"))
        if not folder:
            return
        path = Path(folder)
        if not themes.looks_like_theme(path):
            self.status.setText(tr.t("themes.import_hint"))
            return
        variant = themes.custom_id(path)
        if variant in self._cards:
            self._cards[variant].check.setChecked(True)
            self.changed.emit()
            return
        card = self._add_card(variant, path.name, path)
        card.check.setChecked(True)
        self.changed.emit()

    # --- превью и импорт ---

    @staticmethod
    def _resources_root() -> Path:
        from ..builder.cache_manager import cache_dir

        return cache_dir() / "resources"

    def _restore_cached_resources(self) -> None:
        """Если иконки уже скачаны ранее — сразу показываем превью."""
        root = self._resources_root() / "Image" / themes.THEME_NAME
        if root.is_dir():
            self.set_resources(self._resources_root())

    def load_previews(self) -> None:
        """Скачивает официальные иконки OcBinaryData и рисует по ним превью."""
        from PySide6.QtWidgets import QApplication

        from ..builder.canopy import ensure_resources

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            written = ensure_resources(self._resources_root())
        finally:
            QApplication.restoreOverrideCursor()
        self.set_resources(self._resources_root())
        if written:
            self.status.setText(tr.t("themes.previews").format(count=written)
                                if "{count}" in tr.t("themes.previews") else "")
        else:
            self.status.setText("")
        self.changed.emit()

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
