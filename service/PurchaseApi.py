import logging
import re

import requests
from PyQt5.QtCore import QThread, pyqtSignal

from config import (
    API_URL,
    PAYMENT_CONNECT_TIMEOUT_SECONDS,
    PAYMENT_READ_TIMEOUT_SECONDS,
    RECEIPT_CONNECT_TIMEOUT_SECONDS,
    RECEIPT_READ_TIMEOUT_SECONDS,
)
from service.BackendClient import BackendClient, BackendHttpError
from service.TerminalAuth import TerminalCredentialMissing


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
    RECEIPT_TIMEOUT = (
        RECEIPT_CONNECT_TIMEOUT_SECONDS, RECEIPT_READ_TIMEOUT_SECONDS
    )
    DOMAIN_MESSAGES = {
        "ACTIVE_PAYMENT_ATTEMPT_EXISTS": "Existe um pagamento em andamento.",
        "PAYMENT_ALREADY_ACTIVE": "Existe um pagamento em andamento.",
        "ORDER_PRICE_NOT_FINALIZED": "O valor da compra ainda nao foi finalizado.",
        "PURCHASE_NOT_FOUND": "Compra nao encontrada.",
        "COUPON_MINIMUM_NOT_REACHED": "O valor minimo do cupom nao foi atingido.",
        "TERMINAL_UNAUTHORIZED": "Terminal precisa ser reprovisionado.",
        "TERMINAL_DISABLED": "Terminal desativado pelo administrador.",
    }

    def __init__(
        self, base_url=API_URL, session=None, terminal_id=None,
        credential_store=None,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.http = session or requests.Session()
        self.client = BackendClient(
            self.base_url, self.http, credential_store=credential_store
        )
        self.terminal_id = str(terminal_id) if terminal_id else None

    def _request_json(self, method, path, stage, ambiguous=False, **kwargs):
        if not self.base_url:
            raise PurchaseApiError("Servidor não configurado", stage)
        try:
            terminal_id = kwargs.pop("terminal_id", None) or self.terminal_id
            logger.info("[PAYMENT-HTTP] enviando request para backend method=%s path=%s", method, path)
            timeout = kwargs.pop("timeout", self.TIMEOUT)
            response = self.client.request(
                method,
                path,
                terminal_id=terminal_id,
                timeout=timeout,
                expected=(200, 201, 202, 204),
                **kwargs,
            )
            logger.info("[PAYMENT-HTTP] backend respondeu status=%s path=%s",
                        getattr(response, "status_code", "unknown"), path)
            if getattr(response, "status_code", 200) == 204:
                return None
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
        except BackendHttpError as error:
            payload = error.payload
            if error.status == 409 and error.code == "PRICE_CHANGED":
                raise PurchaseApiError(
                    str(error), "price_changed", False, payload
                ) from error
            if error.status == 409 and error.code in {
                "PAYMENT_ALREADY_ACTIVE", "ACTIVE_PAYMENT_ATTEMPT_EXISTS",
            }:
                raise PurchaseApiError(
                    "Existe um pagamento em andamento. Verificando o status.",
                    "payment_active", True, payload,
                ) from error
            if error.status == 409 and error.code == "ORDER_PRICE_NOT_FINALIZED":
                raise PurchaseApiError(
                    "O valor da compra ainda nao foi finalizado pelo servidor.",
                    "price_not_finalized", False, payload,
                ) from error
            if error.authentication_failed:
                raise PurchaseApiError(
                    "Terminal precisa ser reprovisionado pelo administrador.",
                    "device_auth", ambiguous, {
                        "status": 401, "code": error.code or "TERMINAL_UNAUTHORIZED",
                    },
                ) from error
            if error.forbidden:
                raise PurchaseApiError(
                    "Terminal sem permissao para esta operacao.",
                    "device_forbidden", ambiguous, {
                        "status": 403, "code": error.code,
                    },
                ) from error
            raise PurchaseApiError(
                self.DOMAIN_MESSAGES.get(error.code, str(error)),
                stage, ambiguous, {
                    "status": error.status, "code": error.code,
                },
            ) from error
        except TerminalCredentialMissing as error:
            logger.error("[SECURITY] credencial do Terminal ausente; request bloqueado")
            raise PurchaseApiError(
                "Terminal sem credencial de dispositivo", "device_auth"
            ) from error
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

    def ensure_cart(self, cart_payload, existing_cart_id=None):
        self.terminal_id = str(cart_payload.get("terminalId") or "") or self.terminal_id
        if existing_cart_id:
            cart = self._request_json(
                "PUT", f"/carrinho/{existing_cart_id}", "cart",
                json=cart_payload,
            )
        elif cart_payload.get("items"):
            cart = self._request_json("POST", "/carrinho", "cart", json=cart_payload)
        else:
            cart = self._request_json("POST", "/carrinho/empty", "cart")
        cart_id = cart.get("carrinhoId")
        if not cart_id:
            raise PurchaseApiError("Carrinho sem identificador", "cart")
        return str(cart_id)

    def start_point(self, cart_payload, on_cart_created=None, existing_cart_id=None):
        cart_id = self.ensure_cart(cart_payload, existing_cart_id)
        if on_cart_created is not None:
            on_cart_created(str(cart_id))

        try:
            point_result = self._request_json(
                "POST", f"/pagamento/terminal/{cart_id}", "payment", ambiguous=True
            )
        except PurchaseApiError as error:
            # Em PAYMENT_ALREADY_ACTIVE, cartId pertence à tentativa anterior e
            # é autoritativo. Preserve-o e registre o carrinho desta request em
            # outro campo apenas para correlação/diagnóstico.
            error.context = {
                "requestedCartId": str(cart_id),
                **error.context,
            }
            raise
        if not isinstance(point_result, dict) or not point_result.get("orderId"):
            raise PurchaseApiError(
                "Pagamento sem identificador do pedido", "payment", True,
                {"cartId": cart_id}
            )
        point_result["cartId"] = cart_id
        return point_result

    def link_customer(self, token, cart_payload, cart_id=None):
        resolved_cart_id = self.ensure_cart(cart_payload, cart_id)
        result = self._request_json(
            "POST", "/terminal/customer-link/consume", "customer_link",
            json={"cartId": resolved_cart_id, "token": str(token)},
        )
        if not isinstance(result, dict) or not result.get("linked"):
            raise PurchaseApiError("Resposta inválida ao identificar cliente", "customer_link")
        result["cartId"] = resolved_cart_id
        return result

    def get_cart(self, cart_id):
        result = self._request_json("GET", f"/carrinho/{cart_id}", "cart_recovery")
        return result if isinstance(result, dict) else None

    def get_order(self, order_id, terminal_id):
        return self._request_json(
            "GET", f"/order/{order_id}/status", "status",
            params={"terminalId": terminal_id}, terminal_id=terminal_id
        )

    def get_active_payment(self, terminal_id):
        return self._request_json(
            "GET", f"/pagamento/terminal/{terminal_id}/ativo", "active_payment",
            terminal_id=terminal_id,
        )

    def cancel_point(self, order_id, terminal_id):
        result = self._request_json(
            "POST", f"/pagamento/terminal/order/{order_id}/cancelamento",
            "payment_cancel", ambiguous=True,
            params={"terminalId": str(terminal_id)},
            terminal_id=terminal_id,
        )
        if not isinstance(result, dict) or str(result.get("orderId")) != str(order_id):
            raise PurchaseApiError(
                "Resposta inválida ao cancelar a compra", "payment_cancel", True
            )
        return result

    @staticmethod
    def normalize_receipt_destination(channel, destination):
        """Normaliza somente os formatos aceitos pelo contrato Spring."""
        normalized_channel = str(channel or "").strip().upper()
        candidate = str(destination or "").strip()
        if normalized_channel == "WHATSAPP":
            digits = "".join(character for character in candidate if character.isdigit())
            if len(digits) in (10, 11):
                digits = "55" + digits
            if not digits.startswith("55") or len(digits) not in (12, 13):
                raise PurchaseApiError(
                    "Digite um número de WhatsApp válido.", "receipt_validation"
                )
            return digits
        if normalized_channel == "EMAIL":
            email = candidate.lower()
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                raise PurchaseApiError(
                    "Digite um e-mail válido.", "receipt_validation"
                )
            return email
        raise PurchaseApiError(
            "Canal de comprovante inválido.", "receipt_validation"
        )

    def send_receipt(self, order_id, terminal_id, channel, destination):
        normalized_channel = str(channel or "").strip().upper()
        normalized_destination = self.normalize_receipt_destination(
            normalized_channel, destination
        )
        payload = {
            "terminalId": str(terminal_id),
            "pedidoId": str(order_id),
            "tipoEnvio": normalized_channel,
            "destinatario": normalized_destination,
        }
        result = self._request_json(
            "POST", "/comprovante", "receipt", json=payload,
            timeout=self.RECEIPT_TIMEOUT,
            terminal_id=terminal_id,
        )
        if not isinstance(result, dict):
            raise PurchaseApiError("Resposta inválida do servidor", "receipt")
        status = str(result.get("status") or "").strip().upper()
        if status not in {"ENVIADO", "JA_ENVIADO"}:
            raise PurchaseApiError("Resposta inválida do servidor", "receipt")
        if str(result.get("pedido")) != str(order_id):
            raise PurchaseApiError("Resposta de outra compra", "receipt")
        if str(result.get("tipoEnvio") or "").strip().upper() != normalized_channel:
            raise PurchaseApiError("Resposta de outro canal", "receipt")
        return result

    def resume_point(self, cart_id, terminal_id=None):
        result = self._request_json(
            "POST", f"/pagamento/terminal/{cart_id}", "payment", ambiguous=True,
            terminal_id=terminal_id,
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
            response = self.client.request(
                "GET",
                "/checkout/qrcode",
                params={"id": session_id},
                timeout=self.TIMEOUT,
                terminal_id=self.terminal_id,
            )
        except (requests.RequestException, BackendHttpError) as error:
            raise PurchaseApiError("Não foi possível gerar o QR Code", "qrcode") from error
        return {"cartId": cart_id, "sessionId": session_id, "image": response.content}


class PointCheckoutWorker(QThread):
    succeeded = pyqtSignal(dict)
    cart_created = pyqtSignal(dict)
    failed = pyqtSignal(str, str, bool, dict)
    timed_out = pyqtSignal(str, str, bool, dict)

    def __init__(self, payload, api_factory=PurchaseApi,
                 existing_cart_id=None,
                 cart_checkpoint=None, parent=None):
        super().__init__(parent)
        self.payload = payload
        self.api_factory = api_factory
        self.existing_cart_id = existing_cart_id
        self.cart_checkpoint = cart_checkpoint
        self.outcome_emitted = False

    def run(self):
        logger.info("[PAYMENT-UI] worker iniciado")
        try:
            api = self.api_factory()
            if self.existing_cart_id:
                result = api.start_point(
                    self.payload, self._checkpoint_cart, self.existing_cart_id
                )
            else:
                result = api.start_point(self.payload, self._checkpoint_cart)
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

    def _checkpoint_cart(self, cart_id):
        if self.cart_checkpoint is not None:
            accepted = self.cart_checkpoint(cart_id)
            if accepted is False:
                raise PurchaseApiError(
                    "Tentativa local não está mais ativa", "cart", False
                )
        self.cart_created.emit({"cartId": str(cart_id)})


class CustomerLinkWorker(QThread):
    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str, str)

    def __init__(self, token, cart_payload, cart_id=None,
                 api_factory=PurchaseApi, parent=None):
        super().__init__(parent)
        self.token = token
        self.cart_payload = cart_payload
        self.cart_id = cart_id
        self.api_factory = api_factory

    def run(self):
        try:
            result = self.api_factory().link_customer(
                self.token, self.cart_payload, self.cart_id
            )
            if not self.isInterruptionRequested():
                self.succeeded.emit(result)
        except PurchaseApiError as error:
            code = str(error.context.get("code") or "CUSTOMER_LINK_FAILED")
            if not self.isInterruptionRequested():
                self.failed.emit(code, str(error))
        except Exception:
            logger.exception("[CUSTOMER-LINK] falha inesperada sem registrar token")
            if not self.isInterruptionRequested():
                self.failed.emit("CUSTOMER_LINK_FAILED", "Não foi possível identificar o cliente")
        finally:
            self.token = None


class CustomerLinkRecoveryWorker(QThread):
    succeeded = pyqtSignal(dict)
    failed = pyqtSignal()

    def __init__(self, cart_id, api_factory=PurchaseApi, parent=None):
        super().__init__(parent)
        self.cart_id = cart_id
        self.api_factory = api_factory

    def run(self):
        try:
            result = self.api_factory().get_cart(self.cart_id)
            if result and result.get("customerLinked") and not self.isInterruptionRequested():
                self.succeeded.emit(result)
            elif not self.isInterruptionRequested():
                self.failed.emit()
        except Exception:
            if not self.isInterruptionRequested():
                self.failed.emit()


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
    failed = pyqtSignal(str, dict)

    def __init__(self, cart_id, terminal_id=None, api_factory=PurchaseApi, parent=None):
        super().__init__(parent)
        self.cart_id = cart_id
        self.terminal_id = terminal_id
        self.api_factory = api_factory

    def run(self):
        try:
            result = self.api_factory().resume_point(
                self.cart_id, self.terminal_id
            )
            if not self.isInterruptionRequested():
                self.succeeded.emit(result)
        except PurchaseApiError as error:
            if not self.isInterruptionRequested():
                self.failed.emit(str(error), error.context)
        except Exception:
            logger.exception("[PAYMENT-WORKER] retomada exception não prevista")
            if not self.isInterruptionRequested():
                self.failed.emit("Não foi possível verificar o início do pagamento", {})
        finally:
            logger.info("[PAYMENT-WORKER] retomada finished emitido")


class ActivePaymentRecoveryWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, terminal_id, api_factory=PurchaseApi, parent=None):
        super().__init__(parent)
        self.terminal_id = terminal_id
        self.api_factory = api_factory

    def run(self):
        try:
            result = self.api_factory().get_active_payment(self.terminal_id)
            if not self.isInterruptionRequested():
                self.succeeded.emit(result)
        except PurchaseApiError as error:
            if not self.isInterruptionRequested():
                self.failed.emit(str(error))
        except Exception:
            logger.exception("[PAYMENT-WORKER] recovery exception não prevista")
            if not self.isInterruptionRequested():
                self.failed.emit("Não foi possível recuperar o pagamento")


class PointCancelWorker(QThread):
    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, order_id, terminal_id, api_factory=PurchaseApi, parent=None):
        super().__init__(parent)
        self.order_id = str(order_id)
        self.terminal_id = str(terminal_id)
        self.api_factory = api_factory

    def run(self):
        try:
            result = self.api_factory().cancel_point(
                self.order_id, self.terminal_id
            )
            if not self.isInterruptionRequested():
                self.succeeded.emit(result)
        except PurchaseApiError as error:
            logger.warning(
                "[PAYMENT-WORKER] cancelamento inconclusivo orderId=%s stage=%s",
                self.order_id, error.stage,
            )
            if not self.isInterruptionRequested():
                self.failed.emit(str(error))
        except Exception:
            logger.exception(
                "[PAYMENT-WORKER] cancelamento exception não prevista orderId=%s",
                self.order_id,
            )
            if not self.isInterruptionRequested():
                self.failed.emit("Não foi possível confirmar o cancelamento")


class ReceiptSendWorker(QThread):
    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str, str)

    def __init__(self, order_id, terminal_id, channel, destination,
                 api_factory=PurchaseApi, parent=None):
        super().__init__(parent)
        self.order_id = str(order_id)
        self.terminal_id = str(terminal_id)
        self.channel = str(channel).upper()
        self.destination = destination
        self.api_factory = api_factory

    def run(self):
        try:
            result = self.api_factory().send_receipt(
                self.order_id, self.terminal_id, self.channel, self.destination
            )
            if not self.isInterruptionRequested():
                self.succeeded.emit(result)
        except PurchaseApiError as error:
            logger.warning(
                "[RECEIPT-WORKER] envio falhou orderId=%s canal=%s stage=%s",
                self.order_id, self.channel, error.stage,
            )
            if not self.isInterruptionRequested():
                self.failed.emit(
                    "Não foi possível enviar o comprovante. Tente novamente.",
                    error.stage,
                )
        except Exception as error:
            logger.exception(
                "[RECEIPT-WORKER] falha inesperada orderId=%s canal=%s",
                self.order_id, self.channel,
            )
            if not self.isInterruptionRequested():
                self.failed.emit(
                    "Não foi possível enviar o comprovante. Tente novamente.",
                    error.__class__.__name__,
                )


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
