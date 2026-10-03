"""Configuração central do Terminal App247.

O código da release é imutável. Todo estado mutável é resolvido a partir de
``APP247_DATA_DIR``/``APP247_DB_PATH`` e, em produção, deve ficar fora de
``/opt/app247/releases``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from app247_terminal.version import APP_VERSION as PACKAGE_VERSION


def _source_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _bundle_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    return Path(frozen_root).resolve() if frozen_root else _source_root()


SOURCE_ROOT = _source_root()
BUNDLE_ROOT = _bundle_root()
# Alias legado mantido durante a migração interna. Não deve guardar estado.
PROJECT_ROOT = SOURCE_ROOT

# Em desenvolvimento, o .env pertence ao repositório. Em uma instalação ele é
# fornecido pelo systemd via EnvironmentFile=/etc/app247/terminal.env.
load_dotenv(SOURCE_ROOT / ".env")


def _env(primary: str, legacy: str | None = None, default: str = "") -> str:
    value = os.getenv(primary)
    if value is None and legacy:
        value = os.getenv(legacy)
    return default if value is None else value


APP_ENV = _env("APP247_ENV", "APP_ENV", "development").strip().lower()
if APP_ENV not in {"development", "production", "test"}:
    APP_ENV = "development"
IS_PRODUCTION = APP_ENV == "production"

API_URL = _env("APP247_API_URL", "API_URL").rstrip("/")
WS_URL = _env("APP247_WS_URL", "WS_URL").rstrip("/")
APP_VERSION = _env("APP247_VERSION", "APP_VERSION", PACKAGE_VERSION).strip()

default_data_dir = Path("/var/lib/app247") if IS_PRODUCTION else SOURCE_ROOT / "data"
DATA_DIR = Path(_env("APP247_DATA_DIR", default=str(default_data_dir))).expanduser()
DATABASE_PATH = Path(
    _env("APP247_DB_PATH", default=str(DATA_DIR / "terminal.db"))
).expanduser()
TERMINAL_CONFIG_PATH = Path(
    _env("APP247_TERMINAL_CONFIG_PATH", default=str(DATA_DIR / "terminal.json"))
).expanduser()
DEVICE_CREDENTIAL_PATH = Path(
    _env("APP247_DEVICE_CREDENTIAL_PATH", "DEVICE_CREDENTIAL_PATH",
         str(DATA_DIR / "device-credential"))
).expanduser()
UPDATE_PUBLIC_KEY_PATH = Path(
    _env(
        "APP247_UPDATE_PUBLIC_KEY_PATH",
        default="/etc/app247/update-signing-public-key.pem",
    )
).expanduser()
DISPLAY_ORIENTATION_PATH = Path(
    _env("APP247_DISPLAY_ORIENTATION_PATH",
         default=str(DATA_DIR / "display_orientation"))
).expanduser()
LAST_SYNC_PATH = Path(
    _env("APP247_LAST_SYNC_PATH", default=str(DATA_DIR / "last_sync.txt"))
).expanduser()
RESET_MARKER_PATH = DATA_DIR / "factory-reset.pending"
RESET_COMPLETION_MARKER_PATH = DATA_DIR / "factory-reset-completion.pending"
RESET_BACKUP_DIR = DATA_DIR / "reset-backups"
RESET_STAGING_DIR = DATA_DIR / "reset-staging"

TERMINAL_ADMIN_PASSWORD = _env(
    "APP247_TERMINAL_ADMIN_PASSWORD", "TERMINAL_ADMIN_PASSWORD"
)
TERMINAL_INTERNAL_TOKEN = _env(
    "APP247_TERMINAL_INTERNAL_TOKEN", "TERMINAL_INTERNAL_TOKEN"
)
LEGACY_TERMINAL_AUTH_ENABLED = _env(
    "APP247_LEGACY_TERMINAL_AUTH_ENABLED", "LEGACY_TERMINAL_AUTH_ENABLED", "false"
).strip().lower() == "true"


def _int_setting(name: str, legacy: str, default: int, minimum: int) -> int:
    try:
        return max(minimum, int(_env(name, legacy, str(default))))
    except (TypeError, ValueError):
        return default


def _float_setting(name: str, legacy: str, default: float, minimum: float) -> float:
    try:
        return max(minimum, float(_env(name, legacy, str(default))))
    except (TypeError, ValueError):
        return default


PRODUCT_SYNC_INTERVAL_SECONDS = _int_setting(
    "APP247_PRODUCT_SYNC_INTERVAL_SECONDS", "PRODUCT_SYNC_INTERVAL_SECONDS", 300, 60
)
HEARTBEAT_INTERVAL_SECONDS = _int_setting(
    "APP247_HEARTBEAT_INTERVAL_SECONDS", "HEARTBEAT_INTERVAL_SECONDS", 10, 5
)
HEARTBEAT_RETRY_SECONDS = _int_setting(
    "APP247_HEARTBEAT_RETRY_SECONDS", "HEARTBEAT_RETRY_SECONDS", 5, 1
)
HEARTBEAT_ACK_TIMEOUT_SECONDS = _float_setting(
    "APP247_HEARTBEAT_ACK_TIMEOUT_SECONDS", "HEARTBEAT_ACK_TIMEOUT_SECONDS", 5, 1
)
TELEMETRY_INTERVAL_SECONDS = _int_setting(
    "APP247_TELEMETRY_INTERVAL_SECONDS", "TELEMETRY_INTERVAL_SECONDS", 60, 30
)
TELEMETRY_TIMEOUT_SECONDS = _float_setting(
    "APP247_TELEMETRY_TIMEOUT_SECONDS", "TELEMETRY_TIMEOUT_SECONDS", 5, 1
)
PAYMENT_CONNECT_TIMEOUT_SECONDS = _float_setting(
    "APP247_PAYMENT_CONNECT_TIMEOUT_SECONDS", "PAYMENT_CONNECT_TIMEOUT_SECONDS", 5, 1
)
PAYMENT_READ_TIMEOUT_SECONDS = _float_setting(
    "APP247_PAYMENT_READ_TIMEOUT_SECONDS", "PAYMENT_READ_TIMEOUT_SECONDS", 20, 1
)
RECEIPT_CONNECT_TIMEOUT_SECONDS = _float_setting(
    "APP247_RECEIPT_CONNECT_TIMEOUT_SECONDS", "RECEIPT_CONNECT_TIMEOUT_SECONDS", 5, 1
)
RECEIPT_READ_TIMEOUT_SECONDS = _float_setting(
    "APP247_RECEIPT_READ_TIMEOUT_SECONDS", "RECEIPT_READ_TIMEOUT_SECONDS", 45, 1
)
