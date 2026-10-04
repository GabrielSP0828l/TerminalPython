#!/usr/bin/env bash
set -Eeuo pipefail

umask 027

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"
EXECUTABLE="$PROJECT_DIR/dist/app247-terminal/app247-terminal"
ARTIFACT_DIR="$PROJECT_DIR/dist/app247-terminal"
RELEASE_DIR="${APP247_RELEASE_DIR:-$PROJECT_DIR/release}"
PRIVATE_KEY="${APP247_UPDATE_PRIVATE_KEY:-}"
PUBLIC_KEY="${APP247_UPDATE_PUBLIC_KEY:-${APP247_UPDATE_PUBLIC_KEY_PATH:-}}"
PASSWORD_FILE="${APP247_UPDATE_PRIVATE_KEY_PASSWORD_FILE:-}"

if [ "$#" -ne 1 ]; then
    echo "Uso: $0 VERSAO" >&2
    exit 2
fi
VERSION="$1"
if [ ! -x "$PYTHON" ]; then
    echo "Erro: Python do projeto não encontrado em $PYTHON." >&2
    exit 1
fi
if ! PYTHONPATH="$PROJECT_DIR/src:$PROJECT_DIR" "$PYTHON" -c \
    'from updater.version import Version; import sys; Version.parse(sys.argv[1])' \
    "$VERSION"; then
    echo "Erro: versão SemVer inválida: $VERSION" >&2
    exit 2
fi
if [ ! -x "$EXECUTABLE" ]; then
    echo "Erro: build onedir ausente: $EXECUTABLE" >&2
    echo "Execute ./scripts/build.sh antes do empacotamento." >&2
    exit 1
fi
if [ -z "$PRIVATE_KEY" ] || [ ! -f "$PRIVATE_KEY" ] || [ -L "$PRIVATE_KEY" ]; then
    echo "Erro: informe uma chave privada Ed25519 regular em APP247_UPDATE_PRIVATE_KEY." >&2
    exit 1
fi
if [ -z "$PUBLIC_KEY" ] || [ ! -f "$PUBLIC_KEY" ] || [ -L "$PUBLIC_KEY" ]; then
    echo "Erro: informe a trust anchor em APP247_UPDATE_PUBLIC_KEY." >&2
    exit 1
fi
if [ -n "$PASSWORD_FILE" ] && { [ ! -f "$PASSWORD_FILE" ] || [ -L "$PASSWORD_FILE" ]; }; then
    echo "Erro: arquivo de senha da chave privada inválido." >&2
    exit 1
fi

INTERNAL_VERSION="$($EXECUTABLE --version)"
if [ "$INTERNAL_VERSION" != "$VERSION" ]; then
    echo "Erro: versão interna $INTERNAL_VERSION diverge da versão solicitada $VERSION." >&2
    exit 1
fi

detect_host_architecture() {
    local detected
    if command -v dpkg >/dev/null 2>&1; then
        detected="$(dpkg --print-architecture 2>/dev/null || true)"
        if [ -n "$detected" ]; then
            printf '%s\n' "$detected"
            return
        fi
    fi
    case "$(uname -m | tr '[:upper:]' '[:lower:]')" in
        aarch64|arm64) printf '%s\n' arm64 ;;
        armv6l|armv7|armv7l) printf '%s\n' armhf ;;
        x86_64|amd64) printf '%s\n' amd64 ;;
        *)
            echo "Erro: arquitetura do host não suportada: $(uname -m)" >&2
            return 1
            ;;
    esac
}

HOST_ARCH="$(detect_host_architecture)"
BINARY_ARCH="$(PYTHONPATH="$PROJECT_DIR/src:$PROJECT_DIR" \
    "$PYTHON" -m updater.release_archive detect-architecture "$EXECUTABLE")"
if [ "$HOST_ARCH" != "$BINARY_ARCH" ]; then
    echo "Erro: arquitetura incompatível: host=$HOST_ARCH binário=$BINARY_ARCH" >&2
    exit 1
fi

mkdir -p "$RELEASE_DIR"
WORK_DIR="$(mktemp -d "$RELEASE_DIR/.package-release.XXXXXX")"
cleanup() {
    rm -rf -- "$WORK_DIR"
}
trap cleanup EXIT INT TERM

DIAGNOSTIC_DATA="$WORK_DIR/diagnostic-data"
mkdir -m 0700 "$DIAGNOSTIC_DATA"
echo "Executando diagnóstico isolado do bundle..."
env \
    APP247_CONFIG_FILE="$WORK_DIR/nonexistent.env" \
    APP247_DIAGNOSTIC_MODE=release \
    APP247_ENV=test \
    APP247_API_URL=https://release-check.invalid \
    APP247_WS_URL=wss://release-check.invalid \
    APP247_DATA_DIR="$DIAGNOSTIC_DATA" \
    APP247_DB_PATH="$DIAGNOSTIC_DATA/terminal.db" \
    APP247_DEVICE_CREDENTIAL_PATH="$DIAGNOSTIC_DATA/device-credential" \
    "$EXECUTABLE" --check

ROOT_NAME="app247-terminal-$VERSION"
STAGING_ROOT="$WORK_DIR/staging/$ROOT_NAME"
mkdir -p "$STAGING_ROOT/app"
cp -a "$ARTIFACT_DIR/." "$STAGING_ROOT/app/"
install -m 0755 "$PROJECT_DIR/scripts/install.sh" "$STAGING_ROOT/install.sh"
install -m 0644 "$PROJECT_DIR/packaging/systemd/app247-terminal.service" \
    "$STAGING_ROOT/app247-terminal.service"
install -m 0755 "$PROJECT_DIR/packaging/app247-terminal-launcher" \
    "$STAGING_ROOT/app247-terminal-launcher"
install -m 0640 "$PROJECT_DIR/packaging/terminal.env.production.example" \
    "$STAGING_ROOT/terminal.env.production.example"
install -m 0644 "$PUBLIC_KEY" "$STAGING_ROOT/update-signing-public-key.pem"
printf '%s\n' "$VERSION" > "$STAGING_ROOT/VERSION"

ARTIFACT_NAME="app247-terminal-$VERSION-$HOST_ARCH.tar.gz"
MANIFEST_NAME="app247-terminal-$VERSION-$HOST_ARCH.manifest.json"
SIGNATURE_NAME="$MANIFEST_NAME.sig"
ARTIFACT_FINAL="$RELEASE_DIR/$ARTIFACT_NAME"
MANIFEST_FINAL="$RELEASE_DIR/$MANIFEST_NAME"
SIGNATURE_FINAL="$RELEASE_DIR/$SIGNATURE_NAME"
for destination in "$ARTIFACT_FINAL" "$MANIFEST_FINAL" "$SIGNATURE_FINAL"; do
    if [ -e "$destination" ]; then
        echo "Erro: artefato já existe; nada será sobrescrito: $destination" >&2
        exit 1
    fi
done
if [ -f "$RELEASE_DIR/SHA256SUMS" ] && {
    grep -Fq "  $ARTIFACT_NAME" "$RELEASE_DIR/SHA256SUMS" ||
    grep -Fq "  $MANIFEST_NAME" "$RELEASE_DIR/SHA256SUMS" ||
    grep -Fq "  $SIGNATURE_NAME" "$RELEASE_DIR/SHA256SUMS";
}; then
    echo "Erro: SHA256SUMS já contém esta release; nada será sobrescrito." >&2
    exit 1
fi

COMMIT="unknown"
SOURCE_TREE_DIRTY="false"
if command -v git >/dev/null 2>&1 && git -C "$PROJECT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    COMMIT="$(git -C "$PROJECT_DIR" rev-parse HEAD)"
    if [ -n "$(git -C "$PROJECT_DIR" status --porcelain --untracked-files=normal)" ]; then
        SOURCE_TREE_DIRTY="true"
    fi
fi
SOURCE_EPOCH="${SOURCE_DATE_EPOCH:-}"
if [ -z "$SOURCE_EPOCH" ] && [ "$COMMIT" != "unknown" ]; then
    SOURCE_EPOCH="$(git -C "$PROJECT_DIR" show -s --format=%ct HEAD)"
fi
if ! [[ "$SOURCE_EPOCH" =~ ^[0-9]+$ ]]; then
    SOURCE_EPOCH="$(date -u +%s)"
fi

"$PYTHON" - "$STAGING_ROOT/RELEASE_INFO.json" "$VERSION" "$HOST_ARCH" \
    "$ARTIFACT_NAME" "$COMMIT" "$SOURCE_EPOCH" "$SOURCE_TREE_DIRTY" <<'PY'
import datetime
import json
import sys
from pathlib import Path

output, version, architecture, artifact, commit, epoch, dirty = sys.argv[1:]
document = {
    "product": "app247-terminal",
    "version": version,
    "architecture": architecture,
    "packaging": "pyinstaller-onedir",
    "artifact": artifact,
    "signatureAlgorithm": "Ed25519",
    "sourceCommit": commit,
    "sourceTreeDirty": dirty == "true",
    "buildTimestampUtc": datetime.datetime.fromtimestamp(
        int(epoch), datetime.timezone.utc
    ).isoformat().replace("+00:00", "Z"),
}
Path(output).write_text(
    json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

ARTIFACT_TEMP="$WORK_DIR/$ARTIFACT_NAME"
MANIFEST_TEMP="$WORK_DIR/$MANIFEST_NAME"
SIGNATURE_TEMP="$WORK_DIR/$SIGNATURE_NAME"
tar --sort=name --format=posix \
    --pax-option=delete=atime,delete=ctime \
    --mtime="@$SOURCE_EPOCH" --owner=0 --group=0 --numeric-owner \
    -czf "$ARTIFACT_TEMP" -C "$WORK_DIR/staging" "$ROOT_NAME"

SIGN_ARGUMENTS=(
    "$ARTIFACT_TEMP"
    --version "$VERSION"
    --architecture "$HOST_ARCH"
    --private-key "$PRIVATE_KEY"
    --output "$MANIFEST_TEMP"
)
if [ -n "$PASSWORD_FILE" ]; then
    SIGN_ARGUMENTS+=(--password-file "$PASSWORD_FILE")
fi
PYTHON_BIN="$PYTHON" "$PROJECT_DIR/scripts/sign-update-manifest.sh" "${SIGN_ARGUMENTS[@]}"
"$PYTHON" - "$MANIFEST_TEMP" "$SIGNATURE_TEMP" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
Path(sys.argv[2]).write_text(str(manifest["signature"]) + "\n", encoding="ascii")
PY

echo "Verificando assinatura, SHA-256, arquitetura, conteúdo e instalador standalone..."
APP247_UPDATE_PUBLIC_KEY="$PUBLIC_KEY" PYTHON_BIN="$PYTHON" \
    "$PROJECT_DIR/scripts/verify-release.sh" \
    "$ARTIFACT_TEMP" "$MANIFEST_TEMP" "$SIGNATURE_TEMP"

mv "$ARTIFACT_TEMP" "$ARTIFACT_FINAL"
mv "$MANIFEST_TEMP" "$MANIFEST_FINAL"
mv "$SIGNATURE_TEMP" "$SIGNATURE_FINAL"
chmod 0644 "$ARTIFACT_FINAL" "$MANIFEST_FINAL" "$SIGNATURE_FINAL"

CHECKSUM_TEMP="$WORK_DIR/SHA256SUMS"
if [ -f "$RELEASE_DIR/SHA256SUMS" ]; then
    cp "$RELEASE_DIR/SHA256SUMS" "$CHECKSUM_TEMP"
fi
(
    cd "$RELEASE_DIR"
    sha256sum "$ARTIFACT_NAME" "$MANIFEST_NAME" "$SIGNATURE_NAME"
) >> "$CHECKSUM_TEMP"
sort -k2,2 "$CHECKSUM_TEMP" -o "$CHECKSUM_TEMP"
echo "Atualizando índice de checksums: $RELEASE_DIR/SHA256SUMS"
install -m 0644 "$CHECKSUM_TEMP" "$RELEASE_DIR/SHA256SUMS"

PACKAGE_SHA256="$(sha256sum "$ARTIFACT_FINAL" | awk '{print $1}')"
echo "Release criada: $ARTIFACT_FINAL"
echo "Arquitetura: $HOST_ARCH"
echo "SHA-256: $PACKAGE_SHA256"
echo "Assinatura Ed25519: válida"
