"""Logo, colours and the window style. Requires PySide6."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QImage, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer

ASSETS = Path(__file__).parent / "assets"

AMBER = "#f59e0b"  # the solo
AMBER_HOVER = "#fbbf24"
AMBER_PRESSED = "#d97706"
INK = "#0f172a"  # text on amber (contrast 8:1)
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)


def render_svg(svg: bytes | str, size: int) -> QImage:
    """Rasterise an SVG into a transparent square image."""
    data = svg.encode() if isinstance(svg, str) else svg
    renderer = QSvgRenderer(QByteArray(data))
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return image


def app_icon() -> QIcon:
    """The rounded-square application icon, used for the window, taskbar and installers."""
    svg = (ASSETS / "app-icon.svg").read_bytes()
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(QPixmap.fromImage(render_svg(svg, size)))
    return icon


def _is_dark() -> bool:
    app = QGuiApplication.instance()
    if app is None:
        return False
    return app.palette().color(QPalette.ColorRole.Window).lightness() < 128


def mark_pixmap(size: int) -> QPixmap:
    """The logo mark (waveform with the amber gap) for the current light or dark theme."""
    svg = (ASSETS / "mark.svg").read_text("utf-8")
    if _is_dark():
        svg = svg.replace("#64748b", "#94a3b8")
    ratio = 2  # crisp on high-density screens
    pixmap = QPixmap.fromImage(render_svg(svg, size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


STYLESHEET = f"""
QGroupBox {{
    border: 1px solid palette(mid);
    border-radius: 8px;
    margin-top: 12px;
    padding: 14px 10px 8px 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    font-weight: 600;
}}
QLineEdit, QPlainTextEdit, QComboBox {{
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 6px 8px;
    background: palette(base);
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 2px solid {AMBER};
    padding: 5px 7px;
}}
QPushButton {{
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 6px 14px;
    min-height: 20px;
    background: palette(button);
}}
QPushButton:hover {{ border-color: {AMBER}; }}
QPushButton:focus {{ border: 2px solid {AMBER}; padding: 5px 13px; }}
QPushButton:disabled {{ color: palette(mid); }}
QPushButton#primary {{
    background: {AMBER};
    color: {INK};
    border: 1px solid {AMBER_PRESSED};
    font-size: 15px;
    font-weight: 600;
    padding: 10px 18px;
}}
QPushButton#primary:hover {{ background: {AMBER_HOVER}; }}
QPushButton#primary:pressed {{ background: {AMBER_PRESSED}; }}
QPushButton#primary:disabled {{
    background: palette(midlight);
    color: palette(mid);
    border-color: palette(mid);
}}
QPushButton#transport, QPushButton#transportMain {{ padding: 6px 0; }}
QPushButton#transportMain {{
    background: {AMBER};
    border: 1px solid {AMBER_PRESSED};
}}
QPushButton#transportMain:hover {{ background: {AMBER_HOVER}; }}
QPushButton#transportMain:pressed {{ background: {AMBER_PRESSED}; }}
QPushButton#transportMain:disabled {{
    background: palette(midlight);
    border-color: palette(mid);
}}
QProgressBar {{ border: none; border-radius: 3px; background: palette(midlight); max-height: 6px; }}
QProgressBar::chunk {{ background: {AMBER}; border-radius: 3px; }}
QCheckBox {{ spacing: 8px; padding: 4px 6px; }}
QFrame#banner {{
    background: rgba(245, 158, 11, 0.16);
    border: 1px solid {AMBER};
    border-radius: 8px;
}}
QLabel#title {{ font-size: 22px; font-weight: 700; }}
QLabel#tagline {{ color: palette(placeholder-text); }}
QLabel#caption {{ font-weight: 600; }}
QToolButton {{ padding: 4px 6px; border: none; }}
"""


def apply_style(app) -> None:
    """Fusion style with an amber accent, so the window looks the same on every platform."""
    app.setStyle("Fusion")
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Highlight, QColor(AMBER))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(INK))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(app_icon())
