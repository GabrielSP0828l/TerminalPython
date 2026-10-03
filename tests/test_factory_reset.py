import tempfile
import unittest
import sqlite3
from pathlib import Path

from app247_terminal.services.factory_reset import (
    FactoryResetService,
    ResetBlockedActivePayment,
    ResetBlockedCriticalState,
)
from app247_terminal.services.terminal_auth import TerminalCredentialStore


class FactoryResetServiceTest(unittest.TestCase):
    def test_request_does_not_remove_state_immediately(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            terminal_file = root / "db/terminal.json"
            terminal_file.parent.mkdir(parents=True)
            terminal_file.write_text("{}", encoding="utf-8")

            service = FactoryResetService(root)
            service.request_reset()

            self.assertTrue(terminal_file.exists())
            self.assertTrue(root.joinpath(service.RESET_MARKER).exists())

    def test_apply_pending_moves_only_local_operational_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = {
                Path("db/terminal.json"): "terminal",
                Path("database/last_sync.txt"): "sync",
                Path("temp_checkout.png"): "image",
            }
            for relative_path, content in expected.items():
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            database = root / "db/terminal.db"
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE cache (id INTEGER PRIMARY KEY)")
            expected_paths = set(expected) | {Path("db/terminal.db")}

            env_file = root / ".env"
            env_file.write_text("API_URL=test", encoding="utf-8")

            service = FactoryResetService(root)
            service.request_reset()
            backup_dir, moved_files = service.apply_pending()

            self.assertEqual(expected_paths, set(moved_files))
            for relative_path, content in expected.items():
                self.assertFalse((root / relative_path).exists())
                self.assertEqual(content, (backup_dir / relative_path).read_text())
            self.assertTrue((backup_dir / "db/terminal.db").exists())

            self.assertTrue(env_file.exists())
            self.assertFalse(root.joinpath(service.RESET_MARKER).exists())

    def test_apply_without_marker_is_a_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            service = FactoryResetService(directory)
            self.assertIsNone(service.apply_pending())

    def test_remote_reset_purges_tenant_data_and_preserves_device_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tenant_files = {
                Path("db/terminal.json"): "empresa-a",
                Path("database/last_sync.txt"): "cursor-a",
                Path("temp_checkout.png"): "pagamento-a",
            }
            preserved = {
                Path(".env"): "API_URL=test",
                Path("db/display_orientation"): "portrait",
                Path("logs/terminal.log"): "log técnico",
            }
            for relative_path, content in {**tenant_files, **preserved}.items():
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            database = root / "db/terminal.db"
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE cache (id INTEGER PRIMARY KEY)")
            tenant_paths = set(tenant_files) | {Path("db/terminal.db")}

            service = FactoryResetService(root)
            service.request_reset(
                terminal_id="terminal-a", reason="COMPANY_CLOSED", remote=True
            )
            backup, moved = service.apply_pending()

            self.assertIsNone(backup)
            self.assertEqual(tenant_paths, set(moved))
            for relative_path in tenant_paths:
                self.assertFalse((root / relative_path).exists())
            for relative_path, content in preserved.items():
                self.assertEqual(content, (root / relative_path).read_text())
            self.assertEqual(
                "terminal-a", service.pending_completion()["terminalId"]
            )
            staging = root / "db/reset-staging"
            self.assertEqual([], list(staging.glob("*")) if staging.exists() else [])

    def test_remote_reset_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            terminal_file = root / "db/terminal.json"
            terminal_file.parent.mkdir(parents=True)
            terminal_file.write_text("empresa-a", encoding="utf-8")
            service = FactoryResetService(root)

            service.request_reset("terminal-a", "COMPANY_CLOSED", remote=True)
            service.apply_pending()
            service.request_reset("terminal-a", "COMPANY_CLOSED", remote=True)
            service.apply_pending()

            self.assertFalse(terminal_file.exists())
            self.assertEqual("terminal-a", service.pending_completion()["terminalId"])

    def test_remote_reset_keeps_credential_until_completion_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = TerminalCredentialStore(root / "device-credential")
            store.install("tdc_test_remote_reset")
            service = FactoryResetService(root, credential_store=store)
            service.request_reset("terminal-a", "COMPANY_CLOSED", remote=True)

            service.apply_pending()
            self.assertEqual("tdc_test_remote_reset", store.load())

            service.acknowledge_completion()
            self.assertIsNone(store.load())

    def test_pending_payment_blocks_reset_and_preserves_marker_and_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "db/terminal.db"
            database.parent.mkdir(parents=True)
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "CREATE TABLE active_payment "
                    "(singleton_id INTEGER PRIMARY KEY, status TEXT)"
                )
                connection.execute(
                    "INSERT INTO active_payment VALUES (1, 'UNKNOWN')"
                )
            service = FactoryResetService(root)
            service.request_reset()

            with self.assertRaises(ResetBlockedActivePayment):
                service.apply_pending()

            self.assertTrue(database.exists())
            self.assertTrue(root.joinpath(service.RESET_MARKER).exists())

    def test_factory_reset_removes_device_credential_after_financial_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = TerminalCredentialStore(root / "device-credential")
            store.install("tdc_test_reset")
            service = FactoryResetService(root, credential_store=store)
            service.request_reset()

            service.apply_pending()

            self.assertIsNone(store.load())

    def test_corrupt_sqlite_blocks_reset_without_deleting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "db/terminal.db"
            database.parent.mkdir(parents=True)
            database.write_bytes(b"not-a-sqlite-database")
            service = FactoryResetService(root)
            service.request_reset()

            with self.assertRaises(ResetBlockedCriticalState):
                service.apply_pending()

            self.assertEqual(b"not-a-sqlite-database", database.read_bytes())


if __name__ == "__main__":
    unittest.main()
