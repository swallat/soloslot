import os
from typing import ClassVar

import numpy as np
import pytest
import soundfile as sf

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from soloslot.config import Solo
from soloslot.gui import regions as rg
from soloslot.gui.player import Player
from soloslot.gui.playerpanel import PlayerPanel
from soloslot.gui.waveform import MIN_VIEW

RATE = 1000


class FakeOutput:
    """Takes everything written and 'plays' it at the pace the test sets."""

    instances: ClassVar[list] = []

    def __init__(self, rate, channels):
        self.rate, self.channels = rate, channels
        self.data = bytearray()
        self.played_us = 0
        self.started = False
        FakeOutput.instances.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def free_bytes(self):
        return 10**6

    def write(self, data):
        self.data += data
        return len(data)

    def processed_us(self):
        return self.played_us

    def flush(self):
        self.data.clear()
        return self.played_us


@pytest.fixture
def app():
    FakeOutput.instances = []
    return QApplication.instance() or QApplication([])


def _audio(seconds=10):
    return np.full((int(RATE * seconds), 2), 0.5, dtype="float32")


def test_player_plays_a_span_and_stops_at_its_end(app):
    p = Player(FakeOutput)
    p.set_audio(_audio(), RATE)
    states = []
    p.stateChanged.connect(states.append)
    p.play(2.0, 3.0)
    out = FakeOutput.instances[-1]
    assert p.playing and out.started
    assert len(out.data) == 1000 * 2 * 2  # one second of 16 bit stereo
    out.played_us = 500_000
    assert p.position() == pytest.approx(2.5)
    out.played_us = 1_000_000
    p._tick()
    assert not p.playing
    assert states == [True, False]
    assert p.position() == pytest.approx(3.0)


def test_player_pause_seek_and_stop(app):
    p = Player(FakeOutput)
    p.set_audio(_audio(), RATE)
    p.play(1.0)
    FakeOutput.instances[-1].played_us = 2_000_000
    p.pause()
    assert not p.playing and p.position() == pytest.approx(3.0)
    p.seek(7.0)
    assert p.position() == pytest.approx(7.0)
    p.stop()
    assert p.position() == 0


def test_player_reports_a_missing_device(app):
    def broken(rate, channels):
        raise OSError("PortAudio library not found")

    p = Player(broken)
    p.set_audio(_audio(), RATE)
    p.play()
    assert not p.playing and "PortAudio" in p.error


def test_set_audio_keeps_position_while_playing(app):
    p = Player(FakeOutput)
    p.set_audio(_audio(), RATE)
    p.play(4.0)
    FakeOutput.instances[-1].played_us = 1_000_000
    p.set_audio(_audio() * 0.5, RATE)
    assert p.playing
    assert FakeOutput.instances[-1] is not FakeOutput.instances[0]
    assert p.position() == pytest.approx(5.0)


def _panel(tmp_path, app):
    for name, level in (("piano", 0.2), ("bass", 0.1)):
        sf.write(tmp_path / f"{name}.wav", np.full((RATE * 10, 2), level, dtype="float32"), RATE)
    panel = PlayerPanel(Player(FakeOutput))
    panel.resize(500, 200)
    panel.set_stems(rg.load_stems(tmp_path))
    return panel


def test_panel_hears_gaps_only_for_muted_stems(tmp_path, app):
    panel = _panel(tmp_path, app)
    panel.set_slots([Solo(2, 4)])
    panel.set_muted(("piano",))
    panel._rebuild()
    audio = panel.player._audio
    assert audio[3000, 0] == pytest.approx(0.1, abs=1e-3)
    assert audio[6000, 0] == pytest.approx(0.3, abs=1e-3)
    panel.original.setChecked(True)
    panel._rebuild()
    assert panel.player._audio[3000, 0] == pytest.approx(0.3, abs=1e-3)


def test_panel_preview_slot_plays_the_padded_span(tmp_path, app):
    panel = _panel(tmp_path, app)
    assert not panel.slot_btn.isEnabled()
    panel.set_slots([Solo(5, 6)])
    assert panel.slot_btn.isEnabled()
    panel.preview_slot()
    out = FakeOutput.instances[-1]
    assert len(out.data) == 7 * RATE * 4  # 2 s .. 9 s


def test_dragging_in_the_waveform_creates_moves_and_deletes_slots(tmp_path, app):
    panel = _panel(tmp_path, app)
    wave = panel.wave
    emitted = []
    panel.slotsChanged.connect(emitted.append)
    w = wave.width()  # the whole 10 s song is in view
    y = 20

    def drag(x0, x1):
        QTest.mousePress(wave, Qt.MouseButton.LeftButton, pos=QPointF(x0, y).toPoint())
        QTest.mouseMove(wave, QPointF(x1, y).toPoint())
        QTest.mouseRelease(wave, Qt.MouseButton.LeftButton, pos=QPointF(x1, y).toPoint())

    drag(w * 0.2, w * 0.4)
    assert len(wave.slots) == 1
    assert wave.slots[0].start == pytest.approx(2.0, abs=0.1)
    assert wave.slots[0].end == pytest.approx(4.0, abs=0.1)
    assert emitted and len(emitted[-1]) == 1
    drag(w * 0.3, w * 0.4)  # grab the body and move it by 1 s
    assert wave.slots[0].start == pytest.approx(3.0, abs=0.1)
    assert wave.slots[0].end == pytest.approx(5.0, abs=0.1)
    drag(w * 0.5, w * 0.7)  # grab the end edge
    assert wave.slots[0].end == pytest.approx(7.0, abs=0.1)
    assert wave.slots[0].start == pytest.approx(3.0, abs=0.1)
    seeks = []
    wave.seekRequested.connect(seeks.append)
    QTest.mouseClick(wave, Qt.MouseButton.LeftButton, pos=QPointF(w * 0.9, y).toPoint())
    assert seeks and seeks[0] == pytest.approx(9.0, abs=0.1)
    wave.selected = 0
    wave.delete_selected()
    assert wave.slots == []
    assert emitted[-1] == []


def test_stem_lanes_are_optional(tmp_path, app):
    panel = _panel(tmp_path, app)
    assert [name for name, _ in panel.wave.lanes] == ["bass", "piano"]
    assert not panel.wave.show_lanes
    base = panel.wave.minimumHeight()
    panel.show_stems.setChecked(True)
    assert panel.wave.show_lanes and panel.wave.minimumHeight() > base
    panel.wave.grab()  # paints with lanes without error
    panel.show_stems.setChecked(False)
    assert panel.wave.minimumHeight() == base


def test_transport_buttons(tmp_path, app):
    panel = _panel(tmp_path, app)
    panel.set_slots([Solo(3, 4), Solo(6, 7)])
    for b in (panel.prev_btn, panel.back_btn, panel.play_btn, panel.stop_btn, panel.fwd_btn):
        assert b.isEnabled() and not b.icon().isNull()
    panel.next_btn.click()
    assert panel.player.position() == pytest.approx(3.0)
    panel.next_btn.click()
    assert panel.player.position() == pytest.approx(6.0)
    panel.back_btn.click()
    assert panel.player.position() == pytest.approx(1.0)
    panel.fwd_btn.click()
    assert panel.player.position() == pytest.approx(6.0)
    panel.fwd_btn.click()
    panel.fwd_btn.click()  # stays inside the song
    assert panel.player.position() == pytest.approx(10.0)
    panel.prev_btn.click()
    assert panel.player.position() == pytest.approx(6.0)
    panel.play_btn.click()
    assert panel.player.playing
    panel.play_btn.click()
    assert not panel.player.playing
    panel.stop_btn.click()
    assert panel.player.position() == 0


def test_transport_buttons_are_off_without_a_song(app):
    panel = PlayerPanel(Player(FakeOutput))
    for b in (panel.prev_btn, panel.back_btn, panel.play_btn, panel.stop_btn, panel.next_btn):
        assert not b.isEnabled()


def test_swap_audio_keeps_playing_without_restarting_the_output(app):
    p = Player(FakeOutput)
    p.set_audio(_audio(), RATE)
    p.play(2.0)
    out = FakeOutput.instances[-1]
    out.played_us = 500_000
    p.swap_audio(_audio() * 0.5)
    assert FakeOutput.instances[-1] is out and p.playing
    assert p.position() == pytest.approx(2.5)
    # what is queued now comes from the new audio, starting at the same position
    first = np.frombuffer(bytes(out.data[:4]), dtype="<i2")
    assert first[0] == pytest.approx(0.25 * 32767, abs=2)
    out.played_us = 1_000_000
    assert p.position() == pytest.approx(3.0)
    with pytest.raises(ValueError):
        p.swap_audio(_audio(5))


def test_ab_switch_is_instant_and_keeps_the_position(tmp_path, app):
    panel = _panel(tmp_path, app)
    panel.set_slots([Solo(2, 4)])
    panel.set_muted(("piano",))
    panel._rebuild()
    panel.player.seek(3.0)
    panel.player.play()
    out = FakeOutput.instances[-1]
    assert panel.gaps.isChecked()
    panel.toggle_ab()  # B -> A
    assert panel.original.isChecked()
    assert FakeOutput.instances[-1] is out  # no restart
    assert panel.player.playing and panel.player.position() == pytest.approx(3.0)
    assert panel.player._audio[3000, 0] == pytest.approx(0.3, abs=1e-3)  # original again
    panel.toggle_ab()  # A -> B
    assert panel.player._audio[3000, 0] == pytest.approx(0.1, abs=1e-3)  # piano is gone


def test_edits_pending_are_rendered_when_switching(tmp_path, app):
    panel = _panel(tmp_path, app)
    panel.original.setChecked(True)
    panel.set_muted(("piano",))
    panel.set_slots([Solo(2, 4)])  # starts the debounce timer
    assert panel._timer.isActive()
    panel.gaps.setChecked(True)
    assert not panel._timer.isActive()
    assert panel.player._audio[3000, 0] == pytest.approx(0.1, abs=1e-3)


def test_ab_is_off_for_a_single_file(tmp_path, app):
    f = tmp_path / "song.wav"
    sf.write(f, np.full((RATE * 2, 2), 0.2, dtype="float32"), RATE)
    panel = PlayerPanel(Player(FakeOutput))
    panel.set_stems(rg.load_stems(f))
    assert not panel.ab_btn.isEnabled() and not panel.gaps.isEnabled()
    panel.toggle_ab()
    assert panel.original.isChecked()


def test_ctrl_wheel_zooms_around_the_mouse_and_wheel_scrolls(tmp_path, app):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QWheelEvent

    panel = _panel(tmp_path, app)
    wave = panel.wave
    assert wave.view_len == pytest.approx(10.0)

    def wheel(dy, x, modifiers):
        pos = QPointF(x, 20)
        event = QWheelEvent(
            pos, wave.mapToGlobal(pos), QPoint(0, 0), QPoint(0, dy),
            Qt.MouseButton.NoButton, modifiers, Qt.ScrollPhase.NoScrollPhase, False,
        )  # fmt: skip
        QApplication.sendEvent(wave, event)

    x = wave.width() * 0.5  # the mouse is over 5.0 s
    wheel(120, x, Qt.KeyboardModifier.ControlModifier)
    assert wave.view_len < 10.0
    assert wave.view_start < 5.0 < wave.view_start + wave.view_len  # 5 s stays in view
    assert wave._x(5.0) == pytest.approx(x, abs=1.5)  # and stays under the mouse
    for _ in range(20):
        wheel(120, x, Qt.KeyboardModifier.ControlModifier)
    assert wave.view_len == pytest.approx(MIN_VIEW)
    start = wave.view_start
    wheel(-120, x, Qt.KeyboardModifier.NoModifier)  # wheel without Ctrl scrolls
    assert wave.view_start > start
    for _ in range(40):
        wheel(-120, x, Qt.KeyboardModifier.ControlModifier)
    assert wave.view_len == pytest.approx(10.0)  # zoomed out again: the whole song


def _hover(wave, x, y=20):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QMouseEvent

    pos = QPointF(x, y)
    event = QMouseEvent(
        QEvent.Type.MouseMove, pos, wave.mapToGlobal(pos),
        Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
    )  # fmt: skip
    QApplication.sendEvent(wave, event)


def _mouse(wave, kind, x, y=20):
    pos = QPointF(x, y).toPoint()
    if kind == "press":
        QTest.mousePress(wave, Qt.MouseButton.LeftButton, pos=pos)
    elif kind == "move":
        QTest.mouseMove(wave, pos)
    else:
        QTest.mouseRelease(wave, Qt.MouseButton.LeftButton, pos=pos)


def test_playhead_can_be_grabbed_by_its_handle_and_line_and_dragged(tmp_path, app):
    panel = _panel(tmp_path, app)
    wave = panel.wave
    w = wave.width()
    panel.player.seek(5.0)
    px = wave._x(5.0)
    # hover: the cursor says "drag me", on the line and on the handle
    _hover(wave, px + 5)
    assert wave.cursor().shape() == Qt.CursorShape.SizeHorCursor
    _hover(wave, px + 8, y=4)  # the handle is wider than the line
    assert wave.cursor().shape() == Qt.CursorShape.SizeHorCursor
    _hover(wave, px + 40)
    assert wave.cursor().shape() == Qt.CursorShape.ArrowCursor
    # drag it from the handle, while paused: the position follows
    _mouse(wave, "press", px + 7, y=5)
    _mouse(wave, "move", w * 0.8)
    assert panel.player.position() == pytest.approx(8.0, abs=0.1)
    _mouse(wave, "release", w * 0.8)
    assert panel.player.position() == pytest.approx(8.0, abs=0.1)
    assert wave.slots == []  # no slot was created by the drag


def test_playhead_handle_follows_the_line_to_both_edges(tmp_path, app):
    panel = _panel(tmp_path, app)
    wave = panel.wave
    w = wave.width()
    # at the start the pennant hangs right of the line; at the end it flips to the left
    assert wave._flag_span(1.0) == (1.0, 1.0 + 16)
    assert wave._flag_span(w - 1.0) == (w - 1.0 - 16, w - 1.0)
    panel.player.seek(0.0)
    assert wave._on_playhead(1, 20) and wave._on_playhead(10, 4)  # the flag is next to the line
    assert not wave._on_playhead(60, 4)
    panel.player.seek(panel.stems.duration)
    assert wave._on_playhead(w - 1, 20) and wave._on_playhead(w - 10, 4)
    assert not wave._on_playhead(w - 60, 4)


def test_playhead_wins_over_a_slot_edge_next_to_it(tmp_path, app):
    panel = _panel(tmp_path, app)
    wave = panel.wave
    panel.set_slots([Solo(5, 7)])
    panel.player.seek(5.0)  # exactly on the slot's start edge
    px = wave._x(5.0)
    _mouse(wave, "press", px + 2)
    _mouse(wave, "move", px + 60)
    _mouse(wave, "release", px + 60)
    assert wave.slots == [Solo(5, 7)]  # the slot did not change
    assert panel.player.position() > 5.5  # the playhead moved


def test_dragging_the_playhead_while_playing_seeks_only_on_release(tmp_path, app):
    panel = _panel(tmp_path, app)
    wave = panel.wave
    panel.player.play(2.0)
    out = FakeOutput.instances[-1]
    px = wave._x(2.0)
    _mouse(wave, "press", px, y=5)
    _mouse(wave, "move", px + 100)
    _mouse(wave, "move", px + 200)
    assert FakeOutput.instances[-1] is out  # the audio was not restarted while dragging
    assert panel.time.text().startswith(rg.format_time(wave._t(px + 200)))  # the label follows
    _mouse(wave, "release", px + 200)
    assert panel.player.playing
    assert panel.player.position() == pytest.approx(wave._t(px + 200), abs=0.2)


def test_clicking_a_slot_or_empty_space_jumps_there(tmp_path, app):
    panel = _panel(tmp_path, app)
    wave = panel.wave
    panel.set_slots([Solo(2, 4)])
    _mouse(wave, "press", wave._x(3.0))
    _mouse(wave, "release", wave._x(3.0))  # a click inside a slot
    assert panel.player.position() == pytest.approx(3.0, abs=0.1)
    assert wave.slots == [Solo(2, 4)]
    _mouse(wave, "press", wave._x(8.0))
    _mouse(wave, "release", wave._x(8.0))  # a click on a free spot
    assert panel.player.position() == pytest.approx(8.0, abs=0.1)
