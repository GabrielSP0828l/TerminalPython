import tempfile
import unittest
from pathlib import Path

from service.FactoryResetService import FactoryResetService


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
                Path("db/terminal.db"): "database",
                Path("database/last_sync.txt"): "sync",
                Path("temp_checkout.png"): "image",
            }
            for relative_path, content in expected.items():
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            env_file = root / ".env"
            env_file.write_text("API_URL=test", encoding="utf-8")

            service = FactoryResetService(root)
            service.request_reset()
            backup_dir, moved_files = service.apply_pending()

            self.assertEqual(set(expected), set(moved_files))
            for relative_path, content in expected.items():
                self.assertFalse((root / relative_path).exists())
                self.assertEqual(content, (backup_dir / relative_path).read_text())

            self.assertTrue(env_file.exists())
            self.assertFalse(root.joinpath(service.RESET_MARKER).exists())

    def test_apply_without_marker_is_a_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            service = FactoryResetService(directory)
            self.assertIsNone(service.apply_pending())


if __name__ == "__main__":
    unittest.main()
