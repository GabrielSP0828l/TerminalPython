import unittest

from service.PurchaseApi import PurchaseApi


class FakeResponse:
    def __init__(self, data=None, content=b"png"):
        self._data = data
        self.content = content

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


if __name__ == "__main__":
    unittest.main()
