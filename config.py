import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

API_URL = os.getenv("API_URL", "").rstrip("/")
WS_URL = os.getenv("WS_URL", "").rstrip("/")
TERMINAL_ADMIN_PASSWORD = os.getenv("TERMINAL_ADMIN_PASSWORD", "")

DATABASE_PATH = PROJECT_ROOT / "db" / "terminal.db"
TERMINAL_CONFIG_PATH = PROJECT_ROOT / "db" / "terminal.json"
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
