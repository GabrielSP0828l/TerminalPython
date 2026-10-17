import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from app247_terminal.models.terminal import Terminal, TerminalConfigCorrupted
from app247_terminal.services.terminal_socket import TerminalSocket


def _terminal(**overrides):
    data = {
        "terminalId": "uuid-1",
        "serialNumber": "SERIAL",
        "nome": "Terminal",
        "codigo": "T1",
        "status": "ATIVO",
        "ativo": True,
        "activated": True,
        "condominioId": "cond",
        "condominioNome": "Condominio",
    }
    data.update(overrides)
    return Terminal.from_dict(data)


class TerminalConfigRecoveryTest(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name)
        self.path = self.root / "terminal.json"

    def tearDown(self):
        self._directory.cleanup()

    def test_save_flushes_file_and_directory_before_returning(self):
        synced = []
        real_fsync = os.fsync

        def tracking_fsync(descriptor):
            synced.append(os.path.realpath(f"/proc/self/fd/{descriptor}"))
            real_fsync(descriptor)

        with patch("app247_terminal.models.terminal.os.fsync", side_effect=tracking_fsync):
            _terminal().save(self.path)

        self.assertEqual("uuid-1", Terminal.load(self.path).terminalId)
        self.assertIn(str(self.path.with_suffix(".json.tmp")), synced)
        self.assertIn(str(self.root), synced)
        self.assertFalse(self.path.with_suffix(".json.tmp").exists())

    def test_unreadable_contents_raise_dedicated_error(self):
        for contents in (b"", b"{", b"\xff\xfe", b"[]", b'{"nome": "sem id"}'):
            with self.subTest(contents=contents):
                self.path.write_bytes(contents)
                with self.assertRaises(TerminalConfigCorrupted):
                    Terminal.load(self.path)
                self.assertIsNone(Terminal.load_or_none(self.path))
                self.assertFalse(Terminal.is_activated(self.path))

    def test_quarantine_preserves_corrupted_file_and_leaves_valid_one(self):
        self.assertIsNone(Terminal.quarantine_if_corrupted(self.path))

        _terminal().save(self.path)
        self.assertIsNone(Terminal.quarantine_if_corrupted(self.path))
        self.assertTrue(self.path.exists())

        self.path.write_bytes(b"\x00\x00\x00")
        backup = Terminal.quarantine_if_corrupted(self.path)
        self.assertFalse(self.path.exists())
        self.assertTrue(backup.name.startswith("terminal.json.corrupt-"))
        self.assertEqual(b"\x00\x00\x00", backup.read_bytes())

        self.path.write_text("{", encoding="utf-8")
        second = Terminal.quarantine_if_corrupted(self.path)
        self.assertNotEqual(backup, second)
        self.assertEqual(b"\x00\x00\x00", backup.read_bytes())

    def test_heartbeat_treats_corrupted_identity_as_not_activated(self):
        self.path.write_text("", encoding="utf-8")
        socket = TerminalSocket(ws_url="ws://backend.test", terminal_path=self.path)
        self.assertIsNone(socket._load_active_terminal())


class StartupWithCorruptedIdentityTest(unittest.TestCase):
    def test_gui_startup_survives_empty_terminal_json(self):
        project_root = Path(__file__).resolve().parents[1]
        script = textwrap.dedent("""
            import sys
            from unittest.mock import patch
            import app247_terminal.application as application
            from PyQt5.QtWidgets import QApplication
            from app247_terminal import main

            class Window:
                shutdown_was_requested = False

            with patch.object(application, "MainWindow", Window), \\
                    patch("app247_terminal.runtime.prepare_runtime_layout"), \\
                    patch.object(application, "present_main_window"), \\
                    patch.object(QApplication, "exec_", return_value=0):
                sys.exit(main.run([]))
        """)
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            (data_dir / "terminal.json").write_text("", encoding="utf-8")
            environment = {
                key: value for key, value in os.environ.items()
                if not key.startswith("APP247_") and key not in {
                    "API_URL", "WS_URL", "APP_ENV", "WAYLAND_DISPLAY",
                    "XDG_SESSION_TYPE",
                }
            }
            environment.update({
                "APP247_CONFIG_FILE": str(data_dir / "missing.env"),
                "APP247_API_URL": "",
                "APP247_WS_URL": "",
                "APP247_ENV": "test",
                "APP247_DATA_DIR": str(data_dir),
                "QT_QPA_PLATFORM": "offscreen",
                "PYTHONPATH": str(project_root / "src"),
            })
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=data_dir,
                env=environment,
                capture_output=True,
                text=True,
                timeout=60,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            backups = list(data_dir.glob("terminal.json.corrupt-*"))
            self.assertEqual(1, len(backups))
            self.assertFalse((data_dir / "terminal.json").exists())


class CredentialReadFailureTest(unittest.TestCase):
    def test_unusable_credential_is_reported_as_unavailable(self):
        from app247_terminal.application import MainWindow
        from app247_terminal.services.terminal_auth import TerminalCredentialMissing

        with patch(
            "app247_terminal.application.TerminalCredentialStore.load",
            side_effect=TerminalCredentialMissing("permissões inseguras"),
        ):
            self.assertFalse(MainWindow._credential_available())


if __name__ == "__main__":
    unittest.main()
