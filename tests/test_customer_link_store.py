import sqlite3
import tempfile
import unittest
from pathlib import Path

from database.CustomerLinkStore import CustomerLinkStore


class CustomerLinkStoreTest(unittest.TestCase):
    def test_persists_only_cart_identifier_and_integrity_stays_ok(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "terminal.db"
            store = CustomerLinkStore(path)
            store.save("cart-123")
            self.assertEqual("cart-123", store.load())
            with sqlite3.connect(path) as connection:
                columns = [row[1] for row in connection.execute(
                    "PRAGMA table_info(customer_link_state)"
                )]
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            self.assertEqual(["singleton_id", "cart_id", "updated_at"], columns)
            self.assertEqual("ok", integrity)
            store.clear()
            self.assertIsNone(store.load())


if __name__ == "__main__":
    unittest.main()
