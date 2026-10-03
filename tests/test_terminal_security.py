import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from app247_terminal.services.terminal_auth import (
    LegacyTerminalAuthDisabled,
    TerminalCredentialMissing,
    TerminalCredentialStore,
    legacy_migration_headers,
    terminal_auth_headers,
)


class TerminalSecurityTest(unittest.TestCase):
    def test_runtime_credential_is_distinct_from_terminal_identifier(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TerminalCredentialStore(Path(directory) / "credential")
            store.install("tdc_test-only-device-secret")
            headers = terminal_auth_headers("terminal-a", store=store)
            self.assertEqual(
                "tdc_test-only-device-secret", headers["X-Terminal-Token"]
            )
            self.assertEqual("terminal-a", headers["X-Terminal-Id"])

    def test_production_fails_closed_without_device_credential(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TerminalCredentialStore(Path(directory) / "missing")
            with self.assertRaises(TerminalCredentialMissing):
                terminal_auth_headers("terminal-a", store=store)

    def test_credential_install_is_atomic_and_mode_0600(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credential"
            store = TerminalCredentialStore(path)
            store.install("tdc_first")
            store.install("tdc_second")
            self.assertEqual("tdc_second", store.load())
            self.assertEqual(0o600, os.stat(path).st_mode & 0o777)
            self.assertEqual([], list(path.parent.glob(f".{path.name}.*")))

    def test_credential_rejects_insecure_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credential"
            path.write_text("tdc_not_private", encoding="ascii")
            os.chmod(path, 0o644)
            with self.assertRaisesRegex(TerminalCredentialMissing, "permissões"):
                TerminalCredentialStore(path).load()

    def test_credential_rejects_symbolic_link(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.write_text("tdc_secret_value", encoding="ascii")
            os.chmod(target, 0o600)
            link = root / "credential"
            link.symlink_to(target)
            with self.assertRaisesRegex(TerminalCredentialMissing, "arquivo regular"):
                TerminalCredentialStore(link).load()

    def test_credential_rejects_unexpected_format(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TerminalCredentialStore(Path(directory) / "credential")
            with self.assertRaisesRegex(ValueError, "formato tdc_"):
                store.install("terminal-a:plain-secret")

    def test_global_token_is_never_operational_fallback(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "app247_terminal.services.terminal_auth.TERMINAL_INTERNAL_TOKEN", "legacy-secret"
        ):
            with self.assertRaises(TerminalCredentialMissing):
                terminal_auth_headers(
                    "terminal-a",
                    store=TerminalCredentialStore(Path(directory) / "missing"),
                )

    def test_legacy_token_requires_explicit_migration_mode(self):
        with patch("app247_terminal.services.terminal_auth.LEGACY_TERMINAL_AUTH_ENABLED", False), patch(
            "app247_terminal.services.terminal_auth.TERMINAL_INTERNAL_TOKEN", "legacy-secret"
        ):
            with self.assertRaises(LegacyTerminalAuthDisabled):
                legacy_migration_headers("terminal-a")

        with patch("app247_terminal.services.terminal_auth.LEGACY_TERMINAL_AUTH_ENABLED", True), patch(
            "app247_terminal.services.terminal_auth.TERMINAL_INTERNAL_TOKEN", "legacy-secret"
        ):
            self.assertEqual(
                "legacy-secret",
                legacy_migration_headers("terminal-a")["X-Terminal-Token"],
            )


if __name__ == "__main__":
    unittest.main()
