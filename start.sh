#!/usr/bin/env bash

set -u

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

cd "$PROJECT_DIR" || exit 1
export PYTHONPATH="$PROJECT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

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
    if ! "$PYTHON" -m app247_terminal.services.display_service --apply "$DISPLAY_ORIENTATION" --no-persist; then
        echo "[TERMINAL] Aviso: não foi possível aplicar a orientação solicitada."
    fi
else
    echo "[TERMINAL] Aplicando orientação salva..."
    if ! "$PYTHON" -m app247_terminal.services.display_service --apply-saved; then
        echo "[TERMINAL] Aviso: não foi possível aplicar a orientação salva."
    fi
fi

exec "$PYTHON" -m app247_terminal
