"""Render the README screenshots offscreen. Usage: python packaging/screenshots.py [OUT_DIR]"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "2")  # crisp on high-density screens
os.environ["SOLOSLOT_NO_UPDATE_CHECK"] = "1"

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from soloslot.gui.about import AboutDialog
from soloslot.gui.app import MainWindow
from soloslot.gui.branding import apply_style


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv[:1])
    light = app.palette()
    dark = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, "#1e293b"),
        (QPalette.ColorRole.WindowText, "#f1f5f9"),
        (QPalette.ColorRole.Base, "#0f172a"),
        (QPalette.ColorRole.AlternateBase, "#1e293b"),
        (QPalette.ColorRole.Text, "#f1f5f9"),
        (QPalette.ColorRole.Button, "#334155"),
        (QPalette.ColorRole.ButtonText, "#f1f5f9"),
        (QPalette.ColorRole.PlaceholderText, "#94a3b8"),
        (QPalette.ColorRole.Mid, "#475569"),
        (QPalette.ColorRole.Midlight, "#334155"),
    ):
        dark.setColor(role, QColor(color))
    # Offscreen Qt has no system theme, so the dark look is simulated with a palette.
    for palette, name in ((light, "light"), (dark, "dark")):
        app.setPalette(palette)
        apply_style(app)
        window = MainWindow()
        window.resize(600, 560)
        window.source.setText("Blue Bossa.mp3")
        window.solos.setPlainText("1:05-2:40")
        window._checks["guitar"].setChecked(True)
        window.show()
        app.processEvents()
        window.grab().save(str(out / f"window-{name}.png"))
        window.close()
    app.setPalette(light)
    apply_style(app)
    dialog = AboutDialog()
    dialog.resize(520, 420)
    dialog.show()
    app.processEvents()
    dialog.grab().save(str(out / "about.png"))
    print(f"screenshots written to {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "docs/screenshots"))
