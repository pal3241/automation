"""Dual logical cursors: always-visible map, optional click-through X11 overlay."""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget


def draw_cursors(painter, cursors, owner, width, height):
    for side, point in cursors.items():
        x, y = point[0] * (width - 1), point[1] * (height - 1)
        color = QColor("#60ebca" if side == "Right" else "#d5a0ff")
        painter.setPen(QPen(QColor("#10151f"), 2))
        painter.setBrush(color)
        painter.drawPolygon(
            QPolygonF(
                [QPointF(x, y), QPointF(x + 5, y + 18), QPointF(x + 10, y + 11), QPointF(x + 19, y + 8)]
            )
        )
        painter.setPen(color)
        painter.setFont(QFont("DejaVu Sans", 9, QFont.Bold))
        label = "R" if side == "Right" else "L"
        painter.drawText(
            QPointF(max(2, min(width - 60, x + 22)), max(15, min(height - 5, y + 15))),
            label + (" • aktif" if side == owner else ""),
        )


class CursorMap(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(135)
        self.cursors = {}
        self.owner = None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#090e17"))
        p.setPen(QColor("#657b95"))
        p.drawRect(self.rect().adjusted(1, 1, -2, -2))
        draw_cursors(p, self.cursors, self.owner, self.width(), self.height())
        p.end()


class DesktopCursors(CursorMap):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        draw_cursors(p, self.cursors, self.owner, self.width(), self.height())
        p.end()
