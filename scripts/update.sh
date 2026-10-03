#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "Uso: $0 PACOTE.tar.gz MANIFESTO.json [CHAVE_PUBLICA.pem]" >&2
    exit 2
fi

echo "Somente validação: esta base não baixa, ativa nem reinicia o Terminal."
PUBLIC_KEY="${3:-${APP247_UPDATE_PUBLIC_KEY_PATH:-/etc/app247/update-signing-public-key.pem}}"
PYTHONPATH="$PROJECT_DIR/src:$PROJECT_DIR" \
    "$PYTHON" -m updater.updater "$1" "$2" --public-key "$PUBLIC_KEY"
