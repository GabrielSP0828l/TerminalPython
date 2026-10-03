#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
HOST_ARCH_RAW="$(uname -m)"

normalize_arch() {
    case "${1,,}" in
        arm64) echo "aarch64" ;;
        amd64) echo "x86_64" ;;
        *) echo "${1,,}" ;;
    esac
}

HOST_ARCH="$(normalize_arch "$HOST_ARCH_RAW")"
TARGET_ARCH="$(normalize_arch "${APP247_TARGET_ARCH:-$HOST_ARCH}")"
if [ "$HOST_ARCH" != "$TARGET_ARCH" ]; then
    echo "Erro: PyInstaller não faz cross-compile ($HOST_ARCH -> $TARGET_ARCH)." >&2
    echo "Execute este build em ARM64/aarch64 ou em pipeline ARM64 compatível." >&2
    exit 1
fi
echo "Build nativo para arquitetura: $HOST_ARCH"

prepare_arm64_python() {
    local system_python="${APP247_SYSTEM_PYTHON:-/usr/bin/python3}"
    local build_venv="${APP247_ARM64_BUILD_VENV:-$PROJECT_DIR/.venv-build-aarch64}"
    local system_pyqt
    local build_pyqt

    if [ ! -x "$system_python" ]; then
        echo "Erro: Python do sistema não encontrado em $system_python." >&2
        exit 1
    fi
    if ! system_pyqt="$($system_python -c 'import PyQt5, PyQt5.QtSvg; print(PyQt5.__file__)' 2>/dev/null)"; then
        echo "Erro: PyQt5 do sistema não está disponível no Raspberry." >&2
        echo "Instale: sudo apt install python3-venv python3-pyqt5 python3-pyqt5.qtsvg" >&2
        exit 1
    fi

    if [ -n "${PYTHON_BIN:-}" ]; then
        PYTHON="$PYTHON_BIN"
    else
        if [ ! -x "$build_venv/bin/python" ]; then
            echo "Criando venv ARM64 com acesso ao python3-pyqt5 do sistema..."
            "$system_python" -m venv --system-site-packages "$build_venv"
        fi
        PYTHON="$build_venv/bin/python"
    fi

    if [ ! -x "$PYTHON" ]; then
        echo "Erro: Python de build ARM64 não encontrado em $PYTHON." >&2
        exit 1
    fi
    if ! build_pyqt="$($PYTHON -c 'import PyQt5, PyQt5.QtSvg; print(PyQt5.__file__)' 2>/dev/null)"; then
        echo "Erro: $PYTHON não enxerga o PyQt5 do sistema." >&2
        echo "Recrie o venv ARM64 com --system-site-packages." >&2
        exit 1
    fi
    if [ "$build_pyqt" != "$system_pyqt" ]; then
        echo "Erro: o build ARM64 selecionou outro PyQt5: $build_pyqt" >&2
        echo "Esperado o pacote do sistema: $system_pyqt" >&2
        exit 1
    fi

    if ! "$PYTHON" -c \
        'import PyInstaller, dotenv, qrcode, PIL, requests, websocket, cryptography' \
        >/dev/null 2>&1; then
        if "$PYTHON" -c 'import sys; raise SystemExit(sys.prefix != sys.base_prefix)' \
            >/dev/null 2>&1; then
            echo "Erro: dependências ausentes no Python global $PYTHON." >&2
            echo "Omita PYTHON_BIN para o script usar o venv ARM64 dedicado." >&2
            exit 1
        fi
        echo "Instalando dependências de build ARM64 sem substituir o PyQt5 do sistema..."
        "$PYTHON" -m pip install \
            -r "$PROJECT_DIR/requirements-arm64.txt" \
            -r "$PROJECT_DIR/requirements-build.txt"
    fi
    echo "PyQt5 do sistema: $system_pyqt"
}

if [ "$HOST_ARCH" = "aarch64" ]; then
    prepare_arm64_python
else
    PYTHON="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"
fi

if [ ! -x "$PYTHON" ]; then
    echo "Erro: Python não encontrado em $PYTHON" >&2
    echo "Crie .venv ou informe PYTHON_BIN=/caminho/python3." >&2
    exit 1
fi

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
