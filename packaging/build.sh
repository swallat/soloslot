#!/usr/bin/env bash
# Build the slim desktop app (no PyTorch/Demucs) into dist/soloslot[.app] with PyInstaller.
set -euo pipefail
cd "$(dirname "$0")/.."

# Icons and the data folder (logo, license notices) that the window reads at run time.
uv run --extra gui python packaging/make_icons.py packaging/icons
sep=$(uv run --no-project python -c "import os; print(os.pathsep)")
case "$(uname -s)" in
  Darwin) icon=packaging/icons/soloslot.icns ;;
  MINGW*|MSYS*|CYGWIN*) icon=packaging/icons/soloslot.ico ;;
  *) icon=packaging/icons/soloslot.png ;;
esac

uv run --extra gui --with pyinstaller pyinstaller --noconfirm --clean --windowed \
  --name soloslot --paths src --icon "$icon" \
  --add-data "src/soloslot/gui/assets${sep}soloslot/gui/assets" \
  --exclude-module torch --exclude-module demucs \
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtQml \
  packaging/entry.py
