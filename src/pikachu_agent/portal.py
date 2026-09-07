from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QMovie, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget


class TownPortal(QWidget):
    """A small animated desktop-level hotspot aligned with a wallpaper house."""

    activated = Signal()

    # Door of the yellow house in the 1586 × 992 generated town artwork.
    ARTWORK_SIZE = (1586, 992)
    HOME_POINT = (226, 825)

    def __init__(self, project_root: Path):
        super().__init__()
        self.setWindowTitle("Agent Town Portal")
        self.setFixedSize(150, 132)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnBottomHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("點一下進入 Agent Town")
        self._phase = 0.0
        self._hovered = False
        self._pressed_at: QPoint | None = None
        self.movie = QMovie(str(project_root / "assets" / "pikachu-animated.gif"))
        self.movie.setCacheMode(QMovie.CacheMode.CacheAll)
        self.movie.setSpeed(115)
        self.movie.frameChanged.connect(lambda _frame: self.update())
        self.movie.start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(42)

    def place_on_screen(self, screen_geometry) -> None:
        image_width, image_height = self.ARTWORK_SIZE
        scale = max(screen_geometry.width() / image_width, screen_geometry.height() / image_height)
        rendered_width, rendered_height = image_width * scale, image_height * scale
        offset_x = screen_geometry.x() + (screen_geometry.width() - rendered_width) / 2
        offset_y = screen_geometry.y() + (screen_geometry.height() - rendered_height) / 2
        center_x = offset_x + self.HOME_POINT[0] * scale
        center_y = offset_y + self.HOME_POINT[1] * scale
        self.move(int(center_x - self.width() / 2), int(center_y - self.height() / 2))

    def _tick(self) -> None:
        self._phase += 0.1
        self.update()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.movie.setSpeed(165)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.movie.setSpeed(115)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed_at = event.position().toPoint()

    def mouseReleaseEvent(self, event) -> None:
        if self._pressed_at is not None:
            if (event.position().toPoint() - self._pressed_at).manhattanLength() < 7:
                self.activated.emit()
        self._pressed_at = None

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pulse = (math.sin(self._phase) + 1) / 2
        bob = math.sin(self._phase * 0.72) * 3
        glow = QRadialGradient(75, 67, 66)
        glow.setColorAt(0, QColor(255, 230, 72, int((85 if self._hovered else 45) + pulse * 45)))
        glow.setColorAt(0.5, QColor(255, 215, 45, 24 if not self._hovered else 50))
        glow.setColorAt(1, QColor(255, 215, 45, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QRectF(9, 1, 132, 125))

        frame = self.movie.currentPixmap()
        if not frame.isNull():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            painter.drawPixmap(QRectF(31, 7 + bob, 88, 88).toRect(), frame)
        else:
            painter.setPen(QColor("#fff078"))
            painter.setFont(QFont("Arial", 48, QFont.Weight.Bold))
            painter.drawText(QRectF(31, 7 + bob, 88, 88), Qt.AlignmentFlag.AlignCenter, "⚡")

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(14, 27, 22, 225 if self._hovered else 188))
        painter.setPen(QPen(QColor(255, 226, 84, 225), 1.2))
        painter.drawRoundedRect(QRectF(22, 98, 106, 25), 12, 12)
        painter.setPen(QColor("#fff078"))
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        label = "進入城鎮  ↗" if self._hovered else "⚡  AGENT TOWN"
        painter.drawText(QRectF(22, 98, 106, 25), Qt.AlignmentFlag.AlignCenter, label)
