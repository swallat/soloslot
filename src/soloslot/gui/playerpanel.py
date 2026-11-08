"""Player with waveform: set solo slots with the mouse and listen to the result."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from soloslot.config import Solo
from soloslot.gui import regions as rg
from soloslot.gui.player import Player
from soloslot.gui.waveform import WaveformView

PEAKS_PER_SECOND = 100
DEFAULT_FADE_MS = 30.0  # same default as Song.fade_ms
REBUILD_MS = 250  # wait for the mouse to settle before re-rendering the preview


class PlayerPanel(QWidget):
    slotsChanged = Signal(list)  # list[Solo], after the user edited them with the mouse

    def __init__(self, player: Player | None = None) -> None:
        super().__init__()
        self.player = player or Player()
        self.stems: rg.Stems | None = None
        self.muted: tuple[str, ...] = ()
        self.fade_ms = DEFAULT_FADE_MS

        self.wave = WaveformView()
        self.play_btn = QPushButton("Play")
        self.stop_btn = QPushButton("Stop")
        self.slot_btn = QPushButton("Preview slot")
        self.slot_btn.setToolTip(
            f"Play the selected slot (or the first) with {rg.PREVIEW_PAD:g} s before and after"
        )
        self.original = QRadioButton("Original")
        self.gaps = QRadioButton("With gaps")
        self.gaps.setChecked(True)
        self.gaps.setToolTip("The backing track as it will be written: muted stems are silent")
        group = QButtonGroup(self)
        group.addButton(self.original)
        group.addButton(self.gaps)
        self.time = QLabel("0:00 / 0:00")
        self.time.setMinimumWidth(90)
        self.hint = QLabel()
        self.hint.setObjectName("tagline")
        self.hint.setWordWrap(True)
        zoom_out, zoom_in, fit = QPushButton("-"), QPushButton("+"), QPushButton("Fit")
        for b, tip in ((zoom_out, "Zoom out"), (zoom_in, "Zoom in"), (fit, "Show the whole song")):
            b.setToolTip(tip)
        zoom_out.setFixedWidth(34)
        zoom_in.setFixedWidth(34)

        row = QHBoxLayout()
        for w in (self.play_btn, self.stop_btn, self.slot_btn, self.original, self.gaps):
            row.addWidget(w)
        row.addStretch(1)
        row.addWidget(self.time)
        for w in (zoom_out, zoom_in, fit):
            row.addWidget(w)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.wave)
        layout.addLayout(row)
        layout.addWidget(self.hint)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(REBUILD_MS)
        self._timer.timeout.connect(self._rebuild)

        self.play_btn.clicked.connect(self.toggle_play)
        self.stop_btn.clicked.connect(self.player.stop)
        self.slot_btn.clicked.connect(self.preview_slot)
        self.original.toggled.connect(self._schedule)
        zoom_out.clicked.connect(lambda: self.wave.zoom(0.8))
        zoom_in.clicked.connect(lambda: self.wave.zoom(1.25))
        fit.clicked.connect(self.wave.fit)
        self.wave.slotsChanged.connect(self._edited)
        self.wave.seekRequested.connect(self.player.seek)
        self.wave.selectionChanged.connect(lambda _i: self._update_buttons())
        self.player.positionChanged.connect(self._position)
        self.player.stateChanged.connect(self._state)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, activated=self.toggle_play)
        self._update_buttons()

    # -- data from the window
    def set_loading(self) -> None:
        self.clear("Loading…")

    def clear(self, message: str = "") -> None:
        self.player.stop()
        self.stems = None
        self.wave.message = message or "Choose a song or a stems folder to see its waveform."
        self.wave.set_peaks(None, 0.0)
        self._update_buttons()
        self._position(0.0)

    def set_stems(self, stems: rg.Stems) -> None:
        self.player.stop()
        self.stems = stems
        original = rg.render(stems, (), [], self.fade_ms, gaps=False)
        buckets = max(int(stems.duration * PEAKS_PER_SECOND), 1)
        self.wave.set_peaks(rg.peaks(original, buckets), stems.duration)
        self.player.set_audio(original, stems.sample_rate)
        self._rebuild()
        self._update_buttons()
        self._position(0.0)

    def set_slots(self, slots: list[Solo]) -> None:
        """Slots typed into the text field. Does not echo back."""
        if slots != self.wave.slots:
            self.wave.set_slots(slots)
            self._schedule()
        self._update_buttons()

    def set_muted(self, muted: tuple[str, ...]) -> None:
        if muted != self.muted:
            self.muted = muted
            self._schedule()

    # -- playback
    def toggle_play(self) -> None:
        if self.stems is None:
            return
        if self.player.playing:
            self.player.pause()
        else:
            self.player.play()
            self._show_error()

    def preview_slot(self) -> None:
        slots = self.wave.slots
        if self.stems is None or not slots:
            return
        slot = slots[self.wave.selected] if 0 <= self.wave.selected < len(slots) else slots[0]
        start, stop = rg.preview_span(slot, self.stems.duration)
        self.player.play(start, stop)
        self._show_error()

    def _show_error(self) -> None:
        self.hint.setText(f"Cannot play audio: {self.player.error}" if self.player.error else "")
        self._update_buttons()

    # -- internals
    def _edited(self) -> None:
        self._schedule()
        self._update_buttons()
        self.slotsChanged.emit(list(self.wave.slots))

    def _schedule(self) -> None:
        self._timer.start()

    def _rebuild(self) -> None:
        if self.stems is None:
            return
        want_gaps = self.gaps.isChecked() and self.stems.can_mute
        audio = rg.render(self.stems, self.muted, self.wave.slots, self.fade_ms, want_gaps)
        self.player.set_audio(audio, self.stems.sample_rate)
        if self.gaps.isChecked() and not self.stems.can_mute:
            self.hint.setText("A single file cannot be muted. Choose a stems folder to hear gaps.")
        elif self.gaps.isChecked() and not rg.matches_any(self.stems.labels, self.muted):
            self.hint.setText("Select the stems to mute below to hear the gaps.")
        else:
            self.hint.setText("")

    def _position(self, seconds: float) -> None:
        total = self.stems.duration if self.stems else 0.0
        self.time.setText(f"{rg.format_time(seconds)} / {rg.format_time(total)}")
        self.wave.set_playhead(seconds)

    def _state(self, playing: bool) -> None:
        self.play_btn.setText("Pause" if playing else "Play")

    def _update_buttons(self) -> None:
        ready = self.stems is not None
        self.play_btn.setEnabled(ready)
        self.stop_btn.setEnabled(ready)
        self.slot_btn.setEnabled(ready and bool(self.wave.slots))
        self.gaps.setEnabled(ready and self.stems.can_mute)
        if ready and not self.stems.can_mute:
            self.original.setChecked(True)
