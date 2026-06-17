#!/usr/bin/env bash
# Double-click launcher for the spritekit GUI (macOS). On Linux use start_linux.sh.
cd "$(dirname "$0")" || exit 1

PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python
command -v "$PY" >/dev/null 2>&1 || { echo "Python 3 not found. Install from https://python.org and retry."; read -r _; exit 1; }

"$PY" -c "import numpy, scipy, PIL" >/dev/null 2>&1 || {
    echo "Installing dependencies, one moment..."
    "$PY" -m pip install -r "$(dirname "$0")/requirements.txt" || { echo "pip install failed."; read -r _; exit 1; }
}

exec "$PY" "$(dirname "$0")/__main__.py" gui
