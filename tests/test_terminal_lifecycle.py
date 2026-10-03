import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from app247_terminal.services.factory_reset import FactoryResetService
from app247_terminal.services.terminal_lifecycle import TerminalLifecycleApi, TerminalResetPolicy


class Response:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class TerminalLifecycleApiTest(unittest.TestCase):
    def setUp(self):
        self.credential_patch = patch(
            "app247_terminal.services.terminal_auth.TerminalCredentialStore.load",
            return_value="tdc_test_lifecycle",
        )
        self.credential_patch.start()

    def tearDown(self):
        self.credential_patch.stop()

    def test_explicit_reset_required_from_http_is_authoritative(self):
        http = Mock()
        http.get.return_value = Response(200, {
            "terminalId": "terminal-a",
            "state": "RESET_REQUIRED",
            "reason": "COMPANY_CLOSED",
        })

        result = TerminalLifecycleApi("http://backend", http).check("terminal-a")

        self.assertEqual("RESET_REQUIRED", result["state"])

    def test_timeout_never_becomes_factory_reset(self):
        http = Mock()
        http.get.side_effect = requests.Timeout("offline")

        result = TerminalLifecycleApi("http://backend", http).check("terminal-a")

        self.assertIsNone(result)

    def test_http_500_never_becomes_factory_reset(self):
        http = Mock()
        http.get.return_value = Response(500, {"state": "RESET_REQUIRED"})

        result = TerminalLifecycleApi("http://backend", http).check("terminal-a")

        self.assertIsNone(result)

    def test_invalid_or_unknown_response_never_becomes_factory_reset(self):
        http = Mock()
        api = TerminalLifecycleApi("http://backend", http)
        http.get.return_value = Response(200, ValueError("invalid json"))
        self.assertIsNone(api.check("terminal-a"))
        http.get.return_value = Response(200, {"state": "SOMETHING_ELSE"})
        self.assertIsNone(api.check("terminal-a"))

    def test_completion_receipt_is_retained_until_backend_acknowledges(self):
        with tempfile.TemporaryDirectory() as directory:
            reset = FactoryResetService(directory)
            reset.request_reset("terminal-a", "COMPANY_CLOSED", remote=True)
            reset.apply_pending()
            http = Mock()
            http.post.return_value = Response(500)
            api = TerminalLifecycleApi("http://backend", http, reset_service=reset)

            self.assertFalse(api.confirm_pending_reset())
            self.assertIsNotNone(reset.pending_completion())

            http.post.return_value = Response(204)
            self.assertTrue(api.confirm_pending_reset())
            self.assertIsNone(reset.pending_completion())

    def test_payment_in_progress_defers_reset_until_reconciliation(self):
        unresolved = SimpleNamespace(
            payment_in_flight=True, order_id="order-a", cart_id="cart-a",
            state="RECONCILIATION_PENDING",
        )
        idle = SimpleNamespace(
            payment_in_flight=False, order_id=None, cart_id=None, state="IDLE",
        )

        self.assertTrue(TerminalResetPolicy.has_unresolved_payment(unresolved))
        self.assertFalse(TerminalResetPolicy.has_unresolved_payment(idle))

    def test_pending_processing_unknown_and_cancelling_block_reset(self):
        for state in ("PENDING", "PROCESSING", "UNKNOWN", "CANCELLING"):
            with self.subTest(state=state):
                session = SimpleNamespace(
                    payment_in_flight=True,
                    order_id="order-a",
                    cart_id="cart-a",
                    state=state,
                )
                self.assertTrue(
                    TerminalResetPolicy.has_unresolved_payment(session)
                )

    def test_approved_and_finalized_session_allows_reset(self):
        finalized = SimpleNamespace(
            payment_in_flight=False,
            order_id=None,
            cart_id=None,
            state="IDLE",
        )
        self.assertFalse(TerminalResetPolicy.has_unresolved_payment(finalized))


if __name__ == "__main__":
    unittest.main()
