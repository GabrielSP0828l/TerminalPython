import os
import sqlite3
from datetime import datetime, timezone

from config import DATABASE_PATH


class CustomerLinkStore:
    """Persiste só o cartId; nunca QR, CPF, e-mail, JWT ou nome do cliente."""

    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = os.fspath(db_path)
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS customer_link_state (
                    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                    cart_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=5)
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def save(self, cart_id):
        with self._connect() as connection:
            connection.execute("""
                INSERT INTO customer_link_state(singleton_id, cart_id, updated_at)
                VALUES(1, ?, ?)
                ON CONFLICT(singleton_id) DO UPDATE SET
                    cart_id=excluded.cart_id, updated_at=excluded.updated_at
            """, (str(cart_id), self._now()))

    def load(self):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT cart_id FROM customer_link_state WHERE singleton_id=1"
            ).fetchone()
        return str(row[0]) if row else None

    def clear(self):
        with self._connect() as connection:
            connection.execute("DELETE FROM customer_link_state WHERE singleton_id=1")
