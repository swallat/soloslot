"""Transport button icons, drawn with QPainter so they follow the theme. Requires PySide6."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygonF

KINDS = ("play", "pause", "stop", "rewind", "forward", "previous", "next")


def _triangle(p: QPainter, x: float, y: float, w: float, h: float, right: bool = True) -> None:
    a, b = (x, x + w) if right else (x + w, x)
    p.drawPolygon(QPolygonF([QPointF(a, y), QPointF(b, y + h / 2), QPointF(a, y + h)]))


def _draw(p: QPainter, kind: str) -> None:
    """Glyphs on a 100 x 100 canvas."""
    if kind == "play":
        _triangle(p, 30, 18, 46, 64)
    elif kind == "pause":
        p.drawRoundedRect(QRectF(26, 20, 16, 60), 3, 3)
        p.drawRoundedRect(QRectF(58, 20, 16, 60), 3, 3)
    elif kind == "stop":
        p.drawRoundedRect(QRectF(24, 24, 52, 52), 6, 6)
    elif kind in ("rewind", "forward"):
        right = kind == "forward"
        _triangle(p, 12 if right else 48, 24, 38, 52, right)
        _triangle(p, 50 if right else 10, 24, 38, 52, right)
    else:  # previous / next: a triangle against a bar
        right = kind == "next"
        _triangle(p, 24 if right else 38, 22, 38, 56, right)
        p.drawRoundedRect(QRectF(66 if right else 22, 22, 12, 56), 3, 3)


def transport_icon(kind: str, color: QColor, disabled: QColor | None = None) -> QIcon:
    """A crisp icon (rendered at 2x) in `color`; `disabled` is used when the button is off."""
    icon = QIcon()
    for mode, c in ((QIcon.Mode.Normal, color), (QIcon.Mode.Disabled, disabled or color)):
        pixmap = QPixmap(96, 96)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(0.96, 0.96)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        _draw(p, kind)
        p.end()
        icon.addPixmap(pixmap, mode)
    return icon
