#!/usr/bin/env bash
# Double-click launcher for the spritekit GUI (Linux). On macOS use start_macos.command.
cd "$(dirname "$0")" || exit 1

PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python
command -v "$PY" >/dev/null 2>&1 || { echo "Python 3 not found. Install from https://python.org and retry."; read -r _; exit 1; }

"$PY" -c "import numpy, scipy, PIL, jurigged" >/dev/null 2>&1 || {
    echo "Installing dependencies, one moment..."
    "$PY" -m pip install -r "$(dirname "$0")/requirements.txt" || { echo "pip install failed."; read -r _; exit 1; }
}

# Launch under jurigged so edits hot-reload live (no restart). -w watches this folder;
# -v prints "Update <fn>" in this terminal each time a file reloads. The window title
# also shows "hot reload" while it's active.
echo 'Watch this terminal: it prints "Update ..." whenever a code edit reloads live.'
exec "$PY" -m jurigged -v -w "$(dirname "$0")" "$(dirname "$0")/__main__.py" gui
