import unittest
from unittest.mock import patch

from database.PaymentListener import PaymentListener
from model.Terminal import Terminal


class WebSocketRoutingTest(unittest.TestCase):
    def setUp(self):
        terminal = Terminal.from_dict({
            "terminalId": "terminal-a", "ativo": True, "activated": True,
        })
        with patch("database.PaymentListener.Terminal.load", return_value=terminal):
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


if __name__ == "__main__":
    unittest.main()
