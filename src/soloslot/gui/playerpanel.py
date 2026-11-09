"""Player with waveform: set solo slots with the mouse and listen to the result."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from soloslot.config import Solo
from soloslot.gui import regions as rg
from soloslot.gui.branding import INK
from soloslot.gui.icons import transport_icon
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
        self._original = None  # both versions stay in memory, so A/B needs no rendering
        self._gapped = None
        self.fade_ms = DEFAULT_FADE_MS

        self.wave = WaveformView()
        self.prev_btn = self._transport("previous", "Previous slot start (or song start)")
        self.back_btn = self._transport("rewind", f"Back {rg.SKIP:g} s")
        self.play_btn = self._transport("play", "Play (Space)")
        self.play_btn.setObjectName("transportMain")
        self.stop_btn = self._transport("stop", "Stop")
        self.fwd_btn = self._transport("forward", f"Forward {rg.SKIP:g} s")
        self.next_btn = self._transport("next", "Next slot start (or song end)")
        self.slot_btn = QPushButton("Preview slot")
        self.slot_btn.setToolTip(
            f"Play the selected slot (or the first) with {rg.PREVIEW_PAD:g} s before and after"
        )
        self.original = QRadioButton("A  Original")
        self.gaps = QRadioButton("B  With gaps")
        self.gaps.setChecked(True)
        self.gaps.setToolTip("The backing track as it will be written: muted stems are silent")
        group = QButtonGroup(self)
        group.addButton(self.original)
        group.addButton(self.gaps)
        self.ab_btn = QPushButton("A/B")
        self.ab_btn.setToolTip(
            "Switch between the original and the result (B), at the same position"
        )
        self.ab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.show_stems = QCheckBox("Show stems")
        self.show_stems.setToolTip("One waveform per stem below the mix")
        self.show_stems.toggled.connect(self.wave.set_show_lanes)
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
        row.setSpacing(6)
        for w in (
            self.prev_btn,
            self.back_btn,
            self.play_btn,
            self.stop_btn,
            self.fwd_btn,
            self.next_btn,
            self.slot_btn,
        ):
            row.addWidget(w)
        row.addStretch(1)
        row.addWidget(self.time)
        for w in (zoom_out, zoom_in, fit):
            row.addWidget(w)
        options = QHBoxLayout()
        for w in (self.ab_btn, self.original, self.gaps, self.show_stems):
            options.addWidget(w)
        options.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.wave)
        layout.addLayout(row)
        layout.addLayout(options)
        layout.addWidget(self.hint)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(REBUILD_MS)
        self._timer.timeout.connect(self._rebuild)

        self.play_btn.clicked.connect(self.toggle_play)
        self.stop_btn.clicked.connect(self.player.stop)
        self.prev_btn.clicked.connect(self.previous)
        self.back_btn.clicked.connect(lambda: self.skip(-rg.SKIP))
        self.fwd_btn.clicked.connect(lambda: self.skip(rg.SKIP))
        self.next_btn.clicked.connect(self.next)
        self.slot_btn.clicked.connect(self.preview_slot)
        self.original.toggled.connect(self._mode_changed)
        self.ab_btn.clicked.connect(self.toggle_ab)
        zoom_out.clicked.connect(lambda: self.wave.zoom(0.8))
        zoom_in.clicked.connect(lambda: self.wave.zoom(1.25))
        fit.clicked.connect(self.wave.fit)
        self.wave.slotsChanged.connect(self._edited)
        self.wave.seekRequested.connect(self.player.seek)
        self.wave.scrub.connect(self._scrub)
        self.wave.selectionChanged.connect(lambda _i: self._update_buttons())
        self.player.positionChanged.connect(self._position)
        self.player.stateChanged.connect(self._state)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, activated=self.toggle_play)
        QShortcut(QKeySequence(Qt.Key.Key_B), self, activated=self.toggle_ab)
        self._update_buttons()

    # -- data from the window
    def set_loading(self) -> None:
        self.clear("Loading…")

    def clear(self, message: str = "") -> None:
        self.player.stop()
        self.stems = None
        self.wave.message = message or "Choose a song or a stems folder to see its waveform."
        self.wave.set_peaks(None, 0.0)
        self.wave.set_lanes([])
        self._update_buttons()
        self._position(0.0)

    def set_stems(self, stems: rg.Stems) -> None:
        self.player.stop()
        self.stems = stems
        original = rg.render(stems, (), [], self.fade_ms, gaps=False)
        buckets = max(int(stems.duration * PEAKS_PER_SECOND), 1)
        self.wave.set_peaks(rg.peaks(original, buckets), stems.duration)
        self.wave.set_lanes(
            [
                (label, rg.peaks(data, buckets))
                for label, data in zip(stems.labels, stems.audio, strict=True)
            ]
            if stems.can_mute
            else []
        )
        self.show_stems.setEnabled(stems.can_mute)
        self._original, self._gapped = original, None
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

    # -- transport
    def _transport(self, kind: str, tip: str) -> QPushButton:
        pal = self.palette()
        if not hasattr(self, "_icons"):
            self._icons: dict[str, QIcon] = {}
        ink = QColor(INK) if kind == "play" else pal.buttonText().color()
        off = pal.mid().color()
        self._icons[kind] = transport_icon(kind, ink, off)
        if kind == "play":  # the pause icon shares the amber button, so it uses the same ink
            self._icons["pause"] = transport_icon("pause", ink, off)
        button = QPushButton()
        button.setObjectName("transport")
        button.setIcon(self._icons[kind])
        button.setIconSize(QSize(20, 20))
        button.setToolTip(tip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedWidth(40)
        return button

    def skip(self, seconds: float) -> None:
        """Move the playhead by `seconds`, staying inside the song."""
        if self.stems is not None:
            self.player.seek(min(max(self.player.position() + seconds, 0.0), self.stems.duration))

    def previous(self) -> None:
        if self.stems is not None:
            self.player.seek(rg.previous_marker(self.wave.slots, self.player.position()))

    def next(self) -> None:
        if self.stems is not None:
            pos = self.player.position()
            self.player.seek(rg.next_marker(self.wave.slots, pos, self.stems.duration))

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
        """Render the version with gaps (after slots or muted stems changed), then apply."""
        if self.stems is None:
            return
        self._gapped = None
        if self.stems.can_mute:
            self._gapped = rg.render(self.stems, self.muted, self.wave.slots, self.fade_ms, True)
        self._apply()

    def _apply(self) -> None:
        """Play the chosen version from the current position, without restarting the output."""
        if self.stems is None or self._original is None:
            return
        audio = (
            self._gapped if self.gaps.isChecked() and self._gapped is not None else self._original
        )
        try:
            self.player.swap_audio(audio)
        except ValueError:  # different length: restart the output
            self.player.set_audio(audio, self.stems.sample_rate)
        if self.gaps.isChecked() and not self.stems.can_mute:
            self.hint.setText("A single file cannot be muted. Choose a stems folder to hear gaps.")
        elif self.gaps.isChecked() and not rg.matches_any(self.stems.labels, self.muted):
            self.hint.setText("Select the stems to mute below to hear the gaps.")
        else:
            self.hint.setText("")

    def _mode_changed(self) -> None:
        if self._timer.isActive():  # edits are pending: render them now, the user wants to hear
            self._timer.stop()
            self._rebuild()
        else:
            self._apply()

    def toggle_ab(self) -> None:
        """Switch between A (original) and B (result with gaps) at the same position."""
        if self.stems is None or not self.stems.can_mute:
            return
        (self.original if self.gaps.isChecked() else self.gaps).setChecked(True)

    def _position(self, seconds: float) -> None:
        self._show_time(seconds)
        self.wave.set_playhead(seconds)

    def _show_time(self, seconds: float) -> None:
        total = self.stems.duration if self.stems else 0.0
        self.time.setText(f"{rg.format_time(seconds)} / {rg.format_time(total)}")

    def _scrub(self, seconds: float) -> None:
        """The playhead is being dragged: follow it silently while playing (the seek happens on
        release, so the audio does not restart on every pixel), or move it right away if paused."""
        if self.player.playing:
            self._show_time(seconds)
        else:
            self.player.seek(seconds)

    def _state(self, playing: bool) -> None:
        self.play_btn.setIcon(self._icons["pause" if playing else "play"])
        self.play_btn.setToolTip("Pause (Space)" if playing else "Play (Space)")

    def _update_buttons(self) -> None:
        ready = self.stems is not None
        for b in (self.prev_btn, self.back_btn, self.play_btn, self.stop_btn):
            b.setEnabled(ready)
        self.fwd_btn.setEnabled(ready)
        self.next_btn.setEnabled(ready)
        self.slot_btn.setEnabled(ready and bool(self.wave.slots))
        self.gaps.setEnabled(ready and self.stems.can_mute)
        self.ab_btn.setEnabled(ready and self.stems.can_mute)
        if ready and not self.stems.can_mute:
            self.original.setChecked(True)
