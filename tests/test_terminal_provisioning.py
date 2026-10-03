import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from service.TerminalAuth import (
    TerminalCredentialStore,
    migrate_legacy_credential,
)


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            "terminalId": "terminal-a",
            "credential": "tdc_individual",
            "version": 1,
            "createdAt": "2026-09-28T12:00:00Z",
        }


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse()


class TerminalProvisioningTest(unittest.TestCase):
    def test_legacy_migration_installs_individual_credential_once(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "service.TerminalAuth.LEGACY_TERMINAL_AUTH_ENABLED", True
        ), patch(
            "service.TerminalAuth.TERMINAL_INTERNAL_TOKEN", "legacy-test-secret"
        ):
            store = TerminalCredentialStore(Path(directory) / "credential")
            session = FakeSession()
            result = migrate_legacy_credential(
                "terminal-a", "http://backend", session, store
            )
            self.assertEqual("terminal-a", result["terminalId"])
            self.assertEqual("tdc_individual", store.load())
            self.assertTrue(session.calls[0][0].endswith(
                "/terminal/terminal-a/credential/migrate"
            ))
            self.assertEqual(
                "legacy-test-secret",
                session.calls[0][1]["headers"]["X-Terminal-Token"],
            )

    def test_migration_never_installs_credential_for_another_terminal(self):
        class WrongTerminalResponse(FakeResponse):
            def json(self):
                payload = super().json()
                payload["terminalId"] = "terminal-b"
                return payload

        class WrongSession(FakeSession):
            def post(self, url, **kwargs):
                return WrongTerminalResponse()

        with tempfile.TemporaryDirectory() as directory, patch(
            "service.TerminalAuth.LEGACY_TERMINAL_AUTH_ENABLED", True
        ), patch(
            "service.TerminalAuth.TERMINAL_INTERNAL_TOKEN", "legacy-test-secret"
        ):
            store = TerminalCredentialStore(Path(directory) / "credential")
            with self.assertRaises(ValueError):
                migrate_legacy_credential(
                    "terminal-a", "http://backend", WrongSession(), store
                )
            self.assertIsNone(store.load())


if __name__ == "__main__":
    unittest.main()
