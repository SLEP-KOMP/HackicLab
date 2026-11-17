"""Приветствие на главной: монитор с macOS и карточки версий."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

HERO_DIR = Path(__file__).resolve().parent.parent / "assets" / "hero"

WALLPAPERS = {
    "macOS Tahoe": "hero-sequoia.jpg",
    "macOS Sequoia": "hero-sequoia.jpg",
    "macOS Sonoma": "hero-sonoma.jpg",
    "macOS Ventura": "hero-ventura.jpg",
    "macOS Monterey": "hero-monterey.jpg",
    "macOS Big Sur": "hero-monterey.jpg",
    "macOS Catalina": "hero-sonoma.jpg",
    "macOS Mojave": "hero-ventura.jpg",
    "macOS High Sierra": "hero-ventura.jpg",
}

_cache: dict[str, QPixmap] = {}


def wallpaper(name: str) -> QPixmap:
    """Обои для версии macOS; кэшируются, чтобы не читать файл на каждый кадр."""
    file_name = WALLPAPERS.get(name, "hero-sonoma.jpg")
    if file_name not in _cache:
        path = HERO_DIR / file_name
        _cache[file_name] = QPixmap(str(path)) if path.exists() else QPixmap()
    return _cache[file_name]


def cover_pixmap(pix: QPixmap, width: float, height: float) -> QPixmap:
    """Кадрирует обои по центру под нужные пропорции (без белых полей)."""
    if pix.isNull() or width <= 0 or height <= 0:
        return pix
    scaled = pix.scaled(
        int(width), int(height),
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    # обрезаем по центру с запасом: у сгенерированных обоев бывает светлая
    # кромка, и она лезет в карточку белой полосой
    zoom = 1.06
    crop_w = max(1, int(int(width) / zoom))
    crop_h = max(1, int(int(height) / zoom))
    left = max(0, (scaled.width() - crop_w) // 2)
    top = max(0, (scaled.height() - crop_h) // 2)
    return scaled.copy(left, top, crop_w, crop_h).scaled(
        int(width), int(height),
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


class MonitorHero(QWidget):
    """Монитор: корпус, подставка и экран с обоями macOS."""

    def __init__(self, parent=None, version: str = "macOS Sonoma"):
        super().__init__(parent)
        self._version = version
        self.setMinimumHeight(232)

    def set_version(self, version: str):
        self._version = version
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        width = float(self.width())
        height = float(self.height())
        bezel = QRectF(6.0, 6.0, width - 12.0, height * 0.72)
        screen = bezel.adjusted(8.0, 8.0, -8.0, -8.0)

        painter.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
        painter.setBrush(QColor(22, 23, 30))
        painter.drawRoundedRect(bezel, 18.0, 18.0)

        path = QPainterPath()
        path.addRoundedRect(screen, 11.0, 11.0)
        painter.save()
        painter.setClipPath(path)
        pix = wallpaper(self._version)
        if not pix.isNull():
            painter.drawPixmap(int(screen.left()), int(screen.top()),
                               cover_pixmap(pix, screen.width(), screen.height()))
        else:
            grad = QLinearGradient(screen.topLeft(), screen.bottomRight())
            grad.setColorAt(0.0, QColor("#3b2d78"))
            grad.setColorAt(1.0, QColor("#0f1220"))
            painter.fillPath(path, grad)
        painter.restore()

        neck = QRectF(bezel.center().x() - 13.0, bezel.bottom() - 2.0, 26.0, height * 0.11)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(26, 27, 35))
        painter.drawRoundedRect(neck, 5.0, 5.0)
        base = QRectF(bezel.center().x() - 66.0, neck.bottom() + 4.0, 132.0, 7.0)
        painter.drawRoundedRect(base, 4.0, 4.0)

        glow = QRectF(bezel.left() + 30.0, bezel.bottom() - 3.0, bezel.width() - 60.0, 3.0)
        painter.setBrush(QColor(120, 96, 255, 160))
        painter.drawRoundedRect(glow, 2.0, 2.0)
        painter.end()


class VersionTile(QPushButton):
    """Карточка версии macOS: превью с затемнением, название и год."""

    picked = Signal(str)

    def __init__(self, name: str, year: int, parent=None):
        super().__init__(parent)
        self._name = name
        self._year = year
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(140, 132)
        self.setAccessibleName(f"{name}, {year}")
        self.clicked.connect(lambda: self.picked.emit(self._name))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        checked = self.isChecked()
        hover = self.underMouse()

        border = QColor("#8b7bff") if checked else (
            QColor(255, 255, 255, 70) if hover else QColor(255, 255, 255, 28))
        painter.setPen(QPen(border, 1.6 if checked else 1.0))
        painter.setBrush(QColor(24, 25, 33))
        painter.drawRoundedRect(rect, 15.0, 15.0)

        thumb = QRectF(rect.left() + 8.0, rect.top() + 8.0,
                       rect.width() - 16.0, rect.height() - 12.0)
        path = QPainterPath()
        path.addRoundedRect(thumb, 11.0, 11.0)
        painter.save()
        painter.setClipPath(path)
        pix = wallpaper(self._name)
        if not pix.isNull():
            painter.drawPixmap(int(thumb.left()), int(thumb.top()),
                               cover_pixmap(pix, thumb.width(), thumb.height()))
        else:
            painter.fillPath(path, QColor("#2a2b3a"))

        shade = QLinearGradient(thumb.topLeft(), thumb.bottomLeft())
        shade.setColorAt(0.25, QColor(0, 0, 0, 0))
        shade.setColorAt(1.0, QColor(8, 9, 14, 235))
        painter.fillPath(path, shade)
        painter.restore()

        painter.setPen(QColor("#ffffff"))
        font = painter.font()
        font.setPointSizeF(9.5)
        font.setBold(True)
        painter.setFont(font)
        title = QRectF(thumb.left() + 11.0, thumb.bottom() - 40.0,
                       thumb.width() - 22.0, 20.0)
        painter.drawText(title, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         self._name.replace("macOS ", ""))

        painter.setPen(QColor(255, 255, 255, 170))
        font.setBold(False)
        painter.setFont(font)
        year_rect = QRectF(thumb.left() + 11.0, title.bottom() - 2.0,
                           thumb.width() - 22.0, 18.0)
        painter.drawText(year_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         str(self._year))
        painter.end()


def hero_block(parent: QWidget, versions: list[dict], title: str, description: str):
    """Приветствие: монитор слева, пояснение справа, карточки версий снизу."""
    holder = QWidget(parent)
    outer = QVBoxLayout(holder)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(12)

    row = QHBoxLayout()
    row.setSpacing(18)
    monitor = MonitorHero(holder)
    row.addWidget(monitor, 5)

    side = QVBoxLayout()
    side.setSpacing(8)
    side.addStretch()
    head = QLabel(title, holder)
    head.setObjectName("h1")
    head.setWordWrap(True)
    side.addWidget(head)
    text = QLabel(description, holder)
    text.setObjectName("muted")
    text.setWordWrap(True)
    side.addWidget(text)
    side.addStretch()
    row.addLayout(side, 4)
    outer.addLayout(row)

    tiles_row = QHBoxLayout()
    tiles_row.setSpacing(10)
    tiles: list[VersionTile] = []
    for version in versions:
        tile = VersionTile(version["name"], int(version.get("release") or 0), holder)
        tiles.append(tile)
        tiles_row.addWidget(tile, 1)
    outer.addLayout(tiles_row)
    return holder, monitor, tiles
