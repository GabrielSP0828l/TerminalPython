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
# Usado somente para retirar com segurança a unit legada de sistema. A GUI é
# instalada como unit do usuário gráfico em USER_SYSTEMD_DIR.
SERVICE_DESTINATION="$SYSTEMD_DIR/$SERVICE_NAME"
SERVICE_SOURCE="${APP247_SERVICE_SOURCE:-$DEFAULT_SERVICE_SOURCE}"
LAUNCHER_SOURCE="${APP247_LAUNCHER_SOURCE:-$DEFAULT_LAUNCHER_SOURCE}"
LAUNCHER_DESTINATION="${APP247_LAUNCHER_DESTINATION:-/usr/local/bin/app247-terminal-launcher}"
MANAGE_SYSTEMD="${APP247_MANAGE_SYSTEMD:-true}"
INSTALL_DESKTOP_INTEGRATION="${APP247_INSTALL_DESKTOP_INTEGRATION:-true}"
DESKTOP_USER="${APP247_DESKTOP_USER:-}"
DESKTOP_HOME="${APP247_DESKTOP_HOME:-}"
DESKTOP_DIR="${APP247_DESKTOP_DIR:-}"
AUTOSTART_DIR="${APP247_AUTOSTART_DIR:-}"
USER_SYSTEMD_DIR="${APP247_USER_SYSTEMD_DIR:-}"
USER_SERVICE_DESTINATION=""
DESKTOP_UID=""
USER_RUNTIME_DIR=""
GROUP_MEMBERSHIP_CHANGED="false"
CURRENT_SESSION_ACCESS_READY="true"
UPDATE_PUBLIC_KEY_SOURCE="${APP247_UPDATE_PUBLIC_KEY_SOURCE:-$DEFAULT_PUBLIC_KEY_SOURCE}"
ACTIVATE="false"
# Decisão operacional: economia de energia do Wi-Fi desligada no Terminal. A
# política global vale também para redes configuradas depois pela tela Wi-Fi.
WIFI_POWERSAVE_POLICY="${APP247_WIFI_POWERSAVE:-disable}"
NM_CONF_DIR="${APP247_NM_CONF_DIR:-/etc/NetworkManager/conf.d}"
# O ícone fica fora de /opt/app247/releases para o atalho continuar válido após
# rollback ou limpeza de releases antigas.
ICON_SOURCE="${APP247_ICON_SOURCE:-$ARTIFACT_DIR/_internal/assets/images/logo.png}"
ICON_DESTINATION="${APP247_ICON_DESTINATION:-/usr/local/share/pixmaps/app247-terminal.png}"
DESKTOP_ICON="computer"

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
if [ "$INSTALL_DESKTOP_INTEGRATION" != "true" ] && [ "$INSTALL_DESKTOP_INTEGRATION" != "false" ]; then
    echo "Erro: APP247_INSTALL_DESKTOP_INTEGRATION deve ser true ou false." >&2
    exit 1
fi
if [[ ! "$SERVICE_NAME" =~ ^[A-Za-z0-9@._-]+\.service$ ]]; then
    echo "Erro: APP247_SERVICE_NAME inválido." >&2
    exit 1
fi
if [ "$ACTIVATE" = "true" ] && [ "$MANAGE_SYSTEMD" = "true" ] && [ "$(id -u)" -ne 0 ]; then
    echo "Erro: ativação com gerenciamento do systemd exige execução como root." >&2
    exit 1
fi

detect_desktop_user() {
    local session_id active remote session_type session_user detected_user=""

    if [ -n "$DESKTOP_USER" ]; then
        printf '%s\n' "$DESKTOP_USER"
        return 0
    fi
    if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
        printf '%s\n' "$SUDO_USER"
        return 0
    fi
    if ! command -v loginctl >/dev/null 2>&1; then
        return 1
    fi

    while IFS= read -r session_id; do
        [ -n "$session_id" ] || continue
        active="$(loginctl show-session "$session_id" -p Active --value 2>/dev/null || true)"
        remote="$(loginctl show-session "$session_id" -p Remote --value 2>/dev/null || true)"
        session_type="$(loginctl show-session "$session_id" -p Type --value 2>/dev/null || true)"
        session_user="$(loginctl show-session "$session_id" -p Name --value 2>/dev/null || true)"
        if [ "$active" != "yes" ] || [ "$remote" = "yes" ]; then
            continue
        fi
        if [ "$session_type" != "wayland" ] && [ "$session_type" != "x11" ]; then
            continue
        fi
        if [ -z "$session_user" ] || [ "$session_user" = "root" ]; then
            continue
        fi
        if [ -n "$detected_user" ] && [ "$detected_user" != "$session_user" ]; then
            return 1
        fi
        detected_user="$session_user"
    done < <(loginctl list-sessions --no-legend 2>/dev/null | awk '{print $1}')

    [ -n "$detected_user" ] || return 1
    printf '%s\n' "$detected_user"
}

resolve_desktop_layout() {
    local passwd_entry detected_home xdg_desktop="" canonical_home canonical_path

    if ! DESKTOP_USER="$(detect_desktop_user)"; then
        echo "Erro: usuário gráfico não detectado. Use sudo a partir da sessão gráfica ou defina APP247_DESKTOP_USER para instalar a unit de usuário." >&2
        return 1
    fi
    if ! id "$DESKTOP_USER" >/dev/null 2>&1 || [ "$DESKTOP_USER" = "root" ]; then
        echo "Erro: usuário gráfico inválido: $DESKTOP_USER" >&2
        return 1
    fi

    if [ -z "$DESKTOP_HOME" ]; then
        passwd_entry="$(getent passwd "$DESKTOP_USER" 2>/dev/null || true)"
        detected_home="$(printf '%s' "$passwd_entry" | awk -F: '{print $6}')"
        DESKTOP_HOME="$detected_home"
    fi
    if [ -z "$DESKTOP_HOME" ] || [[ "$DESKTOP_HOME" != /* ]] || [ "$DESKTOP_HOME" = "/" ] || [ ! -d "$DESKTOP_HOME" ]; then
        echo "Erro: diretório home inválido para $DESKTOP_USER: ${DESKTOP_HOME:-ausente}" >&2
        return 1
    fi

    if [ -z "$DESKTOP_DIR" ] && command -v xdg-user-dir >/dev/null 2>&1; then
        if [ "$(id -u)" -eq 0 ]; then
            xdg_desktop="$(runuser -u "$DESKTOP_USER" -- env HOME="$DESKTOP_HOME" xdg-user-dir DESKTOP 2>/dev/null || true)"
        elif [ "$(id -un)" = "$DESKTOP_USER" ]; then
            xdg_desktop="$(HOME="$DESKTOP_HOME" xdg-user-dir DESKTOP 2>/dev/null || true)"
        fi
    fi
    if [ -z "$DESKTOP_DIR" ]; then
        if [ -n "$xdg_desktop" ] && [ "$xdg_desktop" != "$DESKTOP_HOME" ]; then
            DESKTOP_DIR="$xdg_desktop"
        else
            DESKTOP_DIR="$DESKTOP_HOME/Desktop"
        fi
    fi
    canonical_home="$(realpath -m -- "$DESKTOP_HOME")"
    DESKTOP_HOME="$canonical_home"
    if [ -z "$AUTOSTART_DIR" ]; then
        AUTOSTART_DIR="$DESKTOP_HOME/.config/autostart"
    fi
    if [ -z "$USER_SYSTEMD_DIR" ]; then
        USER_SYSTEMD_DIR="$DESKTOP_HOME/.config/systemd/user"
    fi
    for desktop_path in "$DESKTOP_DIR" "$AUTOSTART_DIR" "$USER_SYSTEMD_DIR"; do
        canonical_path="$(realpath -m -- "$desktop_path")"
        if [[ "$canonical_path" != "$canonical_home"/* ]] || [[ "$desktop_path" == *$'\n'* ]]; then
            echo "Erro: destino gráfico fora da home de $DESKTOP_USER: $desktop_path" >&2
            return 1
        fi
    done
    DESKTOP_DIR="$(realpath -m -- "$DESKTOP_DIR")"
    AUTOSTART_DIR="$(realpath -m -- "$AUTOSTART_DIR")"
    USER_SYSTEMD_DIR="$(realpath -m -- "$USER_SYSTEMD_DIR")"
    USER_SERVICE_DESTINATION="$USER_SYSTEMD_DIR/$SERVICE_NAME"
    DESKTOP_UID="$(id -u "$DESKTOP_USER")"
    USER_RUNTIME_DIR="/run/user/$DESKTOP_UID"
    if [[ "$LAUNCHER_DESTINATION" == *$'\n'* ]] || [[ "$LAUNCHER_DESTINATION" == *'"'* ]]; then
        echo "Erro: path do launcher não pode ser representado com segurança no arquivo .desktop." >&2
        return 1
    fi
}

ensure_desktop_directory() {
    local directory="$1" owner_uid

    if [ -e "$directory" ]; then
        if [ ! -d "$directory" ] || [ -L "$directory" ]; then
            echo "Erro: destino gráfico não é um diretório regular: $directory" >&2
            return 1
        fi
        owner_uid="$(stat -c '%U' "$directory")"
        if [ "$owner_uid" != "$DESKTOP_USER" ] && [ "$(id -u)" -eq 0 ]; then
            echo "Erro: destino gráfico não pertence a $DESKTOP_USER: $directory" >&2
            return 1
        fi
        return 0
    fi

    if [ "$(id -u)" -eq 0 ]; then
        install -d -o "$DESKTOP_USER" -g "$(id -gn "$DESKTOP_USER")" -m 0755 "$directory"
    else
        install -d -m 0755 "$directory"
    fi
}

install_desktop_icon() {
    DESKTOP_ICON="computer"
    if [ ! -f "$ICON_SOURCE" ] || [ -L "$ICON_SOURCE" ]; then
        echo "Aviso: logo ausente na release ($ICON_SOURCE); atalho usa ícone genérico." >&2
        return 0
    fi
    if [[ "$ICON_DESTINATION" == *$'\n'* ]] || [[ "$ICON_DESTINATION" == *' '* ]]; then
        echo "Aviso: destino do ícone inválido para .desktop; atalho usa ícone genérico." >&2
        return 0
    fi
    if [ -L "$ICON_DESTINATION" ] ||
       ! install -d -m 0755 "$(dirname -- "$ICON_DESTINATION")" ||
       ! install -m 0644 "$ICON_SOURCE" "$ICON_DESTINATION"; then
        echo "Aviso: não foi possível instalar o logo em $ICON_DESTINATION; atalho usa ícone genérico." >&2
        return 0
    fi
    DESKTOP_ICON="$ICON_DESTINATION"
}

# Atalho criado manualmente nas instalações 1.0.0/1.0.1: chama o launcher direto
# (fora da unit) e não tem ícone. É preservado fora da área de trabalho para não
# haver dois atalhos do Terminal.
retire_legacy_desktop_shortcut() {
    local legacy="$DESKTOP_DIR/App247 Terminal.desktop" backup_dir backup

    [ -f "$legacy" ] && [ ! -L "$legacy" ] || return 0
    grep -qx 'X-App247-Managed=true' "$legacy" && return 0
    if ! grep -qx 'Name=App247 Terminal' "$legacy" ||
       ! grep -qx 'Exec=/usr/local/bin/app247-terminal-launcher' "$legacy"; then
        return 0
    fi
    backup_dir="$DESKTOP_HOME/.local/share/app247/legacy-desktop"
    if ! ensure_desktop_directory "$backup_dir"; then
        echo "Aviso: atalho legado mantido; não foi possível criar $backup_dir." >&2
        return 0
    fi
    backup="$backup_dir/App247 Terminal.desktop.$(date +%Y%m%d%H%M%S)"
    if mv -- "$legacy" "$backup"; then
        echo "Atalho legado substituído; original preservado em $backup"
    else
        echo "Aviso: não foi possível mover o atalho legado $legacy." >&2
    fi
}

install_desktop_integration() {
    local desktop_target="$DESKTOP_DIR/Terminal 24-7.desktop"
    local autostart_target="$AUTOSTART_DIR/app247-terminal.desktop"
    local entry_temp desktop_temp autostart_temp desktop_group

    if ! ensure_desktop_directory "$DESKTOP_DIR" || ! ensure_desktop_directory "$AUTOSTART_DIR"; then
        return 1
    fi
    retire_legacy_desktop_shortcut
    for target in "$desktop_target" "$autostart_target"; do
        if [ -e "$target" ] || [ -L "$target" ]; then
            if [ ! -f "$target" ] || [ -L "$target" ] || ! grep -qx 'X-App247-Managed=true' "$target"; then
                echo "Erro: arquivo gráfico existente não é gerenciado pelo App247: $target" >&2
                return 1
            fi
        fi
    done

    install_desktop_icon
    entry_temp="$(mktemp --suffix=.desktop)" || return 1
    desktop_temp="$desktop_target.tmp.$$"
    autostart_temp="$autostart_target.tmp.$$"
    desktop_group="$(id -gn "$DESKTOP_USER")"
    if ! cat > "$entry_temp" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Terminal 24/7
Comment=Terminal de autoatendimento App247
Exec=/usr/bin/systemctl --user start --no-block $SERVICE_NAME
TryExec=/usr/bin/systemctl
Icon=$DESKTOP_ICON
Terminal=false
StartupNotify=false
Categories=Utility;
X-GNOME-Autostart-enabled=true
X-App247-Managed=true
EOF
    then
        rm -f "$entry_temp"
        return 1
    fi
    if command -v desktop-file-validate >/dev/null 2>&1 && ! desktop-file-validate "$entry_temp"; then
        echo "Erro: entrada gráfica gerada é inválida." >&2
        rm -f "$entry_temp"
        return 1
    fi
    if ! install -m 0755 "$entry_temp" "$desktop_temp" ||
       ! install -m 0644 "$entry_temp" "$autostart_temp"; then
        rm -f "$entry_temp" "$desktop_temp" "$autostart_temp"
        return 1
    fi
    rm -f "$entry_temp"
    if [ "$(id -u)" -eq 0 ]; then
        chown "$DESKTOP_USER:$desktop_group" "$desktop_temp" "$autostart_temp"
    fi
    if ! mv -f "$desktop_temp" "$desktop_target" || ! mv -f "$autostart_temp" "$autostart_target"; then
        rm -f "$desktop_temp" "$autostart_temp"
        return 1
    fi

    if command -v gio >/dev/null 2>&1; then
        if [ "$(id -u)" -eq 0 ]; then
            runuser -u "$DESKTOP_USER" -- gio set "$desktop_target" metadata::trusted true >/dev/null 2>&1 || true
        elif [ "$(id -un)" = "$DESKTOP_USER" ]; then
            gio set "$desktop_target" metadata::trusted true >/dev/null 2>&1 || true
        fi
    fi
    echo "Atalho instalado para $DESKTOP_USER: $desktop_target"
    echo "Inicialização gráfica instalada: $autostart_target"
}

# Units instaladas antes do marcador "# Managed by App247" (releases 1.0.0/1.0.1
# em campo) usavam o launcher antigo, que descartava os argumentos: o
# ExecStartPre --apply-display subia a GUI inteira e terminava em timeout.
is_legacy_app247_unit() {
    local unit="$1"

    grep -qx 'Description=Terminal de autoatendimento App247' "$unit" &&
        grep -Eq '^ExecStart=(/usr/local/bin/app247-terminal-launcher|/opt/app247/current/app247-terminal)$' "$unit"
}

backup_legacy_user_unit() {
    local backup

    backup="$USER_SERVICE_DESTINATION.legacy-$(date +%Y%m%d%H%M%S)"
    if ! cp -p -- "$USER_SERVICE_DESTINATION" "$backup"; then
        echo "Erro: não foi possível preservar a unit legada em $backup" >&2
        return 1
    fi
    echo "Unit legada do App247 preservada em $backup e substituída."
}

warn_user_unit_dropins() {
    local dropin_dir="$USER_SERVICE_DESTINATION.d" dropin

    [ -d "$dropin_dir" ] || return 0
    for dropin in "$dropin_dir"/*.conf; do
        [ -f "$dropin" ] || continue
        if grep -Eq '^ExecStart(Pre)?=' "$dropin"; then
            echo "Aviso: $dropin redefine ExecStart/ExecStartPre e prevalece sobre a unit instalada." >&2
            echo "       Revise-o manualmente; o instalador não altera drop-ins do operador." >&2
        fi
    done
}

install_wifi_powersave_policy() {
    local target="$NM_CONF_DIR/app247-wifi-powersave.conf" temporary

    case "$WIFI_POWERSAVE_POLICY" in
        keep)
            echo "Política de economia de energia do Wi-Fi mantida (APP247_WIFI_POWERSAVE=keep)."
            return 0
            ;;
        disable) ;;
        *)
            echo "Aviso: APP247_WIFI_POWERSAVE inválido ($WIFI_POWERSAVE_POLICY); use disable ou keep." >&2
            return 0
            ;;
    esac
    if [ ! -d "$(dirname -- "$NM_CONF_DIR")" ]; then
        echo "NetworkManager não encontrado; política de Wi-Fi não instalada."
        return 0
    fi
    if [ -L "$target" ] || { [ -e "$target" ] && ! grep -qx '# Managed by App247' "$target"; }; then
        echo "Aviso: $target existe e não é gerenciado pelo App247; não foi alterado." >&2
        return 0
    fi
    if ! install -d -m 0755 "$NM_CONF_DIR" ||
       ! temporary="$(mktemp "$NM_CONF_DIR/.app247-wifi-powersave.XXXXXX")"; then
        echo "Aviso: não foi possível gravar a política de Wi-Fi em $NM_CONF_DIR." >&2
        return 0
    fi
    # 2 = NM_SETTING_WIRELESS_POWERSAVE_DISABLE. Vale para perfis com
    # 802-11-wireless.powersave=default (0); perfis com valor explícito vencem.
    if ! printf '%s\n' \
        '# Managed by App247' \
        '# Economia de energia do Wi-Fi desligada no Terminal (decisão operacional).' \
        '[connection]' \
        'wifi.powersave = 2' > "$temporary" ||
       ! chmod 0644 "$temporary" ||
       ! mv -f -- "$temporary" "$target"; then
        rm -f -- "$temporary"
        echo "Aviso: não foi possível gravar a política de Wi-Fi em $target." >&2
        return 0
    fi
    echo "Política de Wi-Fi instalada: $target (wifi.powersave = 2)."
    echo "Ela vale na próxima ativação da conexão; a rede não foi reiniciada."
}

install_user_service() {
    local unit_temp unit_group

    if ! ensure_desktop_directory "$USER_SYSTEMD_DIR"; then
        return 1
    fi
    if [ -e "$USER_SERVICE_DESTINATION" ] || [ -L "$USER_SERVICE_DESTINATION" ]; then
        if [ ! -f "$USER_SERVICE_DESTINATION" ] || [ -L "$USER_SERVICE_DESTINATION" ]; then
            echo "Erro: unit de usuário existente não é um arquivo regular: $USER_SERVICE_DESTINATION" >&2
            return 1
        fi
        if ! grep -qx '# Managed by App247' "$USER_SERVICE_DESTINATION"; then
            if ! is_legacy_app247_unit "$USER_SERVICE_DESTINATION"; then
                echo "Erro: unit de usuário existente não é gerenciada pelo App247: $USER_SERVICE_DESTINATION" >&2
                return 1
            fi
            backup_legacy_user_unit || return 1
        fi
    fi
    unit_temp="$(mktemp --suffix=.service)" || return 1
    unit_group="$(id -gn "$DESKTOP_USER")"
    if ! sed \
        -e "s|^ExecStartPre=.*|ExecStartPre=-$LAUNCHER_DESTINATION --apply-display|" \
        -e "s|^ExecStart=.*|ExecStart=$LAUNCHER_DESTINATION|" \
        "$SERVICE_SOURCE" > "$unit_temp"; then
        rm -f "$unit_temp"
        return 1
    fi
    if ! install -m 0644 "$unit_temp" "$USER_SERVICE_DESTINATION"; then
        rm -f "$unit_temp"
        return 1
    fi
    rm -f "$unit_temp"
    if [ "$(id -u)" -eq 0 ]; then
        chown "$DESKTOP_USER:$unit_group" "$USER_SERVICE_DESTINATION"
    fi
    warn_user_unit_dropins
}

enable_user_service_offline() {
    local wants_dir wants_link temporary_link unit_group

    wants_dir="$USER_SYSTEMD_DIR/default.target.wants"
    wants_link="$wants_dir/$SERVICE_NAME"
    if ! ensure_desktop_directory "$wants_dir"; then
        return 1
    fi
    if [ -e "$wants_link" ] || [ -L "$wants_link" ]; then
        if [ ! -L "$wants_link" ] || [ "$(readlink "$wants_link")" != "../$SERVICE_NAME" ]; then
            echo "Erro: enable existente da unit não pertence ao App247: $wants_link" >&2
            return 1
        fi
        return 0
    fi
    temporary_link="$wants_dir/.${SERVICE_NAME}.tmp.$$"
    ln -s "../$SERVICE_NAME" "$temporary_link"
    if [ "$(id -u)" -eq 0 ]; then
        unit_group="$(id -gn "$DESKTOP_USER")"
        chown -h "$DESKTOP_USER:$unit_group" "$temporary_link"
    fi
    mv -Tf "$temporary_link" "$wants_link"
}

require_regular_file() {
    local path="$1" label="$2"

    # Nunca aplique chmod/chown de root a um link. O diretório de dados é
    # compartilhado com a sessão gráfica; seguir um link aqui permitiria que
    # um arquivo externo fosse alterado durante uma atualização.
    if [ ! -e "$path" ]; then
        return 0
    fi
    if [ -L "$path" ] || [ ! -f "$path" ]; then
        echo "Erro: $label deve ser um arquivo regular e não pode ser link: $path" >&2
        return 1
    fi
}

reject_data_symlinks() {
    local link_path

    link_path="$(find "$DATA_DIR" -xdev -type l -print -quit)"
    if [ -n "$link_path" ]; then
        echo "Erro: link simbólico não é permitido em $DATA_DIR: $link_path" >&2
        return 1
    fi
}

user_systemd_bus_available() {
    [ -d "$USER_RUNTIME_DIR" ] &&
        [ "$(stat -c '%u' "$USER_RUNTIME_DIR")" = "$DESKTOP_UID" ] &&
        [ -S "$USER_RUNTIME_DIR/bus" ]
}

run_user_systemctl() {
    if [ "$(id -u)" -eq 0 ]; then
        runuser -u "$DESKTOP_USER" -- env \
            HOME="$DESKTOP_HOME" \
            XDG_CONFIG_HOME="$DESKTOP_HOME/.config" \
            XDG_RUNTIME_DIR="$USER_RUNTIME_DIR" \
            DBUS_SESSION_BUS_ADDRESS="unix:path=$USER_RUNTIME_DIR/bus" \
            systemctl --user "$@"
    else
        env \
            HOME="$DESKTOP_HOME" \
            XDG_CONFIG_HOME="$DESKTOP_HOME/.config" \
            XDG_RUNTIME_DIR="$USER_RUNTIME_DIR" \
            DBUS_SESSION_BUS_ADDRESS="unix:path=$USER_RUNTIME_DIR/bus" \
            systemctl --user "$@"
    fi
}

retire_legacy_system_service() {
    if [ "$(id -u)" -ne 0 ] || [ ! -e "$SERVICE_DESTINATION" ]; then
        return 0
    fi
    if [ ! -f "$SERVICE_DESTINATION" ] || [ -L "$SERVICE_DESTINATION" ] ||
       ! grep -qx 'Description=Terminal de autoatendimento App247' "$SERVICE_DESTINATION"; then
        echo "Erro: unit de sistema existente não é reconhecida como legado App247: $SERVICE_DESTINATION" >&2
        return 1
    fi
    systemctl disable --now "$SERVICE_NAME" >/dev/null 2>&1 || true
    rm -f "$SERVICE_DESTINATION"
    systemctl daemon-reload
    echo "Unit de sistema legada removida; a GUI agora usa systemd --user."
}

if [ "$ACTIVATE" = "true" ]; then
    resolve_desktop_layout
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
    if [ "$ACTIVATE" = "true" ] &&
       ! id -nG "$DESKTOP_USER" | tr ' ' '\n' | grep -Fxq "$SERVICE_GROUP"; then
        if ! command -v usermod >/dev/null 2>&1; then
            echo "Erro: usermod indisponível para autorizar o usuário gráfico no grupo $SERVICE_GROUP." >&2
            exit 1
        fi
        usermod -a -G "$SERVICE_GROUP" "$DESKTOP_USER"
        GROUP_MEMBERSHIP_CHANGED="true"
        echo "Usuário gráfico $DESKTOP_USER adicionado ao grupo $SERVICE_GROUP (válido no próximo login)."
    fi
fi

install -d -m 0755 "$INSTALL_ROOT/releases"
install -d -m 2770 "$DATA_DIR"
install -d -m 0750 "$CONFIG_DIR"
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
if ! require_regular_file "$CONFIG_FILE" "terminal.env"; then
    exit 1
fi
if [ "$INSTALL_PUBLIC_KEY" = "true" ]; then
    install -m 0644 "$UPDATE_PUBLIC_KEY_SOURCE" "$PUBLIC_KEY_DESTINATION"
fi
if [ "$(id -u)" -eq 0 ]; then
    # Não toque na credencial durante o prepare de uma atualização: a GUI da
    # release ainda ativa pode estar usando seu arquivo 0600. Ela só é migrada
    # para o usuário gráfico conhecido na ativação.
    if ! reject_data_symlinks ||
       ! require_regular_file "$DEVICE_CREDENTIAL_PATH" "device-credential" ||
       ! require_regular_file "$PUBLIC_KEY_DESTINATION" "chave pública de atualização"; then
        exit 1
    fi
    chown "$SERVICE_USER:$SERVICE_GROUP" "$DATA_DIR"
    find "$DATA_DIR" -mindepth 1 -type d -exec chown "$SERVICE_USER:$SERVICE_GROUP" {} +
    find "$DATA_DIR" -mindepth 1 -type f ! -path "$DEVICE_CREDENTIAL_PATH" \
        -exec chown "$SERVICE_USER:$SERVICE_GROUP" {} +
    find "$DATA_DIR" -type d -exec chmod 2770 {} +
    find "$DATA_DIR" -type f ! -path "$DEVICE_CREDENTIAL_PATH" -exec chmod 0660 {} +
    # A GUI é o processo que consome a credencial. Ela permanece privada (0600)
    # e pertence ao usuário gráfico; nunca se flexibiliza a validação da app.
    if [ -n "$DESKTOP_USER" ] && [ -f "$DEVICE_CREDENTIAL_PATH" ] && [ ! -L "$DEVICE_CREDENTIAL_PATH" ]; then
        chown "$DESKTOP_USER:$SERVICE_GROUP" "$DEVICE_CREDENTIAL_PATH"
        chmod 0600 "$DEVICE_CREDENTIAL_PATH"
    fi
    chown "root:$SERVICE_GROUP" "$CONFIG_DIR" "$CONFIG_FILE"
    chmod 0750 "$CONFIG_DIR"
    chmod 0640 "$CONFIG_FILE"
    if [ -f "$PUBLIC_KEY_DESTINATION" ]; then
        chown root:root "$CONFIG_DIR/update-signing-public-key.pem"
        chmod 0644 "$CONFIG_DIR/update-signing-public-key.pem"
    fi
    # Um systemd --user já em execução mantém os grupos do login original. ACL
    # nominal temporariamente dá ao mesmo usuário gráfico acesso imediato sem
    # tornar configuração ou dados públicos; após relogin, o grupo app247 basta.
    if [ "$ACTIVATE" = "true" ] && [ "$GROUP_MEMBERSHIP_CHANGED" = "true" ]; then
        if command -v setfacl >/dev/null 2>&1; then
            setfacl -m "u:$DESKTOP_USER:rx" "$CONFIG_DIR"
            setfacl -m "u:$DESKTOP_USER:r" "$CONFIG_FILE"
            find "$DATA_DIR" -type d -exec setfacl -m "u:$DESKTOP_USER:rwx,d:u:$DESKTOP_USER:rwx" {} +
        else
            CURRENT_SESSION_ACCESS_READY="false"
            echo "Aviso: setfacl indisponível; faça logout/login ou reinicie antes de iniciar a GUI." >&2
        fi
    fi
fi

echo "Release instalada sem apagar dados/configurações: $RELEASE_DIR"
if [ "$ACTIVATE" = "true" ]; then
    PREVIOUS=""
    if [ -L "$INSTALL_ROOT/current" ]; then
        PREVIOUS="$(readlink -f "$INSTALL_ROOT/current")"
        printf '%s\n' "$PREVIOUS" > "$DATA_DIR/previous-release"
        if [ "$(id -u)" -eq 0 ]; then
            chown "$SERVICE_USER:$SERVICE_GROUP" "$DATA_DIR/previous-release"
            chmod 0660 "$DATA_DIR/previous-release"
        fi
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
        runuser -u "$DESKTOP_USER" -- env \
            HOME="$DESKTOP_HOME" \
            XDG_CONFIG_HOME="$DESKTOP_HOME/.config" \
            "${CHECK_COMMAND[@]}"
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

    install -d -m 0755 "$(dirname -- "$LAUNCHER_DESTINATION")"
    install -m 0755 "$LAUNCHER_SOURCE" "$LAUNCHER_DESTINATION"
    install_wifi_powersave_policy
    if ! install_user_service || ! enable_user_service_offline; then
        echo "Erro: não foi possível instalar/habilitar a unit gráfica do usuário." >&2
        restore_previous_release
        exit 1
    fi
    if [ "$INSTALL_DESKTOP_INTEGRATION" = "true" ] && ! install_desktop_integration; then
        echo "Erro: não foi possível instalar o atalho/autostart gráfico." >&2
        restore_previous_release
        exit 1
    fi

    if [ "$MANAGE_SYSTEMD" = "true" ]; then
        if ! retire_legacy_system_service; then
            restore_previous_release
            exit 1
        fi
        if user_systemd_bus_available && [ "$CURRENT_SESSION_ACCESS_READY" = "true" ]; then
            SYSTEMD_STATUS=0
            run_user_systemctl daemon-reload || SYSTEMD_STATUS=$?
            if [ "$SYSTEMD_STATUS" -eq 0 ]; then
                if run_user_systemctl is-active --quiet "$SERVICE_NAME"; then
                    run_user_systemctl restart "$SERVICE_NAME" || SYSTEMD_STATUS=$?
                else
                    run_user_systemctl start "$SERVICE_NAME" || SYSTEMD_STATUS=$?
                fi
            fi
            if [ "$SYSTEMD_STATUS" -ne 0 ]; then
                echo "Erro: não foi possível iniciar a unit gráfica: $SERVICE_NAME" >&2
                run_user_systemctl status "$SERVICE_NAME" --no-pager >&2 || true
                restore_previous_release
                if [ -n "$PREVIOUS" ]; then
                    run_user_systemctl restart "$SERVICE_NAME" || true
                fi
                exit 1
            fi
            echo "Unit gráfica do usuário instalada e iniciada: $USER_SERVICE_DESTINATION"
        else
            echo "Unit gráfica instalada e habilitada para $DESKTOP_USER; ela iniciará no próximo login gráfico."
        fi
    else
        echo "Unit gráfica instalada sem operar systemd --user: $USER_SERVICE_DESTINATION"
    fi
    echo "Release ativada e diagnóstico concluído: $RELEASE_DIR"
else
    echo "Release preparada. Edite $CONFIG_FILE e execute novamente com --activate."
fi
