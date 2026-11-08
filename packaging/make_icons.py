"""Render the app icon to PNG, Windows .ico and macOS .icns files.

Usage: python packaging/make_icons.py OUTPUT_DIR   (needs PySide6)
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter

from soloslot.gui.branding import ASSETS, render_svg


def _png(svg: bytes, size: int) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    render_svg(svg, size).save(buf, "PNG")
    return bytes(QByteArray(buf.data()))


def make_ico(pngs: dict[int, bytes]) -> bytes:
    sizes = sorted(pngs)
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries, blobs = b"", b""
    for size in sizes:
        data = pngs[size]
        dim = 0 if size >= 256 else size  # 0 means 256
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return header + entries + blobs


ICNS_TYPES = {16: b"icp4", 32: b"icp5", 64: b"icp6", 128: b"ic07", 256: b"ic08", 512: b"ic09"}


def make_icns(pngs: dict[int, bytes]) -> bytes:
    body = b""
    for size, kind in ICNS_TYPES.items():
        body += kind + struct.pack(">I", len(pngs[size]) + 8) + pngs[size]
    return b"icns" + struct.pack(">I", len(body) + 8) + body


def _wizard_bmp(svg: bytes, width: int, height: int, logo: int, top: int) -> bytes:
    """A white BMP (Inno Setup wizard image) with the logo mark centred near the top."""
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    painter.drawImage((width - logo) // 2, top, render_svg(svg, logo))
    painter.end()
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "BMP")
    return bytes(QByteArray(buf.data()))


def main(out: Path) -> None:
    _app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    svg = (ASSETS / "app-icon.svg").read_bytes()
    pngs = {size: _png(svg, size) for size in (16, 24, 32, 48, 64, 128, 256, 512)}
    out.mkdir(parents=True, exist_ok=True)
    (out / "soloslot.png").write_bytes(pngs[256])
    (out / "soloslot.ico").write_bytes(
        make_ico({s: pngs[s] for s in (16, 24, 32, 48, 64, 128, 256)})
    )
    (out / "soloslot.icns").write_bytes(make_icns(pngs))
    mark = (ASSETS / "mark.svg").read_bytes()
    # Inno Setup picks the size that fits the user's display scaling.
    for scale, tag in ((1, ""), (2, "@2x")):
        (out / f"wizard{tag}.bmp").write_bytes(
            _wizard_bmp(mark, 164 * scale, 314 * scale, 120 * scale, 40 * scale)
        )
        (out / f"wizard-small{tag}.bmp").write_bytes(
            _wizard_bmp(mark, 55 * scale, 58 * scale, 44 * scale, 7 * scale)
        )
    print(f"icons written to {out}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))
