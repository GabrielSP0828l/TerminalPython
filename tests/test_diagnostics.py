import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app247_terminal.diagnostics import run_diagnostics


class FakeResponse:
    status_code = 200


class FakeSession:
    def get(self, url, timeout):
        self.url = url
        self.timeout = timeout
        return FakeResponse()


class InstallationDiagnosticsTest(unittest.TestCase):
    def test_production_installation_reports_valid_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"
            data.mkdir()
            database = data / "terminal.db"
            sqlite3.connect(database).close()
            credential = data / "device-credential"
            credential.write_text("tdc_valid-test-credential", encoding="ascii")
            credential.chmod(0o600)
            config_file = root / "terminal.env"
            config_file.touch()
            config_file.chmod(0o640)
            release = root / "releases/1.0.0"
            release.mkdir(parents=True)
            (release / "app247-terminal").touch()
            current = root / "current"
            current.symlink_to(release)

            with patch("app247_terminal.diagnostics.settings.API_URL", "https://api.app247.test"), patch(
                "app247_terminal.diagnostics.settings.WS_URL", "wss://api.app247.test"
            ), patch("app247_terminal.diagnostics.settings.IS_PRODUCTION", True), patch(
                "app247_terminal.diagnostics.settings.CONFIG_ENV_PATH", config_file
            ), patch(
                "app247_terminal.diagnostics.settings.TERMINAL_ADMIN_PASSWORD", "strong-password"
            ), patch(
                "app247_terminal.diagnostics.settings.LEGACY_TERMINAL_AUTH_ENABLED", False
            ), patch("app247_terminal.diagnostics.settings.DATA_DIR", data), patch(
                "app247_terminal.diagnostics.settings.DATABASE_PATH", database
            ), patch(
                "app247_terminal.diagnostics.settings.DEVICE_CREDENTIAL_PATH", credential
            ):
                results = run_diagnostics(session=FakeSession(), current_link=current)

            self.assertFalse([item for item in results if item.level == "ERROR"])
            self.assertIn("SQLite", {item.name for item in results if item.level == "OK"})
            self.assertIn(
                "Credencial individual",
                {item.name for item in results if item.level == "OK"},
            )

    def test_placeholder_urls_and_insecure_credential_are_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            credential = root / "credential"
            credential.write_text("tdc_valid-test-credential", encoding="ascii")
            credential.chmod(0o644)
            with patch(
                "app247_terminal.diagnostics.settings.API_URL",
                "https://api.exemplo.app247.com",
            ), patch(
                "app247_terminal.diagnostics.settings.WS_URL",
                "wss://api.exemplo.app247.com",
            ), patch("app247_terminal.diagnostics.settings.IS_PRODUCTION", False), patch(
                "app247_terminal.diagnostics.settings.DATA_DIR", root
            ), patch("app247_terminal.diagnostics.settings.DATABASE_PATH", root / "missing.db"), patch(
                "app247_terminal.diagnostics.settings.DEVICE_CREDENTIAL_PATH", credential
            ):
                results = run_diagnostics(session=FakeSession(), current_link=root / "current")

            errors = {item.name for item in results if item.level == "ERROR"}
            self.assertTrue({"API URL", "WebSocket URL", "Credencial individual"} <= errors)


if __name__ == "__main__":
    unittest.main()
