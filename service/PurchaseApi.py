import logging

import requests
from PyQt5.QtCore import QThread, pyqtSignal

from config import (
    API_URL,
    PAYMENT_CONNECT_TIMEOUT_SECONDS,
    PAYMENT_READ_TIMEOUT_SECONDS,
)


logger = logging.getLogger(__name__)


class PurchaseApiError(RuntimeError):
    def __init__(self, message, stage, ambiguous=False, context=None, timed_out=False):
        super().__init__(message)
        self.stage = stage
        self.ambiguous = ambiguous
        self.context = context or {}
        self.timed_out = bool(timed_out)


class PurchaseApi:
    TIMEOUT = (PAYMENT_CONNECT_TIMEOUT_SECONDS, PAYMENT_READ_TIMEOUT_SECONDS)

    def __init__(self, base_url=API_URL, session=None):
        self.base_url = (base_url or "").rstrip("/")
        self.http = session or requests.Session()

    def _request_json(self, method, path, stage, ambiguous=False, **kwargs):
        if not self.base_url:
            raise PurchaseApiError("Servidor não configurado", stage)
        try:
            logger.info("[PAYMENT-HTTP] enviando request para backend method=%s path=%s", method, path)
            response = self.http.request(
                method, f"{self.base_url}{path}", timeout=self.TIMEOUT, **kwargs
            )
            logger.info("[PAYMENT-HTTP] backend respondeu status=%s path=%s",
                        getattr(response, "status_code", "unknown"), path)
            if getattr(response, "status_code", 200) == 409:
                try:
                    payload = response.json()
                except ValueError:
                    payload = {}
                if payload.get("code") == "PRICE_CHANGED":
                    raise PurchaseApiError(
                        payload.get("message") or "O preço da compra foi atualizado",
                        "price_changed", False, payload
                    )
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError as error:
                logger.warning("[PAYMENT-HTTP] JSON inesperado status=%s path=%s",
                               getattr(response, "status_code", "unknown"), path)
                raise PurchaseApiError(
                    "Resposta inválida do servidor", stage, ambiguous
                ) from error
            logger.info("[PAYMENT-HTTP] resposta parseada path=%s", path)
            return payload
        except PurchaseApiError:
            raise
        except requests.Timeout as error:
            logger.warning("[PAYMENT-HTTP] timeout path=%s", path)
            raise PurchaseApiError(
                "Tempo de resposta excedido", stage, ambiguous, timed_out=True
            ) from error
        except requests.RequestException as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            logger.warning("[PAYMENT-HTTP] falha status=%s path=%s errorType=%s",
                           status, path, error.__class__.__name__)
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
            error.context = {**error.context, "cartId": cart_id}
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
    timed_out = pyqtSignal(str, str, bool, dict)

    def __init__(self, payload, api_factory=PurchaseApi, parent=None):
        super().__init__(parent)
        self.payload = payload
        self.api_factory = api_factory
        self.outcome_emitted = False

    def run(self):
        logger.info("[PAYMENT-UI] worker iniciado")
        try:
            result = self.api_factory().start_point(self.payload)
            if not self.isInterruptionRequested():
                self.outcome_emitted = True
                logger.info("[PAYMENT-WORKER] success emitido")
                self.succeeded.emit(result)
        except PurchaseApiError as error:
            if not self.isInterruptionRequested():
                self.outcome_emitted = True
                if error.timed_out:
                    logger.warning("[PAYMENT-WORKER] timeout emitido stage=%s", error.stage)
                    self.timed_out.emit(
                        str(error), error.stage, error.ambiguous, error.context
                    )
                else:
                    logger.warning("[PAYMENT-WORKER] error emitido stage=%s", error.stage)
                    self.failed.emit(
                        str(error), error.stage, error.ambiguous, error.context
                    )
        except Exception:
            logger.exception("[PAYMENT-WORKER] exception não prevista")
            if not self.isInterruptionRequested():
                self.outcome_emitted = True
                logger.warning("[PAYMENT-WORKER] error emitido stage=unknown")
                self.failed.emit("Não foi possível preparar o pagamento", "unknown", False, {})
        finally:
            logger.info("[PAYMENT-WORKER] finished emitido")


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
            if not self.isInterruptionRequested():
                self.failed.emit(str(error))
        except Exception:
            logger.exception("[PAYMENT-WORKER] status exception não prevista")
            if not self.isInterruptionRequested():
                self.failed.emit("Não foi possível verificar o pagamento")
        finally:
            logger.info("[PAYMENT-WORKER] status finished emitido")


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
            if not self.isInterruptionRequested():
                self.failed.emit(str(error))
        except Exception:
            logger.exception("[PAYMENT-WORKER] retomada exception não prevista")
            if not self.isInterruptionRequested():
                self.failed.emit("Não foi possível verificar o início do pagamento")
        finally:
            logger.info("[PAYMENT-WORKER] retomada finished emitido")


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
            if not self.isInterruptionRequested():
                self.failed.emit(str(error))
        except Exception:
            logger.exception("[PAYMENT-WORKER] checkout app exception não prevista")
            if not self.isInterruptionRequested():
                self.failed.emit("Não foi possível preparar o checkout")
        finally:
            logger.info("[PAYMENT-WORKER] checkout app finished emitido")
