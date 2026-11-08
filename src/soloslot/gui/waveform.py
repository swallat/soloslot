"""Waveform with draggable solo slots. Requires PySide6."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QMenu, QSizePolicy, QWidget

from soloslot.config import Solo
from soloslot.gui import regions as rg

GRAB_PX = 6  # how close to a slot edge the mouse grabs it
CLICK_PX = 3  # smaller drags count as a click
MIN_VIEW = 2.0  # seconds; the most zoomed-in view


class WaveformView(QWidget):
    """Shows peaks, slots and the playhead. Mouse: drag empty space to add a slot, drag a
    slot to move it, drag its edges to resize, click to seek, Delete removes the selected
    slot, mouse wheel scrolls, Ctrl+wheel zooms."""

    slotsChanged = Signal()
    seekRequested = Signal(float)
    selectionChanged = Signal(int)  # index or -1

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.peaks: np.ndarray | None = None  # (n, 2) min/max over the whole song
        self.duration = 0.0
        self.lanes: list[tuple[str, np.ndarray]] = []  # per-stem peaks
        self.show_lanes = False
        self.slots: list[Solo] = []
        self.selected = -1
        self.playhead = 0.0
        self.view_start = 0.0
        self.view_len = 0.0
        self._drag: tuple[str, int, float, Solo | None] | None = None  # mode, index, t0, original
        self._press_x = 0.0
        self.message = "Choose a song or a stems folder to see its waveform."

    # -- data
    def set_peaks(self, peaks: np.ndarray | None, duration: float) -> None:
        self.peaks, self.duration = peaks, duration
        self.fit()

    def set_lanes(self, lanes: list[tuple[str, np.ndarray]]) -> None:
        self.lanes = lanes
        self._resize_for_lanes()

    def set_show_lanes(self, on: bool) -> None:
        self.show_lanes = on
        self._resize_for_lanes()

    def _resize_for_lanes(self) -> None:
        count = 1 + (len(self.lanes) if self.show_lanes else 0)
        self.setMinimumHeight(110 if count == 1 else min(60 * count, 420))
        self.update()

    def set_slots(self, slots: list[Solo]) -> None:
        """Replace the slots from outside (e.g. the text field); does not emit."""
        self.slots = list(slots)
        self.selected = min(self.selected, len(slots) - 1)
        self.update()

    def set_playhead(self, seconds: float) -> None:
        self.playhead = seconds
        if (
            self._drag is None
            and self.view_len
            and not (self.view_start <= seconds <= self.view_start + self.view_len)
        ):
            self._scroll_to(seconds)
        self.update()

    # -- view
    def fit(self) -> None:
        self.view_start, self.view_len = 0.0, self.duration
        self.update()

    def zoom(self, factor: float, anchor: float | None = None) -> None:
        if not self.duration:
            return
        anchor = self.view_start + self.view_len / 2 if anchor is None else anchor
        new_len = min(max(self.view_len / factor, min(MIN_VIEW, self.duration)), self.duration)
        frac = (anchor - self.view_start) / self.view_len if self.view_len else 0.5
        self.view_len = new_len
        self.view_start = min(max(anchor - frac * new_len, 0.0), self.duration - new_len)
        self.update()

    def _scroll_to(self, seconds: float) -> None:
        self.view_start = min(
            max(seconds - self.view_len * 0.1, 0.0), max(self.duration - self.view_len, 0.0)
        )

    def _t(self, x: float) -> float:
        if not self.view_len:
            return 0.0
        return min(max(self.view_start + x / self.width() * self.view_len, 0.0), self.duration)

    def _x(self, t: float) -> float:
        return (t - self.view_start) / self.view_len * self.width() if self.view_len else 0.0

    def _px(self, pixels: float) -> float:
        return pixels / self.width() * self.view_len if self.width() else 0.0

    # -- editing (also used by tests)
    def add_slot(self, start: float, end: float) -> int:
        self.slots.append(rg.clamp_slot(start, end, self.duration))
        self.selected = len(self.slots) - 1
        self._changed()
        return self.selected

    def delete_selected(self) -> None:
        if 0 <= self.selected < len(self.slots):
            del self.slots[self.selected]
            self.selected = -1
            self.selectionChanged.emit(-1)
            self._changed()

    def _changed(self) -> None:
        self.update()
        self.slotsChanged.emit()

    def _draw_peaks(self, p: QPainter, peaks: np.ndarray, mid: float, scale: float) -> None:
        n, w = len(peaks), max(self.width(), 1)
        per_px = self.view_len / w
        for px in range(w):
            t0 = self.view_start + px * per_px
            i0 = int(t0 / self.duration * n)
            i1 = max(int((t0 + per_px) / self.duration * n), i0 + 1)
            if i0 >= n:
                break
            seg = peaks[i0 : min(i1, n)]
            lo, hi = float(seg[:, 0].min()), float(seg[:, 1].max())
            p.drawLine(QPointF(px + 0.5, mid - hi * scale), QPointF(px + 0.5, mid - lo * scale))

    # -- painting
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        pal = self.palette()
        p.fillRect(self.rect(), pal.base())
        if self.peaks is None or not self.duration:
            p.setPen(pal.placeholderText().color())
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.message)
            return
        h = self.height()
        accent = pal.highlight().color()
        # slots under the waveform
        for i, s in enumerate(self.slots):
            x0, x1 = self._x(s.start), self._x(s.end)
            c = QColor(accent)
            c.setAlpha(110 if i == self.selected else 60)
            p.fillRect(QRectF(x0, 0, x1 - x0, h), c)
            p.setPen(QPen(accent, 2 if i == self.selected else 1))
            p.drawLine(QPointF(x0, 0), QPointF(x0, h))
            p.drawLine(QPointF(x1, 0), QPointF(x1, h))
            p.setPen(pal.text().color())
            p.drawText(QPointF(x0 + 4, 14), f"{i + 1}")
        # peaks: the mix, then (optionally) one lane per stem
        lanes = [("", self.peaks)] + (self.lanes if self.show_lanes else [])
        lane_h = h / len(lanes)
        p.setPen(QPen(pal.text().color(), 1))
        for k, (label, data) in enumerate(lanes):
            top = k * lane_h
            self._draw_peaks(p, data, top + lane_h / 2, lane_h / 2 * 0.92)
            if label:
                p.setPen(QPen(pal.mid().color(), 1))
                p.drawLine(QPointF(0, top), QPointF(self.width(), top))
                p.setPen(pal.placeholderText().color())
                p.drawText(QPointF(self.width() - 6 - 8 * len(label), top + 13), label)
                p.setPen(QPen(pal.text().color(), 1))
        # playhead
        x = self._x(self.playhead)
        p.setPen(QPen(QColor("#e5484d"), 2))
        p.drawLine(QPointF(x, 0), QPointF(x, h))

    # -- mouse
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if not self.duration or e.button() != Qt.MouseButton.LeftButton:
            return
        self.setFocus()
        t = self._t(e.position().x())
        self._press_x = e.position().x()
        hit = rg.hit_test(self.slots, t, self._px(GRAB_PX))
        if hit is None:
            self._drag = ("new", -1, t, None)
            self._select(-1)
            return
        i, part = hit
        self._select(i)
        self._drag = (part, i, t, self.slots[i])

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        t = self._t(e.position().x())
        if self._drag is None:
            hit = rg.hit_test(self.slots, t, self._px(GRAB_PX))
            shape = Qt.CursorShape.ArrowCursor
            if hit:
                shape = (
                    Qt.CursorShape.OpenHandCursor
                    if hit[1] == "body"
                    else Qt.CursorShape.SizeHorCursor
                )
            self.setCursor(shape)
            return
        mode, i, t0, orig = self._drag
        if mode == "new":
            if abs(e.position().x() - self._press_x) < CLICK_PX:
                return
            if self.selected < 0:
                self.slots.append(rg.clamp_slot(t0, t, self.duration))
                self._select(len(self.slots) - 1)
            i = self.selected
            self.slots[i] = rg.clamp_slot(t0, t, self.duration)
        elif orig is not None:
            if mode == "body":
                self.slots[i] = rg.move_slot(orig, t - t0, self.duration)
            elif mode == "start":
                self.slots[i] = rg.clamp_slot(
                    min(t, orig.end - rg.MIN_SLOT), orig.end, self.duration
                )
            else:
                self.slots[i] = rg.clamp_slot(
                    orig.start, max(t, orig.start + rg.MIN_SLOT), self.duration
                )
        self._changed()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        drag, self._drag = self._drag, None
        if drag and drag[0] == "new" and abs(e.position().x() - self._press_x) < CLICK_PX:
            self.seekRequested.emit(self._t(e.position().x()))

    def keyPressEvent(self, e) -> None:
        if e.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
        else:
            super().keyPressEvent(e)

    def contextMenuEvent(self, e) -> None:
        hit = rg.hit_test(self.slots, self._t(e.pos().x()), self._px(GRAB_PX))
        if hit is None:
            return
        self._select(hit[0])
        menu = QMenu(self)
        menu.addAction("Delete slot", self.delete_selected)
        menu.exec(e.globalPos())

    def wheelEvent(self, e) -> None:
        if not self.duration:
            return
        dy = e.angleDelta().y()
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(1.25 if dy > 0 else 0.8, self._t(e.position().x()))
        else:
            step = self.view_len * 0.1 * (-1 if dy > 0 else 1)
            self.view_start = min(
                max(self.view_start + step, 0.0), max(self.duration - self.view_len, 0.0)
            )
            self.update()

    def _select(self, i: int) -> None:
        if i != self.selected:
            self.selected = i
            self.selectionChanged.emit(i)
        self.update()
