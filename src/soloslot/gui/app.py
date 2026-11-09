"""The window. Requires PySide6 (`pip install 'soloslot[gui]'`)."""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

try:
    from PySide6.QtCore import QObject, QProcess, Qt, QThread, QUrl, Signal
    from PySide6.QtGui import QAction, QDesktopServices
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
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

from soloslot import __version__, bootstrap
from soloslot.config import OUTPUT_FORMATS, ConfigError
from soloslot.gui.about import show_about
from soloslot.gui.branding import app_icon, apply_style, mark_pixmap
from soloslot.gui.model import (
    DEFAULT_STEMS,
    Form,
    backing_track_path,
    build_song,
    cli_args,
    reveal_command,
    separated_stems,
    stems_of,
)
from soloslot.gui.playerpanel import PlayerPanel
from soloslot.gui.regions import load_stems, slots_to_text, text_to_slots
from soloslot.process import process_song
from soloslot.update import Update, UpdateError, check_for_update, download_update


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

    def __init__(self, job):
        super().__init__()
        self._job = job  # called with a log function, returns True on success

    def run(self) -> None:
        stream = _Stream(self.line.emit)
        try:
            with contextlib.redirect_stderr(stream), contextlib.redirect_stdout(stream):
                ok = self._job(self.line.emit)
        except Exception as e:  # show anything unexpected in the log instead of dying silently
            self.line.emit(f"  ERROR: {type(e).__name__}: {e}")
            ok = False
        self.finished.emit(ok)


class Task(QObject):
    """Runs `fn` on a worker thread and reports (result, error text)."""

    done = Signal(object, str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            self.done.emit(self._fn(), "")
        except UpdateError as e:
            self.done.emit(None, str(e))
        except Exception as e:  # never let a background check crash the app
            self.done.emit(None, f"{type(e).__name__}: {e}")


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"soloslot {__version__}")
        self.setWindowIcon(app_icon())  # title bar and taskbar, also on Windows
        self.resize(720, 860)
        self._thread: QThread | None = None
        self._worker: Worker | None = None
        self._checks: dict[str, QCheckBox] = {}
        self._preview_path: Path | None = None
        self._stems_folder: Path | None = None  # where the last run left the split stems

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        help_menu = self.menuBar().addMenu("&Help")
        about = QAction("&About soloslot…", self)
        about.setMenuRole(QAction.MenuRole.AboutRole)
        about.triggered.connect(lambda: show_about(self))
        check = QAction("Check for &updates…", self)
        check.triggered.connect(self.check_updates_manually)
        help_menu.addAction(check)
        help_menu.addAction(about)

        # Header: logo and name
        header = QHBoxLayout()
        header.setSpacing(12)
        self.logo = QLabel()
        self.logo.setPixmap(mark_pixmap(56))
        header.addWidget(self.logo)
        names = QVBoxLayout()
        names.setSpacing(0)
        title = QLabel("soloslot")
        title.setObjectName("title")
        tagline = QLabel("Make room for your solo.")
        tagline.setObjectName("tagline")
        names.addWidget(title)
        names.addWidget(tagline)
        header.addLayout(names, 1)
        layout.addLayout(header)

        # Update notice (hidden until a newer release is found)
        self.banner = QFrame()
        self.banner.setObjectName("banner")
        banner_row = QHBoxLayout(self.banner)
        banner_row.setContentsMargins(0, 0, 0, 0)
        self.banner_text = QLabel()
        self.banner_text.setWordWrap(True)
        self.banner_button = QPushButton()
        self.banner_button.clicked.connect(self._update_clicked)
        banner_row.addWidget(self.banner_text, 1)
        banner_row.addWidget(self.banner_button)
        self.banner.setVisible(False)
        layout.addWidget(self.banner)
        self._update: Update | None = None
        self._tasks: list[tuple[QThread, Task]] = []

        # Input
        layout.addWidget(self._caption("Song or stems"))
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
        layout.addWidget(self._caption("Solo regions"))
        self.solos = QPlainTextEdit()
        self.solos.setPlaceholderText("One solo per line: START-END, e.g. 2:15-3:40")
        self.solos.setFixedHeight(84)
        self.solos.textChanged.connect(self._solos_typed)
        layout.addWidget(self.solos)

        # Player: draw the solo slots on the waveform and listen to the result
        layout.addWidget(self._caption("Player"))
        self.panel = PlayerPanel()
        self.panel.slotsChanged.connect(self._slots_drawn)
        layout.addWidget(self.panel)

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
        self.start.setObjectName("primary")
        self.start.setDefault(True)
        self.start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start.clicked.connect(self._start)
        layout.addWidget(self.start)
        self.open_output = QPushButton("Open output folder")
        self.open_output.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_output.setVisible(False)
        self.open_output.clicked.connect(self._open_output)
        layout.addWidget(self.open_output)
        self._result: Path | None = None
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

    @staticmethod
    def _caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("caption")
        return label

    # -- updates
    def _run_task(self, fn, slot) -> None:
        thread, task = QThread(), Task(fn)
        task.moveToThread(thread)
        thread.started.connect(task.run)
        task.done.connect(slot)
        task.done.connect(thread.quit)
        self._tasks.append((thread, task))
        thread.start()

    def check_updates(self) -> None:
        if os.environ.get("SOLOSLOT_NO_UPDATE_CHECK"):
            return
        self._run_task(lambda: check_for_update(__version__), self._update_found)

    def check_updates_manually(self) -> None:
        self._run_task(lambda: check_for_update(__version__), self._manual_result)

    def _manual_result(self, update, error: str) -> None:
        if error:
            QMessageBox.warning(self, "soloslot", f"Could not check for updates.\n\n{error}")
        elif update is None:
            QMessageBox.information(self, "soloslot", f"soloslot {__version__} is up to date.")
        else:
            self._update_found(update, "")

    def _update_found(self, update, error: str) -> None:
        if error or update is None:
            return  # offline or up to date: stay quiet
        self._update = update
        self.banner_text.setText(f"soloslot {update.version} is available.")
        installable = _frozen() and update.asset_url is not None
        self.banner_button.setText("Download and install" if installable else "Release page")
        self.banner.setVisible(True)

    def _update_clicked(self) -> None:
        update = self._update
        if update is None:
            return
        if not (_frozen() and update.asset_url):
            QDesktopServices.openUrl(QUrl(update.page))
            return
        self.banner_button.setEnabled(False)
        self.banner_text.setText(f"Downloading soloslot {update.version}…")
        folder = Path.home() / "Downloads"
        self._run_task(lambda: download_update(update, folder), self._downloaded)

    def _downloaded(self, path, error: str) -> None:
        self.banner_button.setEnabled(True)
        if error or path is None:
            self.banner_text.setText(f"Update failed: {error}")
            return
        self.banner_text.setText(f"Downloaded {path.name}. Close soloslot to finish the update.")
        # Windows runs the installer, macOS mounts the disk image, Linux shows the folder.
        target = path.parent if sys.platform.startswith("linux") else path
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

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
            check.toggled.connect(lambda _on: self.panel.set_muted(self._muted()))
            self._checks[name] = check
            self.stem_layout.addWidget(check)

    def _refresh_stems(self) -> None:
        text = self.source.text().strip()
        names = stems_of(Path(text)) if text and Path(text).exists() else DEFAULT_STEMS
        self._set_stems(names or DEFAULT_STEMS)
        path = Path(text) if text and Path(text).exists() else None
        out = self.output.text().strip()
        # A song that was split before plays from its stems, so A/B works right away.
        self._load_preview(separated_stems(path, Path(out) if out else None) or path)

    def _load_preview(self, path: Path | None) -> None:
        if path is None:
            self.panel.clear()
            return
        self.panel.set_loading()
        self._preview_path = path

        def work():  # runs on a worker thread
            try:
                return path, load_stems(path), ""
            except Exception as e:
                return path, None, f"{type(e).__name__}: {e}"

        # A bound method (not a lambda), so the result is handled on the GUI thread.
        self._run_task(work, self._preview_loaded)

    def _preview_loaded(self, result, _error: str) -> None:
        path, stems, error = result
        if path != self._preview_path:
            return  # the user picked something else meanwhile
        if error or stems is None:
            self.panel.clear(f"Cannot show waveform: {error}")
            return
        self.panel.set_stems(stems)
        self.panel.set_slots(text_to_slots(self.solos.toPlainText()))
        self.panel.set_muted(self._muted())

    def _muted(self) -> tuple[str, ...]:
        return tuple(n for n, c in self._checks.items() if c.isChecked())

    def _solos_typed(self) -> None:
        self.panel.set_slots(text_to_slots(self.solos.toPlainText()))

    def _slots_drawn(self, slots: list) -> None:
        self.solos.blockSignals(True)
        self.solos.setPlainText(slots_to_text(slots))
        self.solos.blockSignals(False)

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
            muted=self._muted(),
            output=Path(out) if out else None,
            fmt=self.fmt.currentText(),
            backing_only=self.backing_only.isChecked(),
        )

    def _start(self) -> None:
        form = self._form()
        try:
            song = build_song(form)
            job = self._make_job(form, song)
        except ConfigError as e:
            QMessageBox.warning(self, "soloslot", str(e))
            return
        if job is None:
            return
        self.log.clear()
        self.open_output.setVisible(False)
        self._result = backing_track_path(song)
        self._stems_folder = song.folder if song.input is not None else None
        self.start.setEnabled(False)
        self.progress.setRange(0, 0)  # busy indicator
        self._thread = QThread()
        self._worker = Worker(job)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.line.connect(self.log.appendPlainText)
        self._worker.finished.connect(self._done)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    def _make_job(self, form: Form, song):
        """What to run. The installed app splits songs in a private environment with Demucs."""
        if not (_frozen() and song.input is not None):
            return lambda log: process_song(song, log=log)
        args = cli_args(form)
        if not bootstrap.is_installed():
            answer = QMessageBox.question(
                self,
                "Set up stem separation",
                "Splitting a song needs PyTorch and Demucs. They are downloaded once "
                "(about 1 to 2 GB) and kept in your user folder.\n\nSet up now?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return None

        def job(log) -> bool:
            try:
                bootstrap.install_separation(__version__, log=log)
            except bootstrap.SetupError as e:
                log(f"  ERROR: {e}")
                return False
            return bootstrap.run_separation(args, log=log)

        return job

    def _done(self, ok: bool) -> None:
        self.start.setEnabled(True)
        self.progress.setRange(0, 1)
        self.progress.setValue(1 if ok else 0)
        if not ok:
            self.toggle.setChecked(True)  # show why it failed
            QMessageBox.warning(self, "soloslot", "Failed. See Details for the reason.")
        else:
            self.log.appendPlainText("\nDone.")
            if self._stems_folder is not None and self._stems_folder.is_dir():
                self._load_preview(self._stems_folder)  # the split stems unlock A/B
            self.open_output.setVisible(self._result is not None)

    def _open_output(self) -> None:
        """Show the result in the file manager, with the backing track selected where possible."""
        if self._result is None:
            return
        folder = self._result.parent
        cmd = reveal_command(self._result) if self._result.exists() else None
        if cmd and QProcess.startDetached(cmd[0], cmd[1:]):
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def closeEvent(self, event) -> None:
        self.panel.player.stop()
        # A running job cannot be cancelled safely; destroying its thread would crash.
        for thread, _ in self._tasks:
            thread.quit()
            thread.wait(2000)
        if self._thread is not None and self._thread.isRunning():
            QMessageBox.information(self, "soloslot", "Please wait until the job has finished.")
            event.ignore()
            return
        super().closeEvent(event)


def _set_windows_app_id() -> None:
    """Give Windows our own identity so the taskbar shows the soloslot icon, not Python's."""
    if sys.platform == "win32":
        import ctypes

        with contextlib.suppress(Exception):
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("soloslot.soloslot.gui")


def main() -> None:
    _set_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName("soloslot")
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("soloslot")
    apply_style(app)
    window = MainWindow()
    window.show()
    window.check_updates()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
