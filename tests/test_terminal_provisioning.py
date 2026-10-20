import tempfile
import unittest
from pathlib import Path

from app247_terminal.services.terminal_auth import (
    TerminalCredentialStore,
    TerminalPairingExpired,
    claim_pairing,
    start_pairing,
)


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


START = {
    "pairingToken": "tpt_secret",
    "code": "K7Q4-MZ8P",
    "qrPayload": "APP247-PAIR:K7Q4-MZ8P",
    "expiresAt": "2026-10-20T12:15:00Z",
}


class TerminalPairingTest(unittest.TestCase):
    def test_start_sends_device_identity_and_returns_code(self):
        session = FakeSession(FakeResponse(201, START))

        pairing = start_pairing(
            {"serialNumber": "serial-a", "macAddress": "aa:bb", "ipAddress": ""},
            "http://backend/", session,
        )

        self.assertEqual("K7Q4-MZ8P", pairing["code"])
        self.assertEqual("tpt_secret", pairing["pairingToken"])
        url, kwargs = session.calls[0]
        self.assertEqual("http://backend/terminal/pairing", url)
        self.assertEqual({"serialNumber": "serial-a", "macAddress": "aa:bb"}, kwargs["json"])

    def test_start_rejects_incomplete_response(self):
        with self.assertRaises(ValueError):
            start_pairing({"serialNumber": "s"}, "http://backend",
                          FakeSession(FakeResponse(201, {"code": "X"})))

    def test_claim_pending_installs_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TerminalCredentialStore(Path(directory) / "credential")
            session = FakeSession(FakeResponse(200, {"status": "PENDING"}))

            self.assertIsNone(claim_pairing("tpt_secret", "http://backend", session, store))
            self.assertIsNone(store.load())
            self.assertEqual({"pairingToken": "tpt_secret"}, session.calls[0][1]["json"])

    def test_claim_paired_installs_credential_and_returns_activation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TerminalCredentialStore(Path(directory) / "credential")
            session = FakeSession(FakeResponse(200, {
                "status": "PAIRED", "terminalId": "terminal-a", "serialNumber": "serial-a",
                "ativo": True, "activated": True, "credential": "tdc_individual",
                "credentialVersion": 1,
            }))

            activation = claim_pairing("tpt_secret", "http://backend", session, store)

            self.assertEqual("tdc_individual", store.load())
            self.assertEqual("terminal-a", activation["terminalId"])
            self.assertTrue(activation["activated"])
            self.assertNotIn("credential", activation)

    def test_claim_expired_asks_for_new_code(self):
        for status in (409, 410):
            with self.subTest(status=status), self.assertRaises(TerminalPairingExpired):
                claim_pairing("tpt_secret", "http://backend",
                              FakeSession(FakeResponse(status, {"code": "PAIRING_EXPIRED"})))

    def test_claim_paired_without_credential_installs_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TerminalCredentialStore(Path(directory) / "credential")
            with self.assertRaises(ValueError):
                claim_pairing("tpt_secret", "http://backend", FakeSession(
                    FakeResponse(200, {"status": "PAIRED", "terminalId": "terminal-a"})), store)
            self.assertIsNone(store.load())


if __name__ == "__main__":
    unittest.main()
