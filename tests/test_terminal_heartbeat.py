import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from model.Terminal import Terminal
from service.TerminalAuth import TerminalCredentialStore
from service.TerminalSocket import TerminalSocket
from service.BackendClient import terminal_access_state


class FakeWebSocket:
    def __init__(self, acknowledgement=None, connected_event=None):
        self.acknowledgement = acknowledgement
        self.connected_event = connected_event
        self.sent = []
        self.closed = False

    def settimeout(self, timeout):
        self.timeout = timeout

    def connect(self, url, **kwargs):
        self.url = url
        self.connect_options = kwargs
        if self.connected_event:
            self.connected_event.set()

    def send(self, payload):
        self.sent.append(json.loads(payload))

    def recv(self):
        return json.dumps(self.acknowledgement)

    def close(self):
        self.closed = True


class TerminalHeartbeatTest(unittest.TestCase):
    def tearDown(self):
        terminal_access_state.set("OPERATIONAL")

    def save_terminal(self, root, active=True):
        path = root / "terminal.json"
        Terminal.from_dict({
            "terminalId": "terminal-a",
            "ativo": active,
            "activated": active,
        }).save(path)
        return path

    def test_heartbeat_uses_uuid_and_requires_persisted_last_ping_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            terminal_path = self.save_terminal(Path(directory))
            socket = FakeWebSocket({
                "type": "HEARTBEAT_ACK",
                "terminalId": "terminal-a",
                "status": "ONLINE",
                "lastPing": "2026-08-24T15:00:00",
            })
            service = TerminalSocket(
                ws_url="ws://backend", terminal_path=terminal_path,
                websocket_factory=lambda: socket,
                credential_store=self.save_credential(Path(directory)),
            )
            service._connect()
            service._send_and_confirm(service._load_active_terminal())

            self.assertEqual(
                {"terminalId": "terminal-a", "status": "ONLINE"}, socket.sent[0]
            )
            self.assertIn(
                "X-Terminal-Token: tdc_test_heartbeat",
                socket.connect_options["header"],
            )
            self.assertTrue(socket.connect_options["suppress_origin"])

    def test_offline_retries_and_recovers_without_stopping_service(self):
        with tempfile.TemporaryDirectory() as directory:
            terminal_path = self.save_terminal(Path(directory))
            recovered = threading.Event()
            healthy = FakeWebSocket({
                "type": "HEARTBEAT_ACK",
                "terminalId": "terminal-a",
                "status": "ONLINE",
                "lastPing": "2026-08-24T15:00:00",
            }, recovered)
            attempts = iter([RuntimeError("offline"), healthy])

            def factory():
                value = next(attempts, healthy)
                if isinstance(value, Exception):
                    raise value
                return value

            service = TerminalSocket(
                ws_url="ws://backend", terminal_path=terminal_path,
                interval_seconds=0.01, retry_seconds=0.01,
                websocket_factory=factory,
                credential_store=self.save_credential(Path(directory)),
            )
            service.start()
            self.assertTrue(recovered.wait(1))
            time.sleep(0.03)
            self.assertTrue(service._thread.is_alive())
            self.assertGreaterEqual(len(healthy.sent), 1)
            service.stop()

    def test_inactive_terminal_does_not_send(self):
        with tempfile.TemporaryDirectory() as directory:
            terminal_path = self.save_terminal(Path(directory), active=False)
            service = TerminalSocket(
                ws_url="ws://backend", terminal_path=terminal_path,
                websocket_factory=lambda: FakeWebSocket({}),
            )
            self.assertIsNone(service._load_active_terminal())

    def test_unauthorized_handshake_enters_safe_mode_without_retry_loop(self):
        class Unauthorized(RuntimeError):
            status_code = 401

        with tempfile.TemporaryDirectory() as directory:
            terminal_path = self.save_terminal(Path(directory))
            attempts = []

            def factory():
                attempts.append(True)
                raise Unauthorized("unauthorized")

            service = TerminalSocket(
                ws_url="ws://backend",
                terminal_path=terminal_path,
                retry_seconds=0.01,
                websocket_factory=factory,
                credential_store=self.save_credential(Path(directory)),
            )
            thread = service.start()
            thread.join(timeout=1)
            self.assertFalse(thread.is_alive())
            self.assertEqual("AUTH_REQUIRED", service.connection_state)
            self.assertEqual(1, len(attempts))

    @staticmethod
    def save_credential(root):
        store = TerminalCredentialStore(root / "device-credential")
        store.install("tdc_test_heartbeat")
        return store


if __name__ == "__main__":
    unittest.main()
