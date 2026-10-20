import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from app247_terminal.services.terminal_auth import TerminalCredentialStore
from app247_terminal.ui.screens import terminal_registration
from app247_terminal.ui.screens.terminal_registration import ActivationCheckThread

DEVICE = {"serialNumber": "serial-a", "macAddress": "aa:bb", "ipAddress": "10.0.0.2"}
START = {
    "pairingToken": "tpt_secret", "code": "K7Q4-MZ8P",
    "qrPayload": "APP247-PAIR:K7Q4-MZ8P", "expiresAt": "2026-10-20T12:15:00Z",
}
PAIRED = {
    "status": "PAIRED", "terminalId": "terminal-a", "serialNumber": "serial-a",
    "ativo": True, "activated": True, "credential": "tdc_individual", "credentialVersion": 1,
}


class Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.urls = []

    def post(self, url, **kwargs):
        self.urls.append(url)
        return self.responses.pop(0)

    get = post


class ActivationPairingFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = TerminalCredentialStore(Path(directory.name) / "credential")
        for target, value in (
            ("API_URL", "http://backend"),
            ("TerminalCredentialStore", lambda: self.store),
        ):
            patcher = patch.object(terminal_registration, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.events = {"pairing": [], "activation": [], "status": []}

    def _thread(self, session):
        thread = ActivationCheckThread(DEVICE, lifecycle_api=MagicMock(), session=session)
        thread.pairing_changed.connect(self.events["pairing"].append)
        thread.activation_found.connect(self.events["activation"].append)
        thread.status_changed.connect(lambda message, error: self.events["status"].append(message))
        return thread

    def test_shows_code_then_installs_credential_after_approval(self):
        session = Session(
            Response(201, START),
            Response(200, {"status": "PENDING"}),
            Response(200, PAIRED),
        )
        thread = self._thread(session)

        thread.run()
        self.assertEqual([{"code": "K7Q4-MZ8P", "qrPayload": "APP247-PAIR:K7Q4-MZ8P"}],
                         self.events["pairing"])
        self.assertEqual([], self.events["activation"])
        self.assertIsNone(self.store.load())

        thread.run()
        self.assertEqual("tdc_individual", self.store.load())
        self.assertEqual("terminal-a", self.events["activation"][0]["terminalId"])
        self.assertEqual(None, self.events["pairing"][-1])
        self.assertEqual(
            ["http://backend/terminal/pairing", "http://backend/terminal/pairing/claim",
             "http://backend/terminal/pairing/claim"],
            session.urls,
        )

    def test_expired_code_is_replaced_on_next_check(self):
        session = Session(
            Response(201, START),
            Response(410, {"code": "PAIRING_EXPIRED"}),
            Response(201, dict(START, code="ABCD-EFGH", qrPayload="APP247-PAIR:ABCD-EFGH")),
            Response(200, {"status": "PENDING"}),
        )
        thread = self._thread(session)

        thread.run()
        self.assertIsNone(thread.pairing)
        thread.run()

        self.assertEqual("ABCD-EFGH", self.events["pairing"][-1]["code"])

    def test_renews_code_before_backend_expires_it(self):
        session = Session(
            Response(201, START), Response(200, {"status": "PENDING"}),
            Response(201, dict(START, code="ABCD-EFGH", qrPayload="APP247-PAIR:ABCD-EFGH")),
            Response(200, {"status": "PENDING"}),
        )
        thread = self._thread(session)

        thread.run()
        thread.pairing_deadline = 0
        thread.run()

        self.assertEqual("ABCD-EFGH", self.events["pairing"][-1]["code"])

    def test_with_credential_only_checks_activation_by_serial(self):
        self.store.install("tdc_existing")
        session = Session(Response(200, {"terminalId": "terminal-a", "activated": True}))

        self._thread(session).run()

        self.assertEqual(["http://backend/terminal/serial/serial-a"], session.urls)
        self.assertEqual("terminal-a", self.events["activation"][0]["terminalId"])
        self.assertEqual([], self.events["pairing"])

    def test_offline_backend_keeps_waiting(self):
        class Offline:
            def post(self, *args, **kwargs):
                raise terminal_registration.requests.ConnectionError("offline")

        self._thread(Offline()).run()

        self.assertIn("Sem conexão com o servidor. Tentando novamente...", self.events["status"])
        self.assertIsNone(self.store.load())


if __name__ == "__main__":
    unittest.main()
