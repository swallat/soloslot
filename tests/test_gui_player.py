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
