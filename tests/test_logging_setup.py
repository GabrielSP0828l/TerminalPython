import logging
import tempfile
import unittest
from pathlib import Path

from app247_terminal.logging_setup import LOG_FILE_NAME, configure_logging


class PersistentLoggingTest(unittest.TestCase):
    """BUG-050: o histórico precisa sobreviver a reinício com journald volátil."""

    def setUp(self):
        self.root = logging.getLogger()
        self.original_handlers = list(self.root.handlers)
        self.original_level = self.root.level
        self.tmp = tempfile.TemporaryDirectory()
        self.log_dir = Path(self.tmp.name) / "logs"

    def tearDown(self):
        for handler in list(self.root.handlers):
            if handler not in self.original_handlers:
                self.root.removeHandler(handler)
                handler.close()
        self.root.setLevel(self.original_level)
        self.tmp.cleanup()

    def _file_handlers(self):
        return [h for h in self.root.handlers if getattr(h, "_app247_file", None)]

    def test_writes_log_file_in_persistent_directory(self):
        path = configure_logging(self.log_dir)
        logging.getLogger("app247.teste").info("[TESTE] orderId=order-1")
        for handler in self._file_handlers():
            handler.flush()

        self.assertEqual(self.log_dir / LOG_FILE_NAME, path)
        self.assertIn("[TESTE] orderId=order-1", path.read_text(encoding="utf-8"))

    def test_rotation_keeps_total_size_bounded(self):
        configure_logging(self.log_dir, max_bytes=2048, backup_count=2)
        logger = logging.getLogger("app247.teste")
        for index in range(400):
            logger.info("linha de teste %04d %s", index, "x" * 40)
        for handler in self._file_handlers():
            handler.flush()

        files = sorted(self.log_dir.iterdir())
        self.assertEqual(
            [LOG_FILE_NAME, f"{LOG_FILE_NAME}.1", f"{LOG_FILE_NAME}.2"],
            [f.name for f in files],
        )
        self.assertLessEqual(sum(f.stat().st_size for f in files), 3 * 2048 + 200)

    def test_repeated_configuration_does_not_duplicate_handlers(self):
        configure_logging(self.log_dir)
        configure_logging(self.log_dir)

        self.assertEqual(1, len(self._file_handlers()))
        self.assertEqual(
            1,
            len([h for h in self.root.handlers if getattr(h, "_app247_stream", False)]),
        )

    def test_unwritable_directory_falls_back_to_journal_only(self):
        blocker = Path(self.tmp.name) / "arquivo"
        blocker.write_text("nao e diretorio")

        self.assertIsNone(configure_logging(blocker / "logs"))
        self.assertEqual([], self._file_handlers())

    def test_symlinked_log_file_is_refused(self):
        self.log_dir.mkdir()
        target = Path(self.tmp.name) / "alvo"
        target.write_text("")
        (self.log_dir / LOG_FILE_NAME).symlink_to(target)

        self.assertIsNone(configure_logging(self.log_dir))
        self.assertEqual("", target.read_text())


if __name__ == "__main__":
    unittest.main()
