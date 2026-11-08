import os
import struct

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from soloslot import __version__
from soloslot.gui.about import AboutDialog, notices_text
from soloslot.gui.branding import app_icon, apply_style, mark_pixmap


def test_about_dialog_shows_version_and_licenses():
    QApplication.instance() or QApplication([])
    dialog = AboutDialog()
    assert dialog.tabs.count() == 2
    labels = [label.text() for label in dialog.tabs.widget(0).findChildren(QLabel)]
    assert f"Version {__version__}" in labels
    licenses = dialog.licenses.toPlainText()
    assert "PySide6" in licenses
    assert "LGPL" in licenses
    assert notices_text().startswith("# Licenses")


def test_logo_and_icon_render():
    app = QApplication.instance() or QApplication([])
    apply_style(app)
    assert not app_icon().isNull()
    assert not mark_pixmap(44).isNull()
    assert app.windowIcon().availableSizes()


def test_icon_files_are_valid(tmp_path):
    import importlib.util
    from pathlib import Path

    QApplication.instance() or QApplication([])
    path = Path(__file__).parent.parent / "packaging" / "make_icons.py"
    spec = importlib.util.spec_from_file_location("make_icons", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main(tmp_path)
    ico = (tmp_path / "soloslot.ico").read_bytes()
    assert struct.unpack("<HHH", ico[:6]) == (0, 1, 7)
    assert (tmp_path / "soloslot.icns").read_bytes()[:4] == b"icns"
    assert (tmp_path / "soloslot.png").read_bytes()[:4] == b"\x89PNG"
