#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"

if [ "$#" -ne 3 ]; then
    echo "Uso: $0 PACOTE.tar.gz MANIFESTO.json MANIFESTO.json.sig" >&2
    exit 2
fi
if [ ! -x "$PYTHON" ]; then
    echo "Erro: Python do projeto não encontrado em $PYTHON." >&2
    exit 1
fi

PUBLIC_KEY="${APP247_UPDATE_PUBLIC_KEY:-${APP247_UPDATE_PUBLIC_KEY_PATH:-/etc/app247/update-signing-public-key.pem}}"
if [ ! -f "$PUBLIC_KEY" ] || [ -L "$PUBLIC_KEY" ]; then
    echo "Erro: informe a trust anchor por APP247_UPDATE_PUBLIC_KEY ou instale-a em /etc/app247." >&2
    exit 1
fi

PYTHONPATH="$PROJECT_DIR/src:$PROJECT_DIR" \
    "$PYTHON" -m updater.release_archive verify \
    "$1" "$2" "$3" --public-key "$PUBLIC_KEY"
