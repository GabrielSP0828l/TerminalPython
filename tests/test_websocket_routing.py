import unittest
from unittest.mock import patch

from websocket import ABNF

from app247_terminal.services.payment_listener import (
    PaymentListener,
    PaymentSocketStale,
)
from app247_terminal.models.terminal import Terminal


class WebSocketRoutingTest(unittest.TestCase):
    def setUp(self):
        terminal = Terminal.from_dict({
            "terminalId": "terminal-a", "ativo": True, "activated": True,
        })
        with patch("app247_terminal.services.payment_listener.Terminal.load", return_value=terminal):
            self.listener = PaymentListener()

    def tearDown(self):
        self.listener.is_running = False

    def test_payment_and_product_events_are_routed_separately(self):
        payment_events = []
        product_events = []
        self.listener.payment_status_signal.connect(payment_events.append)
        self.listener.product_sync_required.connect(product_events.append)

        payment = {"type": "PAYMENT_STATUS", "status": "APPROVED"}
        product = {"type": "PRODUCT_SYNC_REQUIRED", "productId": "product-1"}
        self.listener.route_message(payment)
        self.listener.route_message(product)

        self.assertEqual([payment], payment_events)
        self.assertEqual([product], product_events)

    def test_connection_and_reconnection_both_request_sync(self):
        origins = []
        self.listener.sync_requested.connect(origins.append)

        self.listener._notify_connected()
        self.listener._notify_connected()

        self.assertEqual(["WEBSOCKET_CONNECTED", "WEBSOCKET_RECONNECT"], origins)

    def test_reset_event_only_requests_authoritative_http_confirmation(self):
        reset_events = []
        lifecycle_checks = []
        self.listener.factory_reset_required.connect(reset_events.append)
        self.listener.lifecycle_check_requested.connect(lifecycle_checks.append)

        event = {
            "type": "TERMINAL_FACTORY_RESET_REQUIRED",
            "state": "RESET_REQUIRED",
        }
        self.listener.route_message(event)
        self.listener._notify_connected()

        self.assertEqual([event], reset_events)
        self.assertEqual(["WEBSOCKET_CONNECTED"], lifecycle_checks)

    def test_unauthorized_payment_socket_stops_reconnect_loop(self):
        error = RuntimeError("unauthorized")
        error.status_code = 401
        self.assertTrue(self.listener._is_auth_failure(error))


class FakeSocket:
    def __init__(self):
        self.pings = 0

    def ping(self):
        self.pings += 1


class PaymentSocketLivenessTest(unittest.TestCase):
    """BUG-049: conexão meio-aberta precisa ser detectada e reconectada."""

    def setUp(self):
        terminal = Terminal.from_dict({
            "terminalId": "terminal-a", "ativo": True, "activated": True,
        })
        with patch("app247_terminal.services.payment_listener.Terminal.load", return_value=terminal):
            self.listener = PaymentListener()
        self.now = 1000.0
        self.listener._clock = lambda: self.now
        self.listener.ws = FakeSocket()
        self.listener._mark_alive()

    def tearDown(self):
        self.listener.is_running = False

    def test_quiet_connection_sends_single_ping_after_interval(self):
        self.now += PaymentListener.PING_INTERVAL_SECONDS - 1
        self.listener._check_liveness()
        self.assertEqual(0, self.listener.ws.pings)

        self.now += 1
        self.listener._check_liveness()
        self.now += 5
        self.listener._check_liveness()
        self.assertEqual(1, self.listener.ws.pings)

    def test_missing_pong_marks_connection_stale(self):
        self.now += PaymentListener.PING_INTERVAL_SECONDS
        self.listener._check_liveness()

        self.now += PaymentListener.PONG_TIMEOUT_SECONDS + 1
        with self.assertRaises(PaymentSocketStale):
            self.listener._check_liveness()

    def test_pong_keeps_connection_alive(self):
        self.now += PaymentListener.PING_INTERVAL_SECONDS
        self.listener._check_liveness()
        self.now += 2
        self.listener._handle_frame(ABNF.OPCODE_PONG, b"")

        self.now += PaymentListener.PONG_TIMEOUT_SECONDS + 1
        self.listener._check_liveness()
        self.assertEqual(1, self.listener.ws.pings)

    def test_event_counts_as_traffic_and_is_routed(self):
        events = []
        self.listener.payment_status_signal.connect(events.append)
        self.now += PaymentListener.PING_INTERVAL_SECONDS - 1
        self.listener._handle_frame(
            ABNF.OPCODE_TEXT, b'{"type": "PAYMENT_STATUS", "status": "APPROVED"}'
        )

        self.now += PaymentListener.PING_INTERVAL_SECONDS - 1
        self.listener._check_liveness()
        self.assertEqual(0, self.listener.ws.pings)
        self.assertEqual([{"type": "PAYMENT_STATUS", "status": "APPROVED"}], events)

    def test_invalid_json_is_ignored_without_dropping_connection(self):
        self.listener._handle_frame(ABNF.OPCODE_TEXT, b"{nao-json")
        self.listener._handle_frame(ABNF.OPCODE_TEXT, b"\xff\xfe")

    def test_server_close_frame_forces_reconnect(self):
        with self.assertRaises(ConnectionError):
            self.listener._handle_frame(ABNF.OPCODE_CLOSE, b"")


if __name__ == "__main__":
    unittest.main()
