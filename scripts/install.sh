#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
ARTIFACT_DIR="${APP247_ARTIFACT_DIR:-$PROJECT_DIR/dist/app247-terminal}"
VERSION="${APP247_INSTALL_VERSION:-}"
INSTALL_ROOT="${APP247_INSTALL_ROOT:-/opt/app247}"
DATA_DIR="${APP247_DATA_DIR:-/var/lib/app247}"
CONFIG_DIR="${APP247_CONFIG_DIR:-/etc/app247}"
SERVICE_USER="${APP247_SERVICE_USER:-app247}"
SERVICE_GROUP="${APP247_SERVICE_GROUP:-app247}"
UPDATE_PUBLIC_KEY_SOURCE="${APP247_UPDATE_PUBLIC_KEY_SOURCE:-}"
ACTIVATE="false"

if [ "${1:-}" = "--activate" ]; then
    ACTIVATE="true"
fi
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]]; then
    echo "Erro: informe APP247_INSTALL_VERSION (ex.: 1.0.0)." >&2
    exit 1
fi
if [ ! -x "$ARTIFACT_DIR/app247-terminal" ]; then
    echo "Erro: artefato onedir inválido em $ARTIFACT_DIR" >&2
    exit 1
fi
PUBLIC_KEY_DESTINATION="$CONFIG_DIR/update-signing-public-key.pem"
if [ -n "$UPDATE_PUBLIC_KEY_SOURCE" ]; then
    if [ ! -f "$UPDATE_PUBLIC_KEY_SOURCE" ] || [ -L "$UPDATE_PUBLIC_KEY_SOURCE" ]; then
        echo "Erro: APP247_UPDATE_PUBLIC_KEY_SOURCE deve ser um arquivo regular." >&2
        exit 1
    fi
    if [ -e "$PUBLIC_KEY_DESTINATION" ]; then
        echo "Erro: chave pública já existe; rotação exige procedimento explícito." >&2
        exit 1
    fi
fi

RELEASE_DIR="$INSTALL_ROOT/releases/$VERSION"
if [ -e "$RELEASE_DIR" ]; then
    echo "Erro: a release já existe; nada foi sobrescrito: $RELEASE_DIR" >&2
    exit 1
fi

if [ "$(id -u)" -eq 0 ]; then
    if ! id "$SERVICE_USER" >/dev/null 2>&1 || ! getent group "$SERVICE_GROUP" >/dev/null 2>&1; then
        echo "Erro: crie o usuário/grupo dedicado ou informe APP247_SERVICE_USER/GROUP." >&2
        exit 1
    fi
fi

install -d -m 0755 "$INSTALL_ROOT/releases"
install -d -m 0750 "$DATA_DIR" "$CONFIG_DIR"
install -d -m 0755 "$RELEASE_DIR"
cp -a "$ARTIFACT_DIR/." "$RELEASE_DIR/"

if [ ! -e "$CONFIG_DIR/terminal.env" ]; then
    install -m 0640 "$PROJECT_DIR/.env.example" "$CONFIG_DIR/terminal.env"
fi
if [ -n "$UPDATE_PUBLIC_KEY_SOURCE" ]; then
    install -m 0644 "$UPDATE_PUBLIC_KEY_SOURCE" "$PUBLIC_KEY_DESTINATION"
fi
if [ "$(id -u)" -eq 0 ]; then
    chown "$SERVICE_USER:$SERVICE_GROUP" "$DATA_DIR"
    chown "root:$SERVICE_GROUP" "$CONFIG_DIR" "$CONFIG_DIR/terminal.env"
    if [ -n "$UPDATE_PUBLIC_KEY_SOURCE" ]; then
        chown root:root "$CONFIG_DIR/update-signing-public-key.pem"
    fi
fi

echo "Release instalada sem apagar dados/configurações: $RELEASE_DIR"
if [ "$ACTIVATE" = "true" ]; then
    PREVIOUS=""
    if [ -L "$INSTALL_ROOT/current" ]; then
        PREVIOUS="$(readlink -f "$INSTALL_ROOT/current")"
        printf '%s\n' "$PREVIOUS" > "$DATA_DIR/previous-release"
    elif [ -e "$INSTALL_ROOT/current" ]; then
        echo "Erro: $INSTALL_ROOT/current existe e não é symlink." >&2
        exit 1
    fi
    TEMP_LINK="$INSTALL_ROOT/.current-$VERSION-$$"
    ln -s "releases/$VERSION" "$TEMP_LINK"
    mv -Tf "$TEMP_LINK" "$INSTALL_ROOT/current"
    echo "Release ativada. Reinício/health-check do serviço continua sendo etapa manual."
else
    echo "Release apenas preparada. Use --activate conscientemente após validação."
fi
