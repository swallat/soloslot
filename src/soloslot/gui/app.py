"""The window. Requires PySide6 (`pip install 'soloslot[gui]'`)."""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

try:
    from PySide6.QtCore import QObject, Qt, QThread, Signal
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError:  # pragma: no cover
    raise SystemExit("The GUI needs PySide6: pip install 'soloslot[gui]'") from None

from soloslot import __version__
from soloslot.config import OUTPUT_FORMATS, ConfigError
from soloslot.gui.model import DEFAULT_STEMS, Form, build_song, stems_of
from soloslot.process import process_song


class _Stream:
    """File-like object that forwards console output (e.g. Demucs progress) as log lines."""

    def __init__(self, emit):
        self._emit = emit

    def write(self, text: str) -> int:
        for line in text.replace("\r", "\n").splitlines():
            if line.strip():
                self._emit(line)
        return len(text)

    def flush(self) -> None:
        pass


class Worker(QObject):
    line = Signal(str)
    finished = Signal(bool)

    def __init__(self, song):
        super().__init__()
        self._song = song

    def run(self) -> None:
        stream = _Stream(self.line.emit)
        try:
            with contextlib.redirect_stderr(stream), contextlib.redirect_stdout(stream):
                ok = process_song(self._song, log=self.line.emit)
        except Exception as e:  # show anything unexpected in the log instead of dying silently
            self.line.emit(f"  ERROR: {type(e).__name__}: {e}")
            ok = False
        self.finished.emit(ok)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"soloslot {__version__}")
        self.resize(560, 640)
        self._thread: QThread | None = None
        self._worker: Worker | None = None
        self._checks: dict[str, QCheckBox] = {}

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        # Input
        self.source = QLineEdit()
        self.source.setPlaceholderText("Song (MP3/WAV/FLAC) or folder with stems")
        self.source.editingFinished.connect(self._refresh_stems)
        row = QHBoxLayout()
        row.addWidget(self.source)
        for text, slot in (("File…", self._pick_file), ("Folder…", self._pick_folder)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        layout.addLayout(row)

        # Solo regions
        self.solos = QPlainTextEdit()
        self.solos.setPlaceholderText("One solo per line: START-END, e.g. 2:15-3:40")
        self.solos.setFixedHeight(70)
        layout.addWidget(self.solos)

        # Stems
        self.stem_box = QGroupBox("Mute in the solo")
        self.stem_layout = QHBoxLayout(self.stem_box)
        layout.addWidget(self.stem_box)
        self._set_stems(DEFAULT_STEMS)

        # Options
        form = QFormLayout()
        self.output = QLineEdit()
        self.output.setPlaceholderText("default: out/<song> next to the input")
        out_row = QHBoxLayout()
        out_row.addWidget(self.output)
        b = QPushButton("Browse…")
        b.clicked.connect(self._pick_output)
        out_row.addWidget(b)
        form.addRow("Output folder", out_row)
        self.fmt = QComboBox()
        self.fmt.addItems(OUTPUT_FORMATS)
        form.addRow("Format", self.fmt)
        self.backing_only = QCheckBox("Backing track only (no individual stems)")
        form.addRow(self.backing_only)
        layout.addLayout(form)

        # Run
        self.start = QPushButton("Create backing track")
        self.start.clicked.connect(self._start)
        layout.addWidget(self.start)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        # Collapsible console output
        self.toggle = QToolButton()
        self.toggle.setText("Details")
        self.toggle.setCheckable(True)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.toggled.connect(self._toggle_log)
        layout.addWidget(self.toggle)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        self.log.setVisible(False)
        layout.addWidget(self.log, 1)
        layout.addStretch(0)

    # -- input helpers
    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a song", "", "Audio (*.mp3 *.wav *.flac);;All files (*)"
        )
        if path:
            self.source.setText(path)
            self._refresh_stems()

    def _pick_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose a folder with stems")
        if path:
            self.source.setText(path)
            self._refresh_stems()

    def _pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Output folder")
        if path:
            self.output.setText(path)

    def _set_stems(self, names: tuple[str, ...]) -> None:
        old = {n for n, c in self._checks.items() if c.isChecked()}
        while self.stem_layout.count():
            self.stem_layout.takeAt(0).widget().deleteLater()
        self._checks = {}
        for name in names:
            check = QCheckBox(name)
            check.setChecked(name in old)
            self._checks[name] = check
            self.stem_layout.addWidget(check)

    def _refresh_stems(self) -> None:
        text = self.source.text().strip()
        names = stems_of(Path(text)) if text and Path(text).exists() else DEFAULT_STEMS
        self._set_stems(names or DEFAULT_STEMS)

    def _toggle_log(self, on: bool) -> None:
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)
        self.log.setVisible(on)

    # -- run
    def _form(self) -> Form:
        text = self.source.text().strip()
        out = self.output.text().strip()
        return Form(
            source=Path(text) if text else None,
            solos=self.solos.toPlainText(),
            muted=tuple(n for n, c in self._checks.items() if c.isChecked()),
            output=Path(out) if out else None,
            fmt=self.fmt.currentText(),
            backing_only=self.backing_only.isChecked(),
        )

    def _start(self) -> None:
        try:
            song = build_song(self._form())
        except ConfigError as e:
            QMessageBox.warning(self, "soloslot", str(e))
            return
        self.log.clear()
        self.start.setEnabled(False)
        self.progress.setRange(0, 0)  # busy indicator
        self._thread = QThread()
        self._worker = Worker(song)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.line.connect(self.log.appendPlainText)
        self._worker.finished.connect(self._done)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    def _done(self, ok: bool) -> None:
        self.start.setEnabled(True)
        self.progress.setRange(0, 1)
        self.progress.setValue(1 if ok else 0)
        if not ok:
            self.toggle.setChecked(True)  # show why it failed
            QMessageBox.warning(self, "soloslot", "Failed. See Details for the reason.")
        else:
            self.log.appendPlainText("\nDone.")

    def closeEvent(self, event) -> None:
        # A running job cannot be cancelled safely; destroying its thread would crash.
        if self._thread is not None and self._thread.isRunning():
            QMessageBox.information(self, "soloslot", "Please wait until the job has finished.")
            event.ignore()
            return
        super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
