#!/usr/bin/env bash

set -u

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

cd "$PROJECT_DIR" || exit 1

# Girar tela para vertical
if command -v wlr-randr >/dev/null 2>&1; then
    echo "[TERMINAL] Girando tela HDMI-A-2..."
    wlr-randr --output HDMI-A-2 --transform 90
else
    echo "[TERMINAL] Aviso: wlr-randr não encontrado."
fi

if [ -x "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"

elif [ -x "$PROJECT_DIR/venv/bin/python" ]; then
    PYTHON="$PROJECT_DIR/venv/bin/python"

else
    PYTHON="${PYTHON_BIN:-python3}"
fi

echo "[TERMINAL] Python: $PYTHON"

exec "$PYTHON" main.py