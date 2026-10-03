import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
if APP_ENV not in {"development", "production"}:
    APP_ENV = "development"
IS_PRODUCTION = APP_ENV == "production"

API_URL = os.getenv("API_URL", "").rstrip("/")
WS_URL = os.getenv("WS_URL", "").rstrip("/")
TERMINAL_ADMIN_PASSWORD = os.getenv("TERMINAL_ADMIN_PASSWORD", "")
# Segredo global legado: somente bootstrap/migracao explicitamente habilitada.
TERMINAL_INTERNAL_TOKEN = os.getenv("TERMINAL_INTERNAL_TOKEN", "")
LEGACY_TERMINAL_AUTH_ENABLED = (
    os.getenv("LEGACY_TERMINAL_AUTH_ENABLED", "false").strip().lower() == "true"
)

DATABASE_PATH = PROJECT_ROOT / "db" / "terminal.db"
TERMINAL_CONFIG_PATH = PROJECT_ROOT / "db" / "terminal.json"
DEVICE_CREDENTIAL_PATH = Path(
    os.getenv("DEVICE_CREDENTIAL_PATH", str(PROJECT_ROOT / "db" / "device-credential"))
)
DISPLAY_ORIENTATION_PATH = PROJECT_ROOT / "db" / "display_orientation"
LAST_SYNC_PATH = PROJECT_ROOT / "database" / "last_sync.txt"

PRODUCT_SYNC_INTERVAL_SECONDS = max(
    60, int(os.getenv("PRODUCT_SYNC_INTERVAL_SECONDS", "300"))
)
HEARTBEAT_INTERVAL_SECONDS = max(
    5, int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "10"))
)
HEARTBEAT_RETRY_SECONDS = max(
    1, int(os.getenv("HEARTBEAT_RETRY_SECONDS", "5"))
)
HEARTBEAT_ACK_TIMEOUT_SECONDS = max(
    1.0, float(os.getenv("HEARTBEAT_ACK_TIMEOUT_SECONDS", "5"))
)
TELEMETRY_INTERVAL_SECONDS = max(
    30, int(os.getenv("TELEMETRY_INTERVAL_SECONDS", "60"))
)
TELEMETRY_TIMEOUT_SECONDS = max(
    1.0, float(os.getenv("TELEMETRY_TIMEOUT_SECONDS", "5"))
)
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
PAYMENT_CONNECT_TIMEOUT_SECONDS = max(
    1.0, float(os.getenv("PAYMENT_CONNECT_TIMEOUT_SECONDS", "5"))
)
PAYMENT_READ_TIMEOUT_SECONDS = max(
    1.0, float(os.getenv("PAYMENT_READ_TIMEOUT_SECONDS", "20"))
)
RECEIPT_CONNECT_TIMEOUT_SECONDS = max(
    1.0, float(os.getenv("RECEIPT_CONNECT_TIMEOUT_SECONDS", "5"))
)
RECEIPT_READ_TIMEOUT_SECONDS = max(
    1.0, float(os.getenv("RECEIPT_READ_TIMEOUT_SECONDS", "45"))
)
