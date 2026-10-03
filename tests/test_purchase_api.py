import unittest
import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtTest import QSignalSpy
from PyQt5.QtWidgets import QApplication

from app247_terminal.services.purchase_api import (
    PointCancelWorker,
    PointCheckoutWorker,
    PurchaseApi,
    PurchaseApiError,
    ReceiptSendWorker,
)


class FakeResponse:
    def __init__(self, data=None, content=b"png", status_code=200):
        self._data = data
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.responses.pop(0)


class PurchaseApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.credential_patch = patch(
            "app247_terminal.services.terminal_auth.TerminalCredentialStore.load",
            return_value="tdc_test_payment",
        )
        self.credential_patch.start()

    def tearDown(self):
        self.credential_patch.stop()

    def test_point_uses_current_backend_contract(self):
        http = FakeSession([
            FakeResponse({"carrinhoId": "cart-1"}),
            FakeResponse({
                "type": "PAYMENT_STATUS", "orderId": "order-1",
                "terminalId": "terminal-1", "status": "WAITING_PAYMENT"
            }),
        ])
        result = PurchaseApi("http://backend", http).start_point({"items": []})
        self.assertEqual("order-1", result["orderId"])
        self.assertEqual("cart-1", result["cartId"])
        self.assertEqual("POST", http.calls[0][0])
        self.assertEqual("POST", http.calls[1][0])
        self.assertTrue(http.calls[1][1].endswith("/pagamento/terminal/cart-1"))

    def test_cart_checkpoint_happens_before_financial_post(self):
        http = FakeSession([
            FakeResponse({"carrinhoId": "cart-1"}),
            FakeResponse({"orderId": "order-1", "status": "WAITING_PAYMENT"}),
        ])
        checkpoints = []

        def checkpoint(cart_id):
            checkpoints.append((cart_id, len(http.calls)))

        PurchaseApi("http://backend", http).start_point(
            {"items": []}, on_cart_created=checkpoint
        )

        self.assertEqual([("cart-1", 1)], checkpoints)
        self.assertEqual(2, len(http.calls))

    def test_customer_link_sends_only_token_and_cart_context(self):
        http = FakeSession([
            FakeResponse({"carrinhoId": "cart-1"}),
            FakeResponse({
                "linked": True, "displayName": "Jefferson", "cartId": "cart-1"
            }),
        ])
        payload = {"terminalId": "terminal-1", "items": []}
        result = PurchaseApi("http://backend", http).link_customer(
            "A" * 43, payload
        )
        self.assertTrue(result["linked"])
        method, url, kwargs = http.calls[1]
        self.assertEqual("POST", method)
        self.assertTrue(url.endswith("/terminal/customer-link/consume"))
        self.assertEqual({"cartId": "cart-1", "token": "A" * 43}, kwargs["json"])
        self.assertNotIn("terminalId", kwargs["json"])
        self.assertNotIn("userId", kwargs["json"])

    def test_linked_cart_is_updated_instead_of_recreated_before_payment(self):
        http = FakeSession([
            FakeResponse({"carrinhoId": "cart-linked"}),
            FakeResponse({"orderId": "order-1", "status": "WAITING_PAYMENT"}),
        ])
        result = PurchaseApi("http://backend", http).start_point(
            {"terminalId": "terminal-1", "items": [{"productId": "p1"}]},
            existing_cart_id="cart-linked",
        )
        self.assertEqual("cart-linked", result["cartId"])
        self.assertEqual("PUT", http.calls[0][0])
        self.assertTrue(http.calls[0][1].endswith("/carrinho/cart-linked"))

    def test_active_payment_conflict_is_structured_and_ambiguous(self):
        http = FakeSession([FakeResponse({
            "code": "PAYMENT_ALREADY_ACTIVE",
            "message": "Pagamento ativo",
            "orderId": "order-old",
            "paymentAttemptId": "attempt-old",
            "paymentStatus": "WAITING_PAYMENT",
        }, status_code=409)])

        with self.assertRaises(PurchaseApiError) as raised:
            PurchaseApi("http://backend", http).resume_point("cart-new")

        self.assertEqual("payment_active", raised.exception.stage)
        self.assertTrue(raised.exception.ambiguous)
        self.assertEqual("order-old", raised.exception.context["orderId"])

    def test_current_active_attempt_code_resumes_instead_of_retrying_charge(self):
        http = FakeSession([FakeResponse({
            "code": "ACTIVE_PAYMENT_ATTEMPT_EXISTS",
            "orderId": "order-old",
            "paymentAttemptId": "attempt-old",
        }, status_code=409)])
        with self.assertRaises(PurchaseApiError) as raised:
            PurchaseApi("http://backend", http).resume_point("cart-new")
        self.assertEqual("payment_active", raised.exception.stage)
        self.assertTrue(raised.exception.ambiguous)

    def test_401_requires_reprovision_and_403_preserves_credential(self):
        for status, expected_stage in ((401, "device_auth"), (403, "device_forbidden")):
            with self.subTest(status=status):
                http = FakeSession([FakeResponse({
                    "code": "TERMINAL_UNAUTHORIZED",
                }, status_code=status)])
                with self.assertRaises(PurchaseApiError) as raised:
                    PurchaseApi("http://backend", http).get_active_payment(
                        "terminal-a"
                    )
                self.assertEqual(expected_stage, raised.exception.stage)
                self.assertEqual(status, raised.exception.context["status"])

    def test_start_point_preserves_active_attempt_cart_on_conflict(self):
        http = FakeSession([
            FakeResponse({"carrinhoId": "cart-new"}),
            FakeResponse({
                "code": "PAYMENT_ALREADY_ACTIVE",
                "message": "Pagamento ativo",
                "orderId": "order-old",
                "cartId": "cart-old",
                "paymentAttemptId": "attempt-old",
                "paymentStatus": "WAITING_PAYMENT",
            }, status_code=409),
        ])

        with self.assertRaises(PurchaseApiError) as raised:
            PurchaseApi("http://backend", http).start_point({"items": []})

        self.assertEqual("payment_active", raised.exception.stage)
        self.assertEqual("cart-old", raised.exception.context["cartId"])
        self.assertEqual("cart-new", raised.exception.context["requestedCartId"])

    def test_active_payment_discovery_accepts_no_content(self):
        http = FakeSession([FakeResponse(status_code=204)])

        result = PurchaseApi("http://backend", http).get_active_payment("terminal-1")

        self.assertIsNone(result)
        self.assertTrue(http.calls[0][1].endswith(
            "/pagamento/terminal/terminal-1/ativo"
        ))

    def test_status_query_is_correlated_by_order_and_terminal(self):
        http = FakeSession([FakeResponse({"orderId": "order-1", "status": "APPROVED"})])
        PurchaseApi("http://backend", http).get_order("order-1", "terminal-1")
        method, url, kwargs = http.calls[0]
        self.assertEqual("GET", method)
        self.assertTrue(url.endswith("/order/order-1/status"))
        self.assertEqual({"terminalId": "terminal-1"}, kwargs["params"])

    def test_total_cancellation_uses_spring_and_correlates_response(self):
        http = FakeSession([FakeResponse({
            "orderId": "order-1", "status": "WAITING_PAYMENT",
            "cancellationRequested": True,
        })])

        result = PurchaseApi("http://backend", http).cancel_point(
            "order-1", "terminal-1"
        )

        self.assertTrue(result["cancellationRequested"])
        method, url, kwargs = http.calls[0]
        self.assertEqual("POST", method)
        self.assertTrue(url.endswith(
            "/pagamento/terminal/order/order-1/cancelamento"
        ))
        self.assertEqual({"terminalId": "terminal-1"}, kwargs["params"])

    def test_cancel_worker_reports_timeout_without_assuming_cancelled(self):
        class TimeoutApi:
            def cancel_point(self, *_args):
                raise PurchaseApiError(
                    "demorou", "payment_cancel", ambiguous=True, timed_out=True
                )

        worker = PointCancelWorker(
            "order-1", "terminal-1", api_factory=TimeoutApi
        )
        succeeded = QSignalSpy(worker.succeeded)
        failed = QSignalSpy(worker.failed)
        worker.start()
        self.assertTrue(worker.wait(1000))
        self.app.processEvents()

        self.assertEqual(0, len(succeeded))
        self.assertEqual(1, len(failed))

    def test_receipt_uses_exact_spring_contract_and_normalizes_whatsapp(self):
        http = FakeSession([FakeResponse({
            "status": "ENVIADO", "pedido": "order-1",
            "tipoEnvio": "WHATSAPP", "n8nStatus": 200, "duplicado": False,
        })])

        result = PurchaseApi("http://backend", http).send_receipt(
            "order-1", "terminal-1", "WHATSAPP", "(75) 99999-9999"
        )

        self.assertEqual("ENVIADO", result["status"])
        method, url, kwargs = http.calls[0]
        self.assertEqual("POST", method)
        self.assertTrue(url.endswith("/comprovante"))
        self.assertEqual({
            "terminalId": "terminal-1",
            "pedidoId": "order-1",
            "tipoEnvio": "WHATSAPP",
            "destinatario": "5575999999999",
        }, kwargs["json"])
        self.assertEqual(PurchaseApi.RECEIPT_TIMEOUT, kwargs["timeout"])

    def test_receipt_normalizes_email_and_rejects_invalid_destinations(self):
        self.assertEqual(
            "cliente@email.com",
            PurchaseApi.normalize_receipt_destination(
                "EMAIL", " Cliente@Email.COM "
            ),
        )
        for channel, destination in (
            ("EMAIL", "sem-arroba"), ("WHATSAPP", "123"),
        ):
            with self.subTest(channel=channel):
                with self.assertRaises(PurchaseApiError):
                    PurchaseApi.normalize_receipt_destination(channel, destination)

    def test_receipt_rejects_response_for_another_channel(self):
        http = FakeSession([FakeResponse({
            "status": "ENVIADO", "pedido": "order-1",
            "tipoEnvio": "EMAIL", "n8nStatus": 200, "duplicado": False,
        })])

        with self.assertRaises(PurchaseApiError):
            PurchaseApi("http://backend", http).send_receipt(
                "order-1", "terminal-1", "WHATSAPP", "5575999999999"
            )

    def test_receipt_worker_converts_failure_to_friendly_message(self):
        class BrokenReceiptApi:
            def send_receipt(self, *_args):
                raise PurchaseApiError("HTTP 502", "receipt")

        worker = ReceiptSendWorker(
            "order-1", "terminal-1", "EMAIL", "cliente@email.com",
            api_factory=BrokenReceiptApi,
        )
        failed = QSignalSpy(worker.failed)
        worker.start()
        self.assertTrue(worker.wait(1000))
        self.app.processEvents()

        self.assertEqual(1, len(failed))
        self.assertNotIn("502", failed[0][0])

    def test_point_worker_emits_timeout_and_always_finishes(self):
        class TimeoutApi:
            def start_point(self, _payload, _on_cart_created=None):
                raise PurchaseApiError(
                    "demorou", "payment", ambiguous=True, timed_out=True
                )

        worker = PointCheckoutWorker({}, api_factory=TimeoutApi)
        timed_out = QSignalSpy(worker.timed_out)
        finished = QSignalSpy(worker.finished)
        worker.start()
        self.assertTrue(worker.wait(1000))
        self.app.processEvents()

        self.assertEqual(1, len(timed_out))
        self.assertEqual(1, len(finished))

    def test_point_worker_converts_unexpected_exception_to_error_and_finishes(self):
        class BrokenApi:
            def start_point(self, _payload, _on_cart_created=None):
                raise RuntimeError("falha simulada")

        worker = PointCheckoutWorker({}, api_factory=BrokenApi)
        failed = QSignalSpy(worker.failed)
        finished = QSignalSpy(worker.finished)
        worker.start()
        self.assertTrue(worker.wait(1000))
        self.app.processEvents()

        self.assertEqual(1, len(failed))
        self.assertEqual(1, len(finished))


if __name__ == "__main__":
    unittest.main()
