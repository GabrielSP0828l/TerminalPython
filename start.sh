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

if [ -n "${DISPLAY_ORIENTATION:-}" ]; then
    echo "[TERMINAL] Aplicando orientação da sessão: $DISPLAY_ORIENTATION"
    if ! "$PYTHON" -m service.DisplayService --apply "$DISPLAY_ORIENTATION" --no-persist; then
        echo "[TERMINAL] Aviso: não foi possível aplicar a orientação solicitada."
    fi
elif [ -f "$PROJECT_DIR/db/display_orientation" ]; then
    echo "[TERMINAL] Aplicando orientação salva..."
    if ! "$PYTHON" -m service.DisplayService --apply-saved; then
        echo "[TERMINAL] Aviso: não foi possível aplicar a orientação salva."
    fi
fi

exec "$PYTHON" main.py
