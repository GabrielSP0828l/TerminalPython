#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"

if [ ! -x "$PYTHON" ]; then
    echo "Erro: Python não encontrado em $PYTHON" >&2
    exit 1
fi

echo "A credencial não será exibida nem incluída nos argumentos do processo."
PYTHONPATH="$PROJECT_DIR/src" \
    "$PYTHON" -m app247_terminal.services.terminal_auth --install-from-stdin
