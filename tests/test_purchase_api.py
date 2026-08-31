import unittest
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtTest import QSignalSpy
from PyQt5.QtWidgets import QApplication

from service.PurchaseApi import (
    PointCheckoutWorker,
    PurchaseApi,
    PurchaseApiError,
)


class FakeResponse:
    def __init__(self, data=None, content=b"png"):
        self._data = data
        self.content = content
        self.status_code = 200

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

    def test_status_query_is_correlated_by_order_and_terminal(self):
        http = FakeSession([FakeResponse({"orderId": "order-1", "status": "APPROVED"})])
        PurchaseApi("http://backend", http).get_order("order-1", "terminal-1")
        method, url, kwargs = http.calls[0]
        self.assertEqual("GET", method)
        self.assertTrue(url.endswith("/order/order-1/status"))
        self.assertEqual({"terminalId": "terminal-1"}, kwargs["params"])

    def test_point_worker_emits_timeout_and_always_finishes(self):
        class TimeoutApi:
            def start_point(self, _payload):
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
            def start_point(self, _payload):
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
