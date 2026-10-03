import tempfile
import unittest
from pathlib import Path

from app247_terminal.services.backend_client import (
    BackendClient,
    BackendHttpError,
    terminal_access_state,
)
from app247_terminal.services.terminal_auth import TerminalCredentialStore


class Response:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self.payload = payload or {}

    def json(self):
        return self.payload


class Session:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


class BackendClientTest(unittest.TestCase):
    def tearDown(self):
        terminal_access_state.set("OPERATIONAL")

    def client(self, root, response):
        store = TerminalCredentialStore(root / "credential")
        store.install("tdc_test_backend_client")
        session = Session(response)
        return BackendClient("http://backend", session, store), session

    def test_operational_request_uses_individual_credential_and_terminal_id(self):
        with tempfile.TemporaryDirectory() as directory:
            client, session = self.client(Path(directory), Response(200))
            client.request("GET", "/produtos/sync", terminal_id="terminal-a")
            headers = session.calls[0][2]["headers"]
            self.assertEqual("tdc_test_backend_client", headers["X-Terminal-Token"])
            self.assertEqual("terminal-a", headers["X-Terminal-Id"])

    def test_401_and_403_are_distinct_safe_states(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for status, attribute in ((401, "authentication_failed"), (403, "forbidden")):
                with self.subTest(status=status):
                    client, _ = self.client(
                        root, Response(status, {"code": "TERMINAL_TEST"})
                    )
                    with self.assertRaises(BackendHttpError) as raised:
                        client.request("POST", "/terminal/telemetry")
                    self.assertTrue(getattr(raised.exception, attribute))
                    self.assertEqual("TERMINAL_TEST", raised.exception.code)

    def test_public_activation_does_not_send_device_credential(self):
        session = Session(Response(200))
        client = BackendClient("http://backend", session)
        client.request(
            "GET", "/terminal/serial/serial-a", authenticated=False
        )
        self.assertEqual({}, session.calls[0][2]["headers"])


if __name__ == "__main__":
    unittest.main()
