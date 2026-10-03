import os
import sqlite3
from datetime import datetime, timezone

from app247_terminal.config.settings import DATABASE_PATH
from app247_terminal.database.connection import connect_sqlite


class DatabaseIntegrityError(RuntimeError):
    """Impede operacao normal quando o SQLite nao pode ser considerado integro."""


class ActivePaymentStore:
    """Checkpoint mínimo da tentativa financeira ainda não resolvida."""

    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = os.fspath(db_path)
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self.assert_integrity()
        self._create_table()
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _connect(self):
        return connect_sqlite(self.db_path, row_factory=True)

    def assert_integrity(self):
        if not os.path.exists(self.db_path) or os.path.getsize(self.db_path) == 0:
            return True
        try:
            with self._connect() as connection:
                row = connection.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as error:
            raise DatabaseIntegrityError(
                "SQLite local corrompido; recuperacao administrativa necessaria"
            ) from error
        if row is None or str(row[0]).lower() != "ok":
            raise DatabaseIntegrityError(
                "SQLite local reprovado no integrity_check"
            )
        return True

    def has_unresolved_payment(self):
        """Consulta fail-closed usada antes de qualquer reset destrutivo."""
        try:
            return self.load() is not None
        except sqlite3.DatabaseError as error:
            raise DatabaseIntegrityError(
                "Nao foi possivel verificar o estado financeiro local"
            ) from error

    def _create_table(self):
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS active_payment (
                    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                    terminal_id TEXT,
                    generation TEXT NOT NULL,
                    local_attempt_id TEXT NOT NULL,
                    cart_id TEXT,
                    order_id TEXT,
                    payment_id TEXT,
                    payment_attempt_id TEXT,
                    cancellation_requested INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(active_payment)")
            }
            if "cancellation_requested" not in columns:
                connection.execute(
                    "ALTER TABLE active_payment ADD COLUMN "
                    "cancellation_requested INTEGER NOT NULL DEFAULT 0"
                )

    def save(self, snapshot):
        now = self._now()
        with self._connect() as connection:
            connection.execute("""
                INSERT INTO active_payment (
                    singleton_id, terminal_id, generation, local_attempt_id,
                    cart_id, order_id, payment_id, payment_attempt_id,
                    cancellation_requested, status, created_at, updated_at
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(singleton_id) DO UPDATE SET
                    terminal_id = excluded.terminal_id,
                    generation = excluded.generation,
                    local_attempt_id = excluded.local_attempt_id,
                    cart_id = excluded.cart_id,
                    order_id = excluded.order_id,
                    payment_id = excluded.payment_id,
                    payment_attempt_id = excluded.payment_attempt_id,
                    cancellation_requested = excluded.cancellation_requested,
                    status = excluded.status,
                    updated_at = excluded.updated_at
            """, (
                snapshot.get("terminal_id"), snapshot["generation"],
                snapshot["local_attempt_id"], snapshot.get("cart_id"),
                snapshot.get("order_id"), snapshot.get("payment_id"),
                snapshot.get("payment_attempt_id"),
                1 if snapshot.get("cancellation_requested") else 0,
                snapshot["status"], now, now,
            ))

    def load(self, terminal_id=None):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM active_payment WHERE singleton_id = 1"
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        if terminal_id and data.get("terminal_id") not in (None, str(terminal_id)):
            return None
        return data

    def checkpoint_cart(self, local_attempt_id, cart_id):
        """Persiste o cart antes do POST financeiro e rejeita worker obsoleto."""
        with self._connect() as connection:
            cursor = connection.execute("""
                UPDATE active_payment
                   SET cart_id = ?, updated_at = ?
                 WHERE singleton_id = 1 AND local_attempt_id = ?
            """, (str(cart_id), self._now(), str(local_attempt_id)))
            return cursor.rowcount == 1

    def clear(self):
        with self._connect() as connection:
            connection.execute("DELETE FROM active_payment WHERE singleton_id = 1")
