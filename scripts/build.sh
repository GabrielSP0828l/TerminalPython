#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"

if [ ! -x "$PYTHON" ]; then
    echo "Erro: Python não encontrado em $PYTHON" >&2
    echo "Crie .venv ou informe PYTHON_BIN=/caminho/python3." >&2
    exit 1
fi

HOST_ARCH="$(uname -m)"
TARGET_ARCH="${APP247_TARGET_ARCH:-$HOST_ARCH}"
if [ "$HOST_ARCH" != "$TARGET_ARCH" ]; then
    echo "Erro: PyInstaller não faz cross-compile ($HOST_ARCH -> $TARGET_ARCH)." >&2
    echo "Execute este build em ARM64/aarch64 ou em pipeline ARM64 compatível." >&2
    exit 1
fi
echo "Build nativo para arquitetura: $HOST_ARCH"

if ! "$PYTHON" -c 'import PyInstaller' >/dev/null 2>&1; then
    echo "Erro: PyInstaller ausente. Instale requirements-build.txt." >&2
    exit 1
fi

rm -rf "$PROJECT_DIR/build" "$PROJECT_DIR/dist"
cd "$PROJECT_DIR"
PYTHONPATH="$PROJECT_DIR/src" "$PYTHON" -m PyInstaller \
    --noconfirm --clean app247-terminal.spec

EXECUTABLE="$PROJECT_DIR/dist/app247-terminal/app247-terminal"
if [ ! -x "$EXECUTABLE" ]; then
    echo "Erro: executável esperado não foi gerado: $EXECUTABLE" >&2
    exit 1
fi
echo "Build concluído: $EXECUTABLE"
