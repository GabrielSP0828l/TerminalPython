import requests
from PyQt5.QtCore import QThread, pyqtSignal

from config import API_URL


class PurchaseApiError(RuntimeError):
    def __init__(self, message, stage, ambiguous=False, context=None):
        super().__init__(message)
        self.stage = stage
        self.ambiguous = ambiguous
        self.context = context or {}


class PurchaseApi:
    TIMEOUT = (5, 20)

    def __init__(self, base_url=API_URL, session=None):
        self.base_url = (base_url or "").rstrip("/")
        self.http = session or requests.Session()

    def _request_json(self, method, path, stage, ambiguous=False, **kwargs):
        if not self.base_url:
            raise PurchaseApiError("Servidor não configurado", stage)
        try:
            response = self.http.request(
                method, f"{self.base_url}{path}", timeout=self.TIMEOUT, **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.Timeout as error:
            raise PurchaseApiError("Tempo de resposta excedido", stage, ambiguous) from error
        except (requests.RequestException, ValueError) as error:
            raise PurchaseApiError("Falha de comunicação com o servidor", stage, ambiguous) from error

    def start_point(self, cart_payload):
        cart = self._request_json("POST", "/carrinho", "cart", json=cart_payload)
        cart_id = cart.get("carrinhoId")
        if not cart_id:
            raise PurchaseApiError("Carrinho sem identificador", "cart")

        try:
            point_result = self._request_json(
                "POST", f"/pagamento/terminal/{cart_id}", "payment", ambiguous=True
            )
        except PurchaseApiError as error:
            error.context = {"cartId": cart_id}
            raise
        if not isinstance(point_result, dict) or not point_result.get("orderId"):
            raise PurchaseApiError(
                "Pagamento sem identificador do pedido", "payment", True,
                {"cartId": cart_id}
            )
        point_result["cartId"] = cart_id
        return point_result

    def get_order(self, order_id, terminal_id):
        return self._request_json(
            "GET", f"/order/{order_id}/status", "status",
            params={"terminalId": terminal_id}
        )

    def resume_point(self, cart_id):
        result = self._request_json(
            "POST", f"/pagamento/terminal/{cart_id}", "payment", ambiguous=True
        )
        if not isinstance(result, dict) or not result.get("orderId"):
            raise PurchaseApiError("Pagamento sem identificador do pedido", "payment", True)
        result["cartId"] = cart_id
        return result

    def create_app_checkout(self, cart_payload):
        cart = self._request_json("POST", "/carrinho", "cart", json=cart_payload)
        cart_id = cart.get("carrinhoId")
        checkout = self._request_json(
            "GET", "/checkout/carrinho", "checkout", params={"idCarrinho": cart_id}
        )
        session_id = checkout.get("sessionId")
        if not session_id:
            raise PurchaseApiError("Checkout sem identificador", "checkout")
        try:
            response = self.http.get(
                f"{self.base_url}/checkout/qrcode",
                params={"id": session_id},
                timeout=self.TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise PurchaseApiError("Não foi possível gerar o QR Code", "qrcode") from error
        return {"cartId": cart_id, "sessionId": session_id, "image": response.content}


class PointCheckoutWorker(QThread):
    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str, str, bool, dict)

    def __init__(self, payload, api_factory=PurchaseApi, parent=None):
        super().__init__(parent)
        self.payload = payload
        self.api_factory = api_factory

    def run(self):
        try:
            result = self.api_factory().start_point(self.payload)
            if not self.isInterruptionRequested():
                self.succeeded.emit(result)
        except PurchaseApiError as error:
            self.failed.emit(str(error), error.stage, error.ambiguous, error.context)
        except Exception:
            self.failed.emit("Não foi possível preparar o pagamento", "unknown", False, {})


class OrderStatusWorker(QThread):
    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, order_id, terminal_id, api_factory=PurchaseApi, parent=None):
        super().__init__(parent)
        self.order_id = order_id
        self.terminal_id = terminal_id
        self.api_factory = api_factory

    def run(self):
        try:
            result = self.api_factory().get_order(self.order_id, self.terminal_id)
            if not self.isInterruptionRequested():
                self.succeeded.emit(result)
        except PurchaseApiError as error:
            self.failed.emit(str(error))


class PointResumeWorker(QThread):
    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, cart_id, api_factory=PurchaseApi, parent=None):
        super().__init__(parent)
        self.cart_id = cart_id
        self.api_factory = api_factory

    def run(self):
        try:
            result = self.api_factory().resume_point(self.cart_id)
            if not self.isInterruptionRequested():
                self.succeeded.emit(result)
        except PurchaseApiError as error:
            self.failed.emit(str(error))


class AppCheckoutWorker(QThread):
    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, payload, api_factory=PurchaseApi, parent=None):
        super().__init__(parent)
        self.payload = payload
        self.api_factory = api_factory

    def run(self):
        try:
            result = self.api_factory().create_app_checkout(self.payload)
            if not self.isInterruptionRequested():
                self.succeeded.emit(result)
        except PurchaseApiError as error:
            self.failed.emit(str(error))
