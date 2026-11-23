"""Прогресс-бар в стиле Apple: яблоко и тонкая скруглённая шкала."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QProgressBar


def _apple_path(rect: QRectF) -> QPainterPath:
    """Силуэт яблока: две доли, выемка сверху и листик."""
    path = QPainterPath()
    w, h = rect.width(), rect.height()
    left = QRectF(rect.left(), rect.top() + h * 0.18, w * 0.62, h * 0.82)
    right = QRectF(rect.left() + w * 0.38, rect.top() + h * 0.18, w * 0.62, h * 0.82)
    path.addEllipse(left)
    path.addEllipse(right)
    body = path.simplified()

    leaf = QPainterPath()
    leaf.moveTo(rect.center().x(), rect.top() + h * 0.16)
    leaf.cubicTo(rect.center().x() + w * 0.30, rect.top() - h * 0.10,
                 rect.center().x() + w * 0.52, rect.top() + h * 0.02,
                 rect.center().x() + w * 0.06, rect.top() + h * 0.22)
    leaf.closeSubpath()
    return body.united(leaf)


class AppleProgressBar(QProgressBar):
    """Обычный QProgressBar, но нарисованный как в macOS: яблоко + шкала."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.setFixedHeight(38)
        self.setRange(0, 100)
        self._accent = QColor("#2f6df6")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        height = float(self.height())
        glyph = min(height - 8.0, 26.0)
        apple_rect = QRectF(2.0, (height - glyph) / 2.0, glyph, glyph)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._accent))
        painter.drawPath(_apple_path(apple_rect))

        bar_left = glyph + 14.0
        bar_width = max(10.0, self.width() - bar_left - 2.0)
        groove = QRectF(bar_left, height / 2.0 - 5.0, bar_width, 10.0)

        painter.setBrush(QColor(255, 255, 255, 28))
        painter.drawRoundedRect(groove, 5.0, 5.0)

        span = self.maximum() - self.minimum()
        ratio = 0.0 if span <= 0 else (self.value() - self.minimum()) / span
        ratio = max(0.0, min(1.0, float(ratio)))
        if ratio > 0:
            fill = QRectF(groove.left(), groove.top(),
                          max(10.0, groove.width() * ratio), groove.height())
            painter.setBrush(self._accent)
            painter.drawRoundedRect(fill, 5.0, 5.0)

        if self.value() > 0:
            painter.setPen(QPen(QColor(255, 255, 255, 200)))
            painter.setFont(self.font())
            painter.drawText(
                QRectF(groove.right() + 6.0, 0, 44.0, height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                f"{round(ratio * 100)}%",
            )
        painter.end()
