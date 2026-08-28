#!/usr/bin/env bash

set -u

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

cd "$PROJECT_DIR" || exit 1

if [ -x "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"

elif [ -x "$PROJECT_DIR/venv/bin/python" ]; then
    PYTHON="$PROJECT_DIR/venv/bin/python"

else
    PYTHON="${PYTHON_BIN:-python3}"
fi

echo "[TERMINAL] Python: $PYTHON"

exec "$PYTHON" main.py
