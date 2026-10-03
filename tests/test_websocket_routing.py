import unittest
from unittest.mock import patch

from app247_terminal.services.payment_listener import PaymentListener
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


if __name__ == "__main__":
    unittest.main()
