import os

import numpy as np
import pytest
import soundfile as sf

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from soloslot.gui.app import MainWindow


def test_window_runs_a_job(tmp_path):
    app = QApplication.instance() or QApplication([])
    folder = tmp_path / "tune"
    folder.mkdir()
    for name in ("piano", "bass"):
        sf.write(folder / f"{name}.wav", np.ones((88200, 2), dtype="float32") * 0.1, 44100)
    w = MainWindow()
    assert not w.log.isVisibleTo(w)
    w.toggle.setChecked(True)
    assert w.log.isVisibleTo(w)
    w.source.setText(str(folder))
    w._refresh_stems()
    assert set(w._checks) == {"bass", "piano"}
    w._checks["piano"].setChecked(True)
    w.solos.setPlainText("0:00.5-0:01")
    w.backing_only.setChecked(True)
    w._start()
    w._thread.wait(10000)
    app.processEvents()
    assert w.start.isEnabled()
    assert (tmp_path / "out" / "tune").is_dir()
    assert "Done" in w.log.toPlainText()
    assert w.open_output.isVisibleTo(w)
    assert w._result == tmp_path / "out" / "tune" / "tune - Backing Track.wav"
    assert w._result.exists()


def test_update_banner(monkeypatch):
    from soloslot.update import Update

    QApplication.instance() or QApplication([])
    w = MainWindow()
    assert not w.banner.isVisibleTo(w)
    w._update_found(None, "offline")
    assert not w.banner.isVisibleTo(w)
    w._update_found(Update("9.9.9", "", "https://example", None, None, None), "")
    assert w.banner.isVisibleTo(w)
    assert "9.9.9" in w.banner_text.text()
    assert w.banner_button.text() == "Release page"


def test_manual_update_check(monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from soloslot.update import Update

    QApplication.instance() or QApplication([])
    shown = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: shown.append(a[2]))
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: shown.append(a[2]))
    w = MainWindow()
    w._manual_result(None, "")
    assert "up to date" in shown[-1]
    w._manual_result(None, "offline")
    assert "offline" in shown[-1]
    assert not w.banner.isVisibleTo(w)
    w._manual_result(Update("9.9.9", "", "https://example", None, None, None), "")
    assert w.banner.isVisibleTo(w)


def test_window_has_the_logo_icon():
    QApplication.instance() or QApplication([])
    w = MainWindow()
    assert not w.windowIcon().isNull()
    assert w.windowIcon().availableSizes()


def _split(tmp_path):
    """A song file and a finished split of it, as a run leaves them."""
    import json

    from soloslot.separate import DEFAULT_MODEL, _fingerprint

    song = tmp_path / "tune.wav"
    sf.write(song, np.zeros((44100, 2), dtype="float32"), 44100)
    folder = tmp_path / "out" / "tune" / "separated" / DEFAULT_MODEL
    folder.mkdir(parents=True)
    for name in ("vocals", "drums"):
        sf.write(folder / f"{name}.flac", np.full((44100, 2), 0.1, dtype="float32"), 44100)
    (folder / "source.json").write_text(json.dumps(_fingerprint(song, DEFAULT_MODEL)))
    return song, folder


def _wait_for_preview(app, w):
    for _ in range(200):
        app.processEvents()
        if w.panel.stems is not None:
            return
        QTest.qWait(10)


def test_a_song_split_before_plays_from_its_stems(tmp_path):
    app = QApplication.instance() or QApplication([])
    song, _ = _split(tmp_path)
    w = MainWindow()
    w.source.setText(str(song))
    w._refresh_stems()
    _wait_for_preview(app, w)
    assert w.panel.stems is not None and w.panel.stems.can_mute  # A/B is on
    assert w.panel.ab_btn.isEnabled()


def test_a_finished_run_loads_the_new_stems_into_the_player(tmp_path):
    app = QApplication.instance() or QApplication([])
    song = tmp_path / "tune.wav"
    sf.write(song, np.zeros((44100, 2), dtype="float32"), 44100)
    w = MainWindow()
    w.source.setText(str(song))
    w._refresh_stems()
    _wait_for_preview(app, w)
    assert not w.panel.stems.can_mute  # a single file: no A/B yet
    _, folder = _split(tmp_path)  # the run splits the song
    w._stems_folder = folder
    w.panel.stems = None
    w._done(True)
    _wait_for_preview(app, w)
    assert w.panel.stems.can_mute
    assert w.panel.ab_btn.isEnabled()
