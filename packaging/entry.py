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
    from PySide6.QtWidgets import QApplication

    from soloslot.gui.app import MainWindow

    app = QApplication(sys.argv[:1])
    MainWindow()
    print("selftest ok")
    raise SystemExit(0)

from soloslot.gui.app import main

main()
