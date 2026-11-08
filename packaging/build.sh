#!/usr/bin/env bash
# Build the slim desktop app (no PyTorch/Demucs) into dist/soloslot[.app] with PyInstaller.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run --extra gui --with pyinstaller pyinstaller --noconfirm --clean --windowed \
  --name soloslot --paths src \
  --exclude-module torch --exclude-module demucs \
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtQml \
  packaging/entry.py
