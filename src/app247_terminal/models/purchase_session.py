import time
import uuid
import logging

from PyQt5.QtCore import QObject, QTimer, Qt, pyqtSignal


logger = logging.getLogger(__name__)


class CompraSession(QObject):
    SESSION_LIMIT_SECONDS = 10 * 60

    remaining_changed = pyqtSignal(int)
    expired = pyqtSignal(str)
    state_changed = pyqtSignal(str)

    INTERMEDIATE = {
        "PENDING", "CREATED", "AT_TERMINAL", "ACTION_REQUIRED",
        "PROCESSING", "WAITING_PAYMENT", "UNKNOWN", "CANCELLING",
        "CANCEL_PENDING",
    }
    APPROVED = {"APPROVED", "PAID", "PROCESSED"}
    FAILED = {"REJECTED", "FAILED", "CANCELED", "CANCELLED", "EXPIRED", "REFUNDED"}

    def __init__(self, parent=None, clock=None, duration_seconds=None,
                 payment_store=None, terminal_id_provider=None):
        super().__init__(parent)
        self._clock = clock or time.monotonic
        self.duration_seconds = int(duration_seconds or self.SESSION_LIMIT_SECONDS)
        self.payment_store = payment_store
        self.terminal_id_provider = terminal_id_provider
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self.reset(clear_persisted=False)

    def start_if_needed(self):
        if self.started_at is not None:
            return self.can_accept_checkout_actions()
        self.started_at = self._clock()
        self.generation = uuid.uuid4().hex
        self.active = True
        self._expired_emitted = False
        self._set_state("SCANNING")
        self._timer.start()
        self._emit_remaining()
        logger.info("[CHECKOUT-SESSION] iniciada duration=%ss", self.duration_seconds)
        return True

    def can_accept_checkout_actions(self):
        if self.started_at is None:
            return self.state == "IDLE"
        if self.remaining_seconds() <= 0:
            self._tick()
            return False
        return self.active

    def begin_payment(self):
        if not self.start_if_needed():
            return None
        if self.payment_in_flight or self.state in {"APPROVED", "SUCCESS", "TIMEOUT_CHECK"}:
            return None
        self.payment_in_flight = True
        self.attempt_id = uuid.uuid4().hex
        # Um carrinho pode ter sido aberto antes do pagamento para vincular o
        # cliente; nesse caso o mesmo id autoritativo deve ser reutilizado.
        self.order_id = None
        self.payment_id = None
        self.payment_attempt_id = None
        self.cancellation_requested = False
        self._set_state("STARTING_PAYMENT")
        try:
            self._persist_payment(strict=True)
        except Exception:
            logger.exception("[PAYMENT] checkpoint inicial falhou; worker não será iniciado")
            self.payment_in_flight = False
            self.attempt_id = None
            self._set_state("CART_READY")
            raise
        return self.attempt_id

    def set_remote_ids(self, cart_id=None, order_id=None, payment_id=None,
                       payment_attempt_id=None):
        if cart_id:
            self.cart_id = str(cart_id)
        if order_id:
            self.order_id = str(order_id)
        if payment_id:
            self.payment_id = str(payment_id)
        if payment_attempt_id:
            self.payment_attempt_id = str(payment_attempt_id)
        if self.payment_in_flight:
            self._persist_payment()

    def mark_waiting(self):
        if self.state not in {"APPROVED", "SUCCESS"}:
            self._set_state("WAITING_PAYMENT")
            self._persist_payment()

    def mark_cancelling(self):
        if not self.payment_in_flight or not self.order_id:
            return False
        self.cancellation_requested = True
        self._timer.stop()
        self.active = False
        self._set_state("CANCELLING")
        self._persist_payment()
        return True

    def apply_status(self, order_id, status, payment_attempt_id=None):
        normalized = str(status or "").strip().upper()
        if not self.order_id or str(order_id) != self.order_id:
            return "IGNORED"
        if (payment_attempt_id and self.payment_attempt_id
                and str(payment_attempt_id) != self.payment_attempt_id):
            logger.warning(
                "[PAYMENT] evento ignorado por tentativa divergente orderId=%s expected=%s received=%s",
                order_id, self.payment_attempt_id, payment_attempt_id,
            )
            return "IGNORED"
        if payment_attempt_id and not self.payment_attempt_id:
            self.payment_attempt_id = str(payment_attempt_id)
        self.last_status = normalized
        if normalized in self.APPROVED:
            if self.state in {"APPROVED", "SUCCESS"}:
                return "DUPLICATE_APPROVED"
            self.payment_in_flight = False
            self.cancellation_requested = False
            self._timer.stop()
            self._set_state("APPROVED")
            self._clear_persisted_payment()
            return "APPROVED"
        if normalized in self.FAILED:
            self.payment_in_flight = False
            self.cancellation_requested = False
            self._set_state("PAYMENT_FAILED")
            self._clear_persisted_payment()
            return "FAILED"
        if normalized in self.INTERMEDIATE:
            self.payment_in_flight = True
            if self.cancellation_requested:
                self._set_state("CANCELLING")
            elif self.state != "RECONCILIATION_PENDING":
                self._set_state("PROCESSING")
            self._persist_payment()
            return "PROCESSING"
        self._persist_payment()
        return "UNKNOWN"

    def prepare_retry(self):
        self.payment_in_flight = False
        self.order_id = None
        self.payment_id = None
        self.payment_attempt_id = None
        self.cancellation_requested = False
        self.attempt_id = None
        self.last_status = None
        self._clear_persisted_payment()
        if self.started_at is not None and self.remaining_seconds() > 0:
            self._set_state("CART_READY")

    def mark_timeout_check(self):
        if self.state in {"APPROVED", "SUCCESS", "IDLE", "TIMEOUT_CHECK"}:
            return False
        self._timer.stop()
        self.active = False
        self._set_state("TIMEOUT_CHECK")
        return True

    def mark_success(self):
        self._timer.stop()
        self._set_state("SUCCESS")
        logger.info("[CHECKOUT-SESSION] pagamento aprovado; timer global encerrado")

    def remaining_seconds(self):
        if self.started_at is None:
            return self.duration_seconds
        elapsed = max(0, int(self._clock() - self.started_at))
        return max(0, self.duration_seconds - elapsed)

    def mark_reconciliation_pending(self):
        self._timer.stop()
        self.payment_in_flight = True
        self._set_state(
            "CANCELLING" if self.cancellation_requested else "RECONCILIATION_PENDING"
        )
        self._persist_payment()
        logger.warning("[CHECKOUT-SESSION] timeout; reconciliação financeira pendente")

    def cancel(self):
        logger.info("[CHECKOUT-SESSION] cancelada")
        self.reset()

    def finish(self):
        logger.info("[CHECKOUT-SESSION] finalizada")
        self.reset()

    def reset(self, clear_persisted=True):
        previous_state = getattr(self, "state", None)
        if hasattr(self, "_timer"):
            self._timer.stop()
        self.started_at = None
        self.generation = None
        self.attempt_id = None
        self.cart_id = None
        self.order_id = None
        self.payment_id = None
        self.payment_attempt_id = None
        self.cancellation_requested = False
        self.payment_in_flight = False
        self.last_status = None
        self.active = False
        self._expired_emitted = False
        self.state = "IDLE"
        if clear_persisted:
            self._clear_persisted_payment()
        if previous_state not in (None, "IDLE"):
            self.state_changed.emit("IDLE")
        if previous_state is not None:
            self._emit_remaining()

    def stop(self):
        """Interrompe somente o timer local, preservando o estado para shutdown."""
        self._timer.stop()

    def restore_pending_payment(self, terminal_id=None):
        if self.payment_store is None:
            return False
        snapshot = self.payment_store.load(terminal_id)
        if not snapshot:
            return False
        self._timer.stop()
        self.started_at = None
        self.generation = snapshot.get("generation") or uuid.uuid4().hex
        self.attempt_id = snapshot.get("local_attempt_id") or uuid.uuid4().hex
        self.cart_id = snapshot.get("cart_id")
        self.order_id = snapshot.get("order_id")
        self.payment_id = snapshot.get("payment_id")
        self.payment_attempt_id = snapshot.get("payment_attempt_id")
        self.cancellation_requested = bool(snapshot.get("cancellation_requested"))
        self.last_status = snapshot.get("status")
        self.payment_in_flight = True
        self.active = False
        self._expired_emitted = False
        self._set_state(
            "CANCELLING" if self.cancellation_requested else "RECONCILIATION_PENDING"
        )
        logger.warning(
            "[PAYMENT-RECOVERY] tentativa local restaurada orderId=%s attemptId=%s status=%s",
            self.order_id, self.payment_attempt_id, self.last_status,
        )
        return True

    def adopt_backend_payment(self, data):
        if not self.generation:
            self.generation = uuid.uuid4().hex
        if not self.attempt_id:
            self.attempt_id = uuid.uuid4().hex
        self.payment_in_flight = True
        self.active = False
        self.set_remote_ids(
            data.get("cartId"), data.get("orderId"),
            data.get("transactionId"),
            data.get("paymentAttemptId") or data.get("paymentId"),
        )
        self.last_status = str(data.get("status") or "UNKNOWN").upper()
        self.cancellation_requested = bool(
            data.get("cancellationRequested", self.cancellation_requested)
        )
        self._set_state(
            "CANCELLING" if self.cancellation_requested else "RECONCILIATION_PENDING"
        )
        self._persist_payment()
        return self.attempt_id

    def clear_unresolved_after_authoritative_absence(self):
        logger.info("[PAYMENT-RECOVERY] backend confirmou ausência de tentativa ativa")
        self.reset()

    def persist_cart_checkpoint(self, local_attempt_id, cart_id):
        if self.payment_store is None:
            return True
        return self.payment_store.checkpoint_cart(local_attempt_id, cart_id)

    def _persist_payment(self, strict=False):
        if self.payment_store is None or not self.payment_in_flight:
            return
        try:
            terminal_id = None
            if self.terminal_id_provider is not None:
                terminal_id = self.terminal_id_provider()
            self.payment_store.save({
                "terminal_id": str(terminal_id) if terminal_id else None,
                "generation": self.generation or uuid.uuid4().hex,
                "local_attempt_id": self.attempt_id or uuid.uuid4().hex,
                "cart_id": self.cart_id,
                "order_id": self.order_id,
                "payment_id": self.payment_id,
                "payment_attempt_id": self.payment_attempt_id,
                "cancellation_requested": self.cancellation_requested,
                "status": self.last_status or self.state or "UNKNOWN",
            })
        except Exception:
            if strict:
                raise
            logger.exception(
                "[PAYMENT] não foi possível atualizar checkpoint; estado em memória preservado"
            )

    def _clear_persisted_payment(self):
        if self.payment_store is not None:
            try:
                self.payment_store.clear()
            except Exception:
                logger.exception(
                    "[PAYMENT] não foi possível limpar checkpoint; backend será consultado no próximo startup"
                )

    def _set_state(self, state):
        if self.state == state:
            return
        self.state = state
        self.state_changed.emit(state)

    def _emit_remaining(self):
        self.remaining_changed.emit(self.remaining_seconds())

    def _tick(self):
        remaining = self.remaining_seconds()
        self.remaining_changed.emit(remaining)
        if remaining > 0:
            return
        if self.state in {"APPROVED", "SUCCESS", "IDLE"}:
            self._timer.stop()
            return

        self.mark_timeout_check()
        if self._expired_emitted:
            return

        self._expired_emitted = True
        logger.warning("[CHECKOUT-SESSION] timeout reached")
        self.expired.emit(self.generation or "")
