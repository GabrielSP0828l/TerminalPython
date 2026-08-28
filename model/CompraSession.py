import time
import uuid
import logging

from PyQt5.QtCore import QObject, QTimer, pyqtSignal


logger = logging.getLogger(__name__)


class CompraSession(QObject):
    SESSION_LIMIT_SECONDS = 10 * 60

    remaining_changed = pyqtSignal(int)
    expired = pyqtSignal(str)
    state_changed = pyqtSignal(str)

    INTERMEDIATE = {
        "PENDING", "CREATED", "AT_TERMINAL", "ACTION_REQUIRED",
        "PROCESSING", "WAITING_PAYMENT"
    }
    APPROVED = {"APPROVED", "PAID", "PROCESSED"}
    FAILED = {"REJECTED", "FAILED", "CANCELED", "CANCELLED", "EXPIRED", "REFUNDED"}

    def __init__(self, parent=None, clock=None, duration_seconds=None):
        super().__init__(parent)
        self._clock = clock or time.monotonic
        self.duration_seconds = int(duration_seconds or self.SESSION_LIMIT_SECONDS)
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self.reset()

    def start_if_needed(self):
        if self.started_at is not None:
            return
        self.started_at = self._clock()
        self.generation = uuid.uuid4().hex
        self._set_state("SCANNING")
        self._timer.start()
        self._emit_remaining()
        logger.info("[CHECKOUT-SESSION] iniciada duration=%ss", self.duration_seconds)

    def begin_payment(self):
        self.start_if_needed()
        if self.payment_in_flight or self.state in {"APPROVED", "SUCCESS", "TIMEOUT_CHECK"}:
            return None
        self.payment_in_flight = True
        self.attempt_id = uuid.uuid4().hex
        self.cart_id = None
        self.order_id = None
        self.payment_id = None
        self._set_state("STARTING_PAYMENT")
        return self.attempt_id

    def set_remote_ids(self, cart_id=None, order_id=None, payment_id=None):
        if cart_id:
            self.cart_id = str(cart_id)
        if order_id:
            self.order_id = str(order_id)
        if payment_id:
            self.payment_id = str(payment_id)

    def mark_waiting(self):
        if self.state not in {"APPROVED", "SUCCESS"}:
            self._set_state("WAITING_PAYMENT")

    def apply_status(self, order_id, status):
        normalized = str(status or "").strip().upper()
        if not self.order_id or str(order_id) != self.order_id:
            return "IGNORED"
        self.last_status = normalized
        if normalized in self.APPROVED:
            if self.state in {"APPROVED", "SUCCESS"}:
                return "DUPLICATE_APPROVED"
            self.payment_in_flight = False
            self._timer.stop()
            self._set_state("APPROVED")
            return "APPROVED"
        if normalized in self.FAILED:
            self.payment_in_flight = False
            self._set_state("PAYMENT_FAILED")
            return "FAILED"
        if normalized in self.INTERMEDIATE:
            self.payment_in_flight = True
            self._set_state("PROCESSING")
            return "PROCESSING"
        return "UNKNOWN"

    def prepare_retry(self):
        self.payment_in_flight = False
        self.cart_id = None
        self.order_id = None
        self.payment_id = None
        self.attempt_id = None
        self.last_status = None
        if self.started_at is not None and self.remaining_seconds() > 0:
            self._set_state("CART_READY")

    def mark_timeout_check(self):
        if self.state in {"APPROVED", "SUCCESS", "IDLE"}:
            return False
        self._timer.stop()
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
        self._set_state("RECONCILIATION_PENDING")
        logger.warning("[CHECKOUT-SESSION] timeout; reconciliação financeira pendente")

    def cancel(self):
        logger.info("[CHECKOUT-SESSION] cancelada")
        self.reset()

    def finish(self):
        logger.info("[CHECKOUT-SESSION] finalizada")
        self.reset()

    def reset(self):
        previous_state = getattr(self, "state", None)
        if hasattr(self, "_timer"):
            self._timer.stop()
        self.started_at = None
        self.generation = None
        self.attempt_id = None
        self.cart_id = None
        self.order_id = None
        self.payment_id = None
        self.payment_in_flight = False
        self.last_status = None
        self.state = "IDLE"
        if previous_state not in (None, "IDLE"):
            self.state_changed.emit("IDLE")

    def stop(self):
        """Interrompe somente o timer local, preservando o estado para shutdown."""
        self._timer.stop()

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
        if remaining == 0 and self.mark_timeout_check():
            logger.warning("[CHECKOUT-SESSION] timeout")
            self.expired.emit(self.generation or "")
