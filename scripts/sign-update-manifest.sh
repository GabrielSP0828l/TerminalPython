#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"

PYTHONPATH="$PROJECT_DIR/src:$PROJECT_DIR" \
    "$PYTHON" -m updater.sign_manifest "$@"
