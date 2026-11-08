"""About dialog: version, author, links and third-party licenses. Requires PySide6."""

from __future__ import annotations

import platform

from PySide6.QtCore import Qt
from PySide6.QtCore import __version__ as qt_version
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from soloslot import __version__
from soloslot.gui.branding import ASSETS, mark_pixmap

REPO = "https://github.com/swallat/soloslot"
LINKS = (
    ("Website and source", REPO),
    ("Report a problem", f"{REPO}/issues"),
    ("Releases", f"{REPO}/releases"),
)
NOTICES = ASSETS / "THIRD_PARTY_NOTICES.md"


def notices_text() -> str:
    try:
        return NOTICES.read_text("utf-8")
    except OSError:
        return f"The license notices were not found. See {REPO}/blob/main/LICENSE."


def _about_tab() -> QWidget:
    tab = QWidget()
    layout = QVBoxLayout(tab)
    layout.setSpacing(6)
    layout.setContentsMargins(0, 16, 0, 0)

    logo = QLabel()
    logo.setPixmap(mark_pixmap(72))
    logo.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout.addWidget(logo)

    title = QLabel("soloslot")
    title.setObjectName("title")
    title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout.addWidget(title)

    version = QLabel(f"Version {__version__}")
    version.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout.addWidget(version)

    tagline = QLabel("Make room for your solo.")
    tagline.setObjectName("tagline")
    tagline.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout.addWidget(tagline)
    layout.addSpacing(10)

    links = QLabel(" · ".join(f'<a href="{url}">{name}</a>' for name, url in LINKS))
    links.setOpenExternalLinks(True)
    links.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    layout.addWidget(links)
    layout.addSpacing(10)

    legal = QLabel(
        "© 2026 Sebastian Wallat. Released under the MIT License.<br>"
        "soloslot is built on open-source software. See the Licenses tab."
    )
    legal.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    legal.setWordWrap(True)
    layout.addWidget(legal)
    layout.addStretch(1)

    build = QLabel(
        f"Python {platform.python_version()} · PySide6 / Qt {qt_version} · {platform.system()}"
    )
    build.setObjectName("tagline")
    build.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    build.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(build)
    return tab


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About soloslot")
        self.resize(520, 480)
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(_about_tab(), "About")

        self.licenses = QTextBrowser()
        self.licenses.setOpenExternalLinks(True)
        self.licenses.setMarkdown(notices_text())
        self.tabs.addTab(self.licenses, "Licenses")
        layout.addWidget(self.tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(buttons)
        layout.addLayout(row)


def show_about(parent=None) -> None:
    AboutDialog(parent).exec()


__all__ = ["REPO", "AboutDialog", "notices_text", "show_about"]
