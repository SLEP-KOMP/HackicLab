"""Плитки выбора темы в виде экранов монитора.

Виджет рисуется вручную: рамка монитора, градиентный «экран», подставка и
подпись. Так переключатель темы выглядит наглядно и не требует картинок,
которые пришлось бы лицензировать отдельно.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPalette, QPen
from PySide6.QtWidgets import QAbstractButton

from ..themes import preview


class MonitorButton(QAbstractButton):
    """Кнопка-монитор: клик выбирает тему, галочка показывает текущую."""

    WIDTH = 136
    HEIGHT = 116

    def __init__(self, key: str, label: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.setText(label)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(label)
        self.setAccessibleName(label)

    def sizeHint(self) -> QSize:
        return QSize(self.WIDTH, self.HEIGHT)

    def minimumSizeHint(self) -> QSize:
        return QSize(self.WIDTH - 12, self.HEIGHT - 10)

    def _colors(self) -> tuple[QColor, QColor, QColor, QColor]:
        """Цвета экрана-превью и акцента; текст берём из текущей палитры окна.

        Раньше подпись красилась цветом самой темы, и у тёмных тем она была
        невидимой на светлом фоне списка.
        """
        top, bottom = preview(self.key)
        return (
            QColor(top),
            QColor(bottom),
            QColor(self.palette().color(QPalette.Highlight)),
            QColor(self.palette().color(QPalette.WindowText)),
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        bezel_w = min(width - 8, self.WIDTH - 10)
        x = (width - bezel_w) / 2
        bezel_h = 76.0
        top_c, bottom_c, accent, text_c = self._colors()

        # рамка монитора
        pen = QPen(accent if self.isChecked() else QColor(120, 124, 140))
        pen.setWidth(2 if self.isChecked() else 1)
        painter.setPen(pen)
        painter.setBrush(QColor(28, 29, 36, 210))
        painter.drawRoundedRect(int(x), 4, int(bezel_w), int(bezel_h), 9, 9)

        # экран темы
        screen_x = x + 6
        screen_w = bezel_w - 12
        screen_h = bezel_h - 12
        gradient = QLinearGradient(screen_x, 10, screen_x, 10 + screen_h)
        gradient.setColorAt(0.0, top_c)
        gradient.setColorAt(1.0, bottom_c)
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(int(screen_x), 10, int(screen_w), int(screen_h), 5, 5)

        # блик на экране
        painter.setBrush(QColor(255, 255, 255, 26))
        painter.drawRoundedRect(int(screen_x), 10, int(screen_w), int(screen_h / 3), 5, 5)

        # подставка
        painter.setBrush(QColor(110, 114, 130))
        stand_w = 22
        painter.drawRect(int(width / 2 - stand_w / 2), int(bezel_h + 4),
                         stand_w, 8)
        painter.drawRoundedRect(int(width / 2 - 26), int(bezel_h + 12), 52, 5, 2, 2)

        # подпись
        painter.setPen(QPen(text_c))
        font = painter.font()
        font.setPointSizeF(9.0)
        font.setBold(self.isChecked())
        painter.setFont(font)
        label_rect = self.rect().adjusted(0, int(bezel_h + 18), 0, 0)
        painter.drawText(label_rect, Qt.AlignHCenter | Qt.AlignTop, self.text())

        # отметка выбора
        if self.isChecked():
            painter.setPen(Qt.NoPen)
            painter.setBrush(accent)
            painter.drawEllipse(int(x + bezel_w - 20), 14, 14, 14)
            painter.setPen(QPen(QColor(255, 255, 255)))
            font2 = painter.font()
            font2.setPointSizeF(7.5)
            font2.setBold(True)
            painter.setFont(font2)
            painter.drawText(int(x + bezel_w - 20), 14, 14, 14, Qt.AlignCenter, "✓")

        painter.end()
