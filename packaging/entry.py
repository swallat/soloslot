"""Entry point of the frozen (PyInstaller) desktop app."""

import os
import sys

from soloslot import __version__

if "--version" in sys.argv:
    print(f"soloslot {__version__}")
    raise SystemExit(0)

if "--selftest" in sys.argv:
    # CI smoke test: build the window without showing it.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import sounddevice  # noqa: F401  (fails if PortAudio is not bundled)
    import soundfile
    from PySide6.QtWidgets import QApplication

    from soloslot.gui.about import AboutDialog
    from soloslot.gui.app import MainWindow
    from soloslot.gui.branding import apply_style

    # The slim bundle must ship a libsndfile that can write MP3.
    assert "MP3" in soundfile.available_formats(), "libsndfile without MP3 support"
    app = QApplication(sys.argv[:1])
    apply_style(app)
    AboutDialog()  # fails if the bundled logo or license notices are missing
    window = MainWindow()
    assert not window.windowIcon().isNull(), "window icon missing"
    print("selftest ok")
    raise SystemExit(0)

from soloslot.gui.app import main

main()
