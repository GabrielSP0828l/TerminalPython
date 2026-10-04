#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPOSITORY_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
if [ -f "$SCRIPT_DIR/VERSION" ] && [ -d "$SCRIPT_DIR/app" ]; then
    PROJECT_DIR="$SCRIPT_DIR"
    DEFAULT_ARTIFACT_DIR="$SCRIPT_DIR/app"
    DEFAULT_CONFIG_TEMPLATE="$SCRIPT_DIR/terminal.env.production.example"
    DEFAULT_SERVICE_SOURCE="$SCRIPT_DIR/app247-terminal.service"
    DEFAULT_LAUNCHER_SOURCE="$SCRIPT_DIR/app247-terminal-launcher"
    DEFAULT_PUBLIC_KEY_SOURCE="$SCRIPT_DIR/update-signing-public-key.pem"
else
    PROJECT_DIR="$REPOSITORY_DIR"
    DEFAULT_ARTIFACT_DIR="$PROJECT_DIR/dist/app247-terminal"
    DEFAULT_CONFIG_TEMPLATE="$PROJECT_DIR/packaging/terminal.env.production.example"
    DEFAULT_SERVICE_SOURCE="$PROJECT_DIR/packaging/systemd/app247-terminal.service"
    DEFAULT_LAUNCHER_SOURCE="$PROJECT_DIR/packaging/app247-terminal-launcher"
    DEFAULT_PUBLIC_KEY_SOURCE=""
fi

ARTIFACT_DIR="${APP247_ARTIFACT_DIR:-$DEFAULT_ARTIFACT_DIR}"
VERSION="${APP247_INSTALL_VERSION:-}"
if [ -z "$VERSION" ] && [ -f "$SCRIPT_DIR/VERSION" ]; then
    VERSION="$(tr -d '\r\n' < "$SCRIPT_DIR/VERSION")"
fi
INSTALL_ROOT="${APP247_INSTALL_ROOT:-/opt/app247}"
DATA_DIR="${APP247_DATA_DIR:-/var/lib/app247}"
DATABASE_PATH="${APP247_DB_PATH:-$DATA_DIR/terminal.db}"
TERMINAL_CONFIG_PATH="${APP247_TERMINAL_CONFIG_PATH:-$DATA_DIR/terminal.json}"
DEVICE_CREDENTIAL_PATH="${APP247_DEVICE_CREDENTIAL_PATH:-$DATA_DIR/device-credential}"
DISPLAY_ORIENTATION_PATH="${APP247_DISPLAY_ORIENTATION_PATH:-$DATA_DIR/display_orientation}"
LAST_SYNC_PATH="${APP247_LAST_SYNC_PATH:-$DATA_DIR/last_sync.txt}"
CONFIG_DIR="${APP247_CONFIG_DIR:-/etc/app247}"
CONFIG_FILE="$CONFIG_DIR/terminal.env"
CONFIG_TEMPLATE="${APP247_CONFIG_TEMPLATE:-$DEFAULT_CONFIG_TEMPLATE}"
SERVICE_USER="${APP247_SERVICE_USER:-app247}"
SERVICE_GROUP="${APP247_SERVICE_GROUP:-app247}"
SYSTEMD_DIR="${APP247_SYSTEMD_DIR:-/etc/systemd/system}"
SERVICE_NAME="${APP247_SERVICE_NAME:-app247-terminal.service}"
SERVICE_DESTINATION="$SYSTEMD_DIR/$SERVICE_NAME"
SERVICE_SOURCE="${APP247_SERVICE_SOURCE:-$DEFAULT_SERVICE_SOURCE}"
LAUNCHER_SOURCE="${APP247_LAUNCHER_SOURCE:-$DEFAULT_LAUNCHER_SOURCE}"
LAUNCHER_DESTINATION="${APP247_LAUNCHER_DESTINATION:-/usr/local/bin/app247-terminal-launcher}"
MANAGE_SYSTEMD="${APP247_MANAGE_SYSTEMD:-true}"
UPDATE_PUBLIC_KEY_SOURCE="${APP247_UPDATE_PUBLIC_KEY_SOURCE:-$DEFAULT_PUBLIC_KEY_SOURCE}"
ACTIVATE="false"

for argument in "$@"; do
    case "$argument" in
        --activate) ACTIVATE="true" ;;
        *) echo "Erro: argumento desconhecido: $argument" >&2; exit 1 ;;
    esac
done
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]]; then
    echo "Erro: versão ausente/inválida em VERSION ou APP247_INSTALL_VERSION." >&2
    exit 1
fi
if [ ! -x "$ARTIFACT_DIR/app247-terminal" ]; then
    echo "Erro: artefato onedir inválido em $ARTIFACT_DIR" >&2
    exit 1
fi
if [ ! -f "$CONFIG_TEMPLATE" ]; then
    echo "Erro: template de configuração ausente: $CONFIG_TEMPLATE" >&2
    exit 1
fi
if [ ! -f "$SERVICE_SOURCE" ]; then
    echo "Erro: unidade systemd de origem ausente." >&2
    exit 1
fi
if [ ! -x "$LAUNCHER_SOURCE" ]; then
    echo "Erro: launcher gráfico ausente ou sem permissão de execução." >&2
    exit 1
fi
if [ "$MANAGE_SYSTEMD" != "true" ] && [ "$MANAGE_SYSTEMD" != "false" ]; then
    echo "Erro: APP247_MANAGE_SYSTEMD deve ser true ou false." >&2
    exit 1
fi
if [ "$ACTIVATE" = "true" ] && [ "$MANAGE_SYSTEMD" = "true" ] && [ "$(id -u)" -ne 0 ]; then
    echo "Erro: ativação com gerenciamento do systemd exige execução como root." >&2
    exit 1
fi
PUBLIC_KEY_DESTINATION="$CONFIG_DIR/update-signing-public-key.pem"
INSTALL_PUBLIC_KEY="false"
if [ -n "$UPDATE_PUBLIC_KEY_SOURCE" ]; then
    if [ ! -f "$UPDATE_PUBLIC_KEY_SOURCE" ] || [ -L "$UPDATE_PUBLIC_KEY_SOURCE" ]; then
        echo "Erro: APP247_UPDATE_PUBLIC_KEY_SOURCE deve ser um arquivo regular." >&2
        exit 1
    fi
    if [ -e "$PUBLIC_KEY_DESTINATION" ]; then
        if [ ! -f "$PUBLIC_KEY_DESTINATION" ] || [ -L "$PUBLIC_KEY_DESTINATION" ]; then
            echo "Erro: chave pública instalada não é um arquivo regular." >&2
            exit 1
        fi
        if ! cmp -s "$UPDATE_PUBLIC_KEY_SOURCE" "$PUBLIC_KEY_DESTINATION"; then
            echo "Erro: chave pública já existe e diverge; rotação exige procedimento explícito." >&2
            exit 1
        fi
        echo "Chave pública confiável já instalada e idêntica."
    else
        INSTALL_PUBLIC_KEY="true"
    fi
fi

RELEASE_DIR="$INSTALL_ROOT/releases/$VERSION"
RELEASE_ALREADY_INSTALLED="false"
if [ -e "$RELEASE_DIR" ]; then
    if [ ! -d "$RELEASE_DIR" ] || [ -L "$RELEASE_DIR" ] || [ ! -x "$RELEASE_DIR/app247-terminal" ]; then
        echo "Erro: release existente é parcial ou inválida: $RELEASE_DIR" >&2
        exit 1
    fi
    if ! diff -qr "$ARTIFACT_DIR" "$RELEASE_DIR" >/dev/null; then
        echo "Erro: release existente diverge do pacote; nada foi sobrescrito: $RELEASE_DIR" >&2
        exit 1
    fi
    RELEASE_ALREADY_INSTALLED="true"
    echo "Release $VERSION já instalada e íntegra; nenhuma cópia foi refeita."
fi

if [ "$(id -u)" -eq 0 ]; then
    if ! getent group "$SERVICE_GROUP" >/dev/null 2>&1; then
        if ! command -v groupadd >/dev/null 2>&1; then
            echo "Erro: grupo $SERVICE_GROUP ausente e groupadd indisponível." >&2
            exit 1
        fi
        groupadd --system "$SERVICE_GROUP"
        echo "Grupo de serviço criado: $SERVICE_GROUP"
    fi
    if ! id "$SERVICE_USER" >/dev/null 2>&1; then
        if ! command -v useradd >/dev/null 2>&1; then
            echo "Erro: usuário $SERVICE_USER ausente e useradd indisponível." >&2
            exit 1
        fi
        useradd --system --gid "$SERVICE_GROUP" --home-dir "$DATA_DIR" \
            --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
        echo "Usuário de serviço criado: $SERVICE_USER"
    fi
fi

install -d -m 0755 "$INSTALL_ROOT/releases"
install -d -m 0750 "$DATA_DIR" "$CONFIG_DIR"
if [ "$RELEASE_ALREADY_INSTALLED" = "false" ]; then
    install -d -m 0755 "$RELEASE_DIR"
    cp -a "$ARTIFACT_DIR/." "$RELEASE_DIR/"
    chmod -R go-w "$RELEASE_DIR"
    if [ "$(id -u)" -eq 0 ]; then
        chown -R root:root "$RELEASE_DIR"
    fi
fi

if [ ! -e "$CONFIG_FILE" ]; then
    CONFIG_TEMP="$(mktemp)"
    trap 'rm -f "$CONFIG_TEMP"' EXIT
    awk \
        -v data_dir="$DATA_DIR" \
        -v database_path="$DATABASE_PATH" \
        -v terminal_config_path="$TERMINAL_CONFIG_PATH" \
        -v credential_path="$DEVICE_CREDENTIAL_PATH" \
        -v public_key_path="$PUBLIC_KEY_DESTINATION" \
        -v orientation_path="$DISPLAY_ORIENTATION_PATH" \
        -v last_sync_path="$LAST_SYNC_PATH" '
        /^APP247_DATA_DIR=/ { print "APP247_DATA_DIR=" data_dir; next }
        /^APP247_DB_PATH=/ { print "APP247_DB_PATH=" database_path; next }
        /^APP247_TERMINAL_CONFIG_PATH=/ { print "APP247_TERMINAL_CONFIG_PATH=" terminal_config_path; next }
        /^APP247_DEVICE_CREDENTIAL_PATH=/ { print "APP247_DEVICE_CREDENTIAL_PATH=" credential_path; next }
        /^APP247_UPDATE_PUBLIC_KEY_PATH=/ { print "APP247_UPDATE_PUBLIC_KEY_PATH=" public_key_path; next }
        /^APP247_DISPLAY_ORIENTATION_PATH=/ { print "APP247_DISPLAY_ORIENTATION_PATH=" orientation_path; next }
        /^APP247_LAST_SYNC_PATH=/ { print "APP247_LAST_SYNC_PATH=" last_sync_path; next }
        { print }
    ' "$CONFIG_TEMPLATE" > "$CONFIG_TEMP"
    install -m 0640 "$CONFIG_TEMP" "$CONFIG_FILE"
    rm -f "$CONFIG_TEMP"
    trap - EXIT
fi
if [ "$INSTALL_PUBLIC_KEY" = "true" ]; then
    install -m 0644 "$UPDATE_PUBLIC_KEY_SOURCE" "$PUBLIC_KEY_DESTINATION"
fi
if [ "$(id -u)" -eq 0 ]; then
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$DATA_DIR"
    chmod 0750 "$DATA_DIR"
    find "$DATA_DIR" -type d -exec chmod o-rwx,g-w {} +
    find "$DATA_DIR" -type f -exec chmod o-rwx,g-wx {} +
    for sensitive_file in "$TERMINAL_CONFIG_PATH" "$DEVICE_CREDENTIAL_PATH"; do
        if [ -f "$sensitive_file" ] && [ ! -L "$sensitive_file" ]; then
            chmod 0600 "$sensitive_file"
        fi
    done
    chown "root:$SERVICE_GROUP" "$CONFIG_DIR" "$CONFIG_FILE"
    chmod 0750 "$CONFIG_DIR"
    chmod 0640 "$CONFIG_FILE"
    if [ -f "$PUBLIC_KEY_DESTINATION" ]; then
        chown root:root "$CONFIG_DIR/update-signing-public-key.pem"
        chmod 0644 "$CONFIG_DIR/update-signing-public-key.pem"
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

    restore_previous_release() {
        if [ -n "$PREVIOUS" ]; then
            ROLLBACK_LINK="$INSTALL_ROOT/.rollback-$VERSION-$$"
            ln -s "$PREVIOUS" "$ROLLBACK_LINK"
            mv -Tf "$ROLLBACK_LINK" "$INSTALL_ROOT/current"
            echo "Release anterior restaurada: $PREVIOUS" >&2
        else
            rm -f "$INSTALL_ROOT/current"
            echo "Ativação inicial desfeita." >&2
        fi
    }

    CHECK_COMMAND=(env
        "APP247_CONFIG_FILE=$CONFIG_FILE"
        "APP247_CURRENT_LINK=$INSTALL_ROOT/current"
        "$RELEASE_DIR/app247-terminal" --check)
    set +e
    if [ "$(id -u)" -eq 0 ]; then
        runuser -u "$SERVICE_USER" -- "${CHECK_COMMAND[@]}"
    else
        "${CHECK_COMMAND[@]}"
    fi
    CHECK_STATUS=$?
    set -e
    if [ "$CHECK_STATUS" -ne 0 ]; then
        echo "Erro: diagnóstico da nova release falhou." >&2
        restore_previous_release
        exit "$CHECK_STATUS"
    fi

    install -d -m 0755 "$SYSTEMD_DIR" "$(dirname -- "$LAUNCHER_DESTINATION")"
    install -m 0755 "$LAUNCHER_SOURCE" "$LAUNCHER_DESTINATION"
    UNIT_TEMP="$(mktemp)"
    trap 'rm -f "$UNIT_TEMP"' EXIT
    sed \
        -e "s|^User=.*|User=$SERVICE_USER|" \
        -e "s|^Group=.*|Group=$SERVICE_GROUP|" \
        -e "s|^EnvironmentFile=.*|EnvironmentFile=-$CONFIG_FILE|" \
        -e "s|^WorkingDirectory=.*|WorkingDirectory=$DATA_DIR|" \
        -e "s|^ExecStartPre=.*|ExecStartPre=-$INSTALL_ROOT/current/app247-terminal --apply-display|" \
        -e "s|^ExecStart=.*|ExecStart=$INSTALL_ROOT/current/app247-terminal|" \
        "$SERVICE_SOURCE" > "$UNIT_TEMP"
    install -m 0644 "$UNIT_TEMP" "$SERVICE_DESTINATION"
    rm -f "$UNIT_TEMP"
    trap - EXIT

    if [ "$MANAGE_SYSTEMD" = "true" ]; then
        SYSTEMD_STATUS=0
        systemctl daemon-reload || SYSTEMD_STATUS=$?
        if [ "$SYSTEMD_STATUS" -eq 0 ]; then
            systemctl enable "$SERVICE_NAME" || SYSTEMD_STATUS=$?
        fi
        if [ "$SYSTEMD_STATUS" -eq 0 ]; then
            if systemctl is-active --quiet "$SERVICE_NAME"; then
                systemctl restart "$SERVICE_NAME" || SYSTEMD_STATUS=$?
            else
                systemctl start "$SERVICE_NAME" || SYSTEMD_STATUS=$?
            fi
        fi
        if [ "$SYSTEMD_STATUS" -ne 0 ] || ! systemctl is-active --quiet "$SERVICE_NAME"; then
            echo "Erro: serviço não permaneceu ativo: $SERVICE_NAME" >&2
            systemctl status "$SERVICE_NAME" --no-pager >&2 || true
            restore_previous_release
            if [ -n "$PREVIOUS" ]; then
                systemctl restart "$SERVICE_NAME" || true
            else
                systemctl disable --now "$SERVICE_NAME" || true
            fi
            exit 1
        fi
        echo "Serviço instalado, habilitado e ativo: $SERVICE_NAME"
    else
        echo "Unidade instalada sem controlar o systemd: $SERVICE_DESTINATION"
    fi
    echo "Release ativada e diagnóstico concluído: $RELEASE_DIR"
else
    echo "Release preparada. Edite $CONFIG_FILE e execute novamente com --activate."
fi
