import logging

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from app247_terminal.models.terminal import Terminal
from app247_terminal.services.purchase_api import (
    ActivePaymentRecoveryWorker,
    OrderStatusWorker,
    PointCancelWorker,
    PointCheckoutWorker,
    PointResumeWorker,
)
from app247_terminal.ui.styles.animated_svg import AnimatedSvgWidget
from app247_terminal.ui.styles.theme import Theme
from app247_terminal.ui.styles.tokens import Colors, Spacing
from app247_terminal.ui.screens.payment_state import PaymentStateWidget
from app247_terminal.ui.screens.session_timer import SessionTimerLabel


logger = logging.getLogger(__name__)


class PagamentoScreen(QWidget):
    POLL_INTERVAL_MS = 10000
    DEGRADED_POLL_INTERVAL_MS = 30000
    OPERATION_TIMEOUT_MS = 30000
    ATTENTION_RECHECK_MS = 90000
    FAILURE_RETURN_MS = 8000
    FINAL_RECONCILIATION_GRACE_MS = 30000
    MAX_RECONCILIATION_FAILURES = 3
    FAILURE_MESSAGES = {
        "REJECTED": "Pagamento recusado",
        "FAILED": "Não foi possível concluir o pagamento",
        "CANCELED": "Pagamento cancelado",
        "CANCELLED": "Pagamento cancelado",
        "EXPIRED": "O tempo para pagamento terminou",
        "REFUNDED": "Pagamento estornado",
    }

    def _terminal_id(self):
        provider = getattr(self.parent, "current_terminal_id", None)
        if provider is not None:
            return provider()
        terminal = Terminal.load()
        return terminal.terminalId if terminal is not None else None

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.current_attempt = None
        self.point_worker = None
        self.status_worker = None
        self.resume_worker = None
        self.active_recovery_worker = None
        self.cancel_worker = None
        self.timeout_pending = False
        self.timeout_abandoned = False
        self.reconciliation_failures = 0
        self.recovered_amount = None

        self.setObjectName("pointPaymentScreen")
        self.setStyleSheet(Theme.payment_stylesheet())

        self.pages = QStackedLayout(self)
        self.pages.setContentsMargins(0, 0, 0, 0)
        self.pages.setSpacing(0)
        self.loading_page = self._build_loading_page()
        self.attention_page = self._build_attention_page()
        self.error_page = self._build_error_page()
        self.pages.addWidget(self.loading_page)
        self.pages.addWidget(self.attention_page)
        self.pages.addWidget(self.error_page)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.reconciliar_estado)
        self.operation_timer = QTimer(self)
        self.operation_timer.setSingleShot(True)
        self.operation_timer.timeout.connect(self._operational_timeout)
        self.attention_recheck_timer = QTimer(self)
        self.attention_recheck_timer.setSingleShot(True)
        self.attention_recheck_timer.timeout.connect(self._attention_timeout)
        self.failure_return_timer = QTimer(self)
        self.failure_return_timer.setSingleShot(True)
        self.failure_return_timer.timeout.connect(self._voltar_lista)
        self.final_recovery_timer = QTimer(self)
        self.final_recovery_timer.setSingleShot(True)
        self.final_recovery_timer.timeout.connect(self._abandon_to_background_reconciliation)

    def _build_loading_page(self):
        page = QWidget(self)
        page.setObjectName("paymentLoadingPage")
        root = QVBoxLayout(page)
        root.setContentsMargins(Spacing.XL, Spacing.LG, Spacing.XL, Spacing.LG)
        root.setSpacing(Spacing.MD)
        top = QHBoxLayout()
        top.addStretch(1)
        self.timer_label = SessionTimerLabel(self.parent.compra_session, page)
        top.addWidget(self.timer_label)
        root.addLayout(top)
        root.addStretch(1)

        self.loading_spinner = AnimatedSvgWidget(
            "tube-spinner.svg", Colors.INFO, page
        )
        self.loading_spinner.setFixedSize(128, 128)
        root.addWidget(self.loading_spinner, 0, Qt.AlignHCenter)

        self.title = QLabel("PREPARANDO PAGAMENTO")
        self.title.setObjectName("paymentTitle")
        self.title.setAlignment(Qt.AlignCenter)
        self.total_final = QLabel("R$ 0,00")
        self.total_final.hide()
        self.loading = QLabel("Preparando pagamento...")
        self.loading.setObjectName("paymentLoading")
        self.loading.setProperty("state", "loading")
        self.loading.setAlignment(Qt.AlignCenter)
        self.loading.setWordWrap(True)
        self.instructions = QLabel()
        self.instructions.setObjectName("paymentInstructions")
        self.instructions.setAlignment(Qt.AlignCenter)
        self.instructions.setWordWrap(True)
        self.btn_voltar = QPushButton("TENTAR NOVAMENTE")
        self.btn_voltar.setProperty("variant", "primary")
        self.btn_voltar.setProperty("primaryAction", True)
        self.btn_voltar.clicked.connect(self._loading_action)
        self.btn_voltar.hide()

        root.addWidget(self.title)
        root.addWidget(self.loading)
        root.addWidget(self.instructions)
        root.addStretch(2)
        root.addWidget(self.btn_voltar)
        return page

    def _build_attention_page(self):
        page = PaymentStateWidget(
            "attention",
            "alert.svg",
            "FINALIZE NA MAQUININHA",
            "Pressione o botão verde e escolha a forma de pagamento.",
            parent=self,
        )
        self.attention_session_timer = SessionTimerLabel(
            self.parent.compra_session, page
        )
        page.set_timer_widget(self.attention_session_timer)
        self.attention_support = QLabel(
            "Se cancelar Débito, Crédito ou outra opção, pressione o botão "
            "verde novamente para escolher outra."
        )
        self.attention_support.setObjectName("paymentStateSupporting")
        self.attention_support.setAlignment(Qt.AlignCenter)
        self.attention_support.setWordWrap(True)
        page.content_layout.addWidget(self.attention_support)
        self.cancel_payment_button = QPushButton("CANCELAR COMPRA")
        self.cancel_payment_button.setProperty("variant", "stateDanger")
        self.cancel_payment_button.clicked.connect(self._cancel_payment)
        page.action_layout.addWidget(self.cancel_payment_button)
        return page

    def _build_error_page(self):
        page = PaymentStateWidget(
            "error",
            "error.svg",
            "PAGAMENTO NÃO APROVADO",
            "Não foi possível concluir o pagamento",
            parent=self,
        )
        self.error_reason = page.message
        self.error_session_timer = SessionTimerLabel(
            self.parent.compra_session, page
        )
        page.set_timer_widget(self.error_session_timer)
        self.error_support = QLabel("Os produtos continuam na sua compra.")
        self.error_support.setObjectName("paymentStateSupporting")
        self.error_support.setAlignment(Qt.AlignCenter)
        self.error_support.setWordWrap(True)
        page.content_layout.addWidget(self.error_support)
        self.error_retry = QPushButton("TENTAR NOVAMENTE")
        self.error_retry.setProperty("variant", "statePrimary")
        self.error_retry.setProperty("primaryAction", True)
        self.error_retry.clicked.connect(self._voltar_lista)
        page.action_layout.addWidget(self.error_retry)
        return page

    def iniciar_pagamento(self, cart_payload, total_text):
        try:
            attempt = self.parent.compra_session.begin_payment()
        except Exception:
            logger.exception("[PAYMENT-UI] persistência local indisponível")
            return False
        if attempt is None:
            logger.warning("[PAYMENT-UI] worker não iniciado: tentativa já ativa")
            return False
        self.current_attempt = attempt
        self.timeout_pending = False
        self.timeout_abandoned = False
        self.reconciliation_failures = 0
        self.recovered_amount = None
        self.total_final.setText(total_text)
        self._show_loading(
            "ENVIANDO PAGAMENTO",
            "Enviando pagamento...",
            "Aguarde só um momento.",
        )
        logger.info("[PAYMENT-UI] cobrança sendo criada")
        self.parent.setCurrentWidget(self)

        self.point_worker = PointCheckoutWorker(
            cart_payload,
            existing_cart_id=self.parent.compra_session.cart_id,
            cart_checkpoint=lambda cart_id, token=attempt:
            self.parent.compra_session.persist_cart_checkpoint(token, cart_id),
            parent=self,
        )
        self.point_worker.cart_created.connect(
            lambda data, token=attempt: self._cart_created(token, data)
        )
        self.point_worker.succeeded.connect(
            lambda data, token=attempt: self._point_started(token, data)
        )
        self.point_worker.failed.connect(
            lambda message, stage, ambiguous, context, token=attempt:
            self._point_failed(token, message, stage, ambiguous, context)
        )
        self.point_worker.timed_out.connect(
            lambda message, stage, ambiguous, context, token=attempt:
            self._point_timeout(token, message, stage, ambiguous, context)
        )
        self.point_worker.finished.connect(
            lambda token=attempt: self._point_worker_finished(token)
        )
        self._track_worker("point_worker", self.point_worker)
        logger.info("[PAYMENT-UI] worker iniciado")
        self.point_worker.start()
        return True

    def _cart_created(self, attempt, data):
        if attempt != self.current_attempt:
            return
        cart_id = data.get("cartId")
        self.parent.compra_session.set_remote_ids(cart_id=cart_id)
        logger.info(
            "[PAYMENT] checkpoint local origin=TERMINAL_REQUEST cartId=%s localAttemptId=%s",
            cart_id, attempt,
        )

    def _show_loading(self, title, message, instructions=""):
        self.failure_return_timer.stop()
        self.attention_recheck_timer.stop()
        self.title.setText(title)
        self.loading.setText(message)
        self.loading.setProperty("state", "loading")
        self.loading.style().unpolish(self.loading)
        self.loading.style().polish(self.loading)
        self.instructions.setText(instructions)
        self.loading_spinner.show()
        self.btn_voltar.hide()
        self.btn_voltar.setEnabled(False)
        self.pages.setCurrentWidget(self.loading_page)
        self.operation_timer.start(self.OPERATION_TIMEOUT_MS)

    def _show_attention(self, warning=False):
        self.operation_timer.stop()
        self.failure_return_timer.stop()
        cancelling = self.parent.compra_session.cancellation_requested
        if cancelling:
            self.attention_page.title.setText("CANCELANDO COMPRA")
            self.attention_page.message.setText(
                "Estamos confirmando o encerramento da cobrança."
            )
            self.attention_support.setText(
                "Se a maquininha ainda mostrar a cobrança, cancele a operação nela. "
                "O terminal continuará verificando o resultado."
            )
            self.cancel_payment_button.setText("CANCELAMENTO SOLICITADO")
            self.cancel_payment_button.setEnabled(False)
        else:
            self.attention_page.title.setText("PAGAMENTO AINDA NÃO CONCLUÍDO" if warning else "FINALIZE NA MAQUININHA")
            self.attention_page.message.setText(
                "Pressione o botão verde e escolha a forma de pagamento."
            )
            self.attention_support.setText(
                "Se cancelar Débito, Crédito ou outra opção, pressione o botão "
                "verde novamente para escolher outra."
            )
            self.cancel_payment_button.setText("CANCELAR COMPRA")
            self.cancel_payment_button.setEnabled(True)
        self.pages.setCurrentWidget(self.attention_page)
        if not self.attention_recheck_timer.isActive():
            self.attention_recheck_timer.start(self.ATTENTION_RECHECK_MS)

    def _point_started(self, attempt, data):
        if attempt != self.current_attempt:
            return
        logger.info(
            "[PAYMENT] cobrança remota aceita orderId=%s attemptId=%s remoteOrderId=%s status=%s",
            data.get("orderId"), data.get("paymentAttemptId") or data.get("paymentId"),
            data.get("remoteOrderId"), data.get("mercadoPagoStatus") or data.get("status"),
        )
        payment = data.get("pagamento") or {}
        self.parent.compra_session.set_remote_ids(
            data.get("cartId"), data.get("orderId"),
            data.get("transactionId") or payment.get("transactionId"),
            data.get("paymentAttemptId") or data.get("paymentId")
            or payment.get("pagamentoId"),
        )
        self.parent.compra_session.mark_waiting()
        self.reconciliation_failures = 0
        self.poll_timer.start(self.POLL_INTERVAL_MS)
        self._apply_payload(data)

    def _point_timeout(self, attempt, message, stage, ambiguous, context):
        logger.warning("[PAYMENT-UI] timeout recebido stage=%s", stage)
        self._point_failed(attempt, message, stage, ambiguous, context)

    def _point_worker_finished(self, attempt):
        logger.info("[PAYMENT-UI] finished recebido")
        worker = self.point_worker
        if (
            attempt == self.current_attempt
            and worker is not None
            and not worker.outcome_emitted
            and not worker.isInterruptionRequested()
        ):
            logger.error("[PAYMENT-UI] worker terminou sem outcome; encerrando loading")
            self._point_failed(
                attempt, "Não foi possível preparar o pagamento",
                "worker_finished", False, {}
            )

    def _point_failed(self, attempt, message, stage, ambiguous, context):
        if attempt != self.current_attempt:
            return
        logger.warning("[PAYMENT-UI] error recebido stage=%s ambiguous=%s", stage, ambiguous)
        logger.warning(
            "Falha ao iniciar Point: stage=%s ambiguous=%s message=%s",
            stage, ambiguous, message,
        )
        if context:
            self.parent.compra_session.set_remote_ids(
                context.get("cartId"), context.get("orderId"),
                payment_attempt_id=context.get("paymentAttemptId"),
            )
        if stage == "payment_active":
            recovery = {
                "cartId": context.get("cartId"),
                "orderId": context.get("orderId"),
                "paymentAttemptId": context.get("paymentAttemptId"),
                "status": context.get("paymentStatus") or "WAITING_PAYMENT",
            }
            self.current_attempt = self.parent.compra_session.adopt_backend_payment(recovery)
            logger.warning(
                "[PAYMENT-RECOVERY] cobrança ativa recuperada origin=PAYMENT_ALREADY_ACTIVE orderId=%s attemptId=%s status=%s",
                recovery.get("orderId"), recovery.get("paymentAttemptId"),
                recovery.get("status"),
            )
            self.mostrar_reconciliacao_pendente(origin="PAYMENT_ALREADY_ACTIVE")
            return
        if stage == "price_changed":
            self.parent.terminal.aplicar_precos_atualizados(context)
            self.parent.terminal.solicitar_sync_produtos("PRICE_CHANGED")
            self._safe_failure(
                "Os preços foram atualizados. Revise o carrinho e confirme novamente."
            )
            return
        if ambiguous and self.parent.compra_session.cart_id:
            self.reconciliation_failures += 1
            if self.reconciliation_failures > self.MAX_RECONCILIATION_FAILURES:
                self._abandon_to_background_reconciliation()
                return
            self.parent.compra_session.mark_waiting()
            self._show_loading(
                "CONFIRMANDO PAGAMENTO",
                "Verificando se a cobrança foi enviada...",
                "A conexão oscilou. Não tente pagar novamente enquanto confirmamos o estado.",
            )
            self.poll_timer.start(self.POLL_INTERVAL_MS)
            self._retomar_inicio_point()
            return
        if self.timeout_pending:
            self._finish_expired_session()
            return
        self._safe_failure("Não foi possível iniciar o pagamento. O carrinho foi preservado.")

    def processar_evento(self, data):
        expected_terminal_id = self._terminal_id()
        terminal_id = data.get("terminalId")
        if not expected_terminal_id or str(terminal_id) != str(expected_terminal_id):
            logger.warning("Evento de pagamento ignorado por terminal divergente")
            return
        status = data.get("status") or data.get("paid")
        self._apply_status(
            data.get("orderId"), status, data.get("transactionId"),
            data.get("mercadoPagoStatus"),
            data.get("paymentAttemptId") or data.get("paymentId"),
        )

    def _apply_payload(self, data):
        payment = data.get("pagamento") or {}
        if data.get("amount") is not None:
            self.recovered_amount = data.get("amount")
        if data.get("cancellationRequested"):
            self.parent.compra_session.mark_cancelling()
        status = data.get("status") or payment.get("status")
        self._apply_status(
            data.get("orderId"), status,
            data.get("transactionId") or payment.get("transactionId"),
            data.get("mercadoPagoStatus"),
            data.get("paymentAttemptId") or data.get("paymentId")
            or payment.get("pagamentoId"),
        )

    def _apply_status(self, order_id, status, transaction_id=None,
                      mercado_pago_status=None, payment_attempt_id=None):
        session = self.parent.compra_session
        cancellation_requested = session.cancellation_requested
        result = session.apply_status(order_id, status, payment_attempt_id)
        if result != "IGNORED" and transaction_id:
            session.set_remote_ids(payment_id=transaction_id)
        if result == "APPROVED":
            recovered_amount = self.recovered_amount
            self._handle_payment_approved(recovered_amount)
        elif result == "FAILED":
            expired_flow = self.timeout_pending
            self.parar_espera()
            if cancellation_requested and session.last_status in {"CANCELED", "CANCELLED", "EXPIRED"}:
                logger.info(
                    "[PAYMENT-UI] cancelamento confirmado orderId=%s status=%s",
                    order_id, session.last_status,
                )
                self.parent.reset_compra(outcome="cancelled")
                self.parent.setCurrentWidget(self.parent.welcome)
            elif expired_flow:
                self._finish_expired_session()
            else:
                self._show_definitive_failure(session.last_status)
        elif result == "PROCESSING":
            remote = str(mercado_pago_status or session.last_status or "UNKNOWN").strip().upper()
            logger.info(
                "[PAYMENT-UI] status permanece ativo; exibindo instruções orderId=%s status=%s",
                order_id, remote,
            )
            self._show_attention(warning=self.timeout_pending or self.timeout_abandoned)
            if self.timeout_abandoned:
                self.poll_timer.start(self.DEGRADED_POLL_INTERVAL_MS)

    def _handle_payment_approved(self, recovered_amount=None):
        """Entrada única da UI para aprovação via WS, polling ou recuperação."""
        session = self.parent.compra_session
        if not session.order_id:
            logger.error("[PAYMENT-UI] aprovação sem orderId; tela não liberada")
            return
        self.parar_espera()
        session.mark_success()
        self.parent.confirmacao.mostrar_tela(recovered_amount)
        self.parent.setCurrentWidget(self.parent.confirmacao)

    def reconciliar_estado(self):
        order_id = self.parent.compra_session.order_id
        if not order_id:
            self._discover_active_payment("TERMINAL_RECOVERY")
            return
        if self.status_worker and self.status_worker.isRunning():
            return
        expected_order = order_id
        terminal_id = self._terminal_id()
        if not terminal_id:
            return
        self.status_worker = OrderStatusWorker(order_id, terminal_id, parent=self)
        self.status_worker.succeeded.connect(
            lambda data, oid=expected_order: self._status_received(oid, data)
        )
        self.status_worker.failed.connect(
            lambda message, oid=expected_order: self._status_failed(oid, message)
        )
        self._track_worker("status_worker", self.status_worker)
        self.status_worker.start()

    def verificar_apos_reconexao(self):
        session = self.parent.compra_session
        if not session.payment_in_flight:
            self._discover_active_payment("RECONNECT")
            return
        self.parent.setCurrentWidget(self)
        if session.order_id:
            self._show_attention()
        else:
            self._show_loading(
                "VERIFICANDO PAGAMENTO",
                "Conexão restaurada. Confirmando o envio da cobrança...",
                "Não tente pagar novamente enquanto consultamos o servidor.",
            )
        if session.order_id:
            self.reconciliar_estado()
        else:
            self._discover_active_payment("RECONNECT")

    def recuperar_apos_startup(self):
        session = self.parent.compra_session
        if session.payment_in_flight:
            self.current_attempt = session.attempt_id
            self.parent.setCurrentWidget(self)
            self._show_pending_recovery()
            if session.order_id:
                self.reconciliar_estado()
            else:
                self._discover_active_payment("STARTUP")
            return
        self._discover_active_payment("STARTUP")

    def mostrar_reconciliacao_pendente(self, origin="UI_RECOVERY"):
        session = self.parent.compra_session
        self.parent.stacked_widget.setCurrentWidget(self)
        self._show_pending_recovery()
        logger.info(
            "[PAYMENT-RECOVERY] verificação solicitada origin=%s orderId=%s attemptId=%s status=%s",
            origin, session.order_id, session.payment_attempt_id, session.last_status,
        )
        if session.order_id:
            self.reconciliar_estado()
        else:
            self._discover_active_payment(origin)

    def _show_pending_recovery(self):
        if self.parent.compra_session.order_id:
            self._show_attention(warning=True)
            return
        self.operation_timer.stop()
        self.failure_return_timer.stop()
        self.attention_recheck_timer.stop()
        self.title.setText("AGUARDANDO PAGAMENTO")
        self.loading.setText("Estamos verificando a cobrança atual.")
        self.loading.setProperty("state", "loading")
        self.loading.style().unpolish(self.loading)
        self.loading.style().polish(self.loading)
        self.instructions.setText(
            "Verifique se a maquininha está ligada e conectada. "
            "Não inicie outro pagamento."
        )
        self.loading_spinner.show()
        self.btn_voltar.setText("VERIFICAR NOVAMENTE")
        self.btn_voltar.show()
        self.btn_voltar.setEnabled(True)
        self.pages.setCurrentWidget(self.loading_page)

    def _loading_action(self):
        if self.parent.compra_session.payment_in_flight:
            self.mostrar_reconciliacao_pendente(origin="MANUAL")
            return
        self._voltar_lista()

    def _discover_active_payment(self, origin):
        if self.active_recovery_worker and self.active_recovery_worker.isRunning():
            return
        terminal_id = self._terminal_id()
        if not terminal_id:
            return
        expected_attempt = self.parent.compra_session.attempt_id
        worker = ActivePaymentRecoveryWorker(terminal_id, parent=self)
        self.active_recovery_worker = worker
        worker.succeeded.connect(
            lambda data, token=expected_attempt, source=origin:
            self._active_recovery_received(token, source, data)
        )
        worker.failed.connect(
            lambda message, token=expected_attempt, source=origin:
            self._active_recovery_failed(token, source, message)
        )
        self._track_worker("active_recovery_worker", worker)
        worker.start()

    def _active_recovery_received(self, expected_attempt, origin, data):
        session = self.parent.compra_session
        if expected_attempt != session.attempt_id:
            return
        if isinstance(data, dict) and data.get("orderId"):
            self.current_attempt = session.adopt_backend_payment(data)
            self.reconciliation_failures = 0
            logger.warning(
                "[PAYMENT-RECOVERY] tentativa ativa encontrada origin=%s orderId=%s attemptId=%s status=%s",
                origin, data.get("orderId"),
                data.get("paymentAttemptId") or data.get("paymentId"),
                data.get("status"),
            )
            self.parent.setCurrentWidget(self)
            self.poll_timer.start(self.POLL_INTERVAL_MS)
            self._apply_payload(data)
            return
        if not session.payment_in_flight:
            return
        if session.cart_id:
            logger.info(
                "[PAYMENT-RECOVERY] nenhuma tentativa ativa; retomando mesmo cart origin=%s cartId=%s",
                origin, session.cart_id,
            )
            self._retomar_inicio_point()
            return
        if not session.order_id:
            session.clear_unresolved_after_authoritative_absence()
            self.parar_espera()
            self.parent.setCurrentWidget(self.parent.welcome)

    def _active_recovery_failed(self, expected_attempt, origin, message):
        if expected_attempt != self.parent.compra_session.attempt_id:
            return
        logger.warning(
            "[PAYMENT-RECOVERY] descoberta falhou origin=%s message=%s", origin, message
        )
        if self.parent.compra_session.payment_in_flight:
            self.parent.compra_session.mark_reconciliation_pending()
            self._show_pending_recovery()
            self.poll_timer.start(self.DEGRADED_POLL_INTERVAL_MS)

    def _retomar_inicio_point(self):
        cart_id = self.parent.compra_session.cart_id
        if not cart_id or (self.resume_worker and self.resume_worker.isRunning()):
            return
        expected_attempt = self.current_attempt
        terminal_id = self._terminal_id()
        if not terminal_id:
            self._status_failed(None, "Terminal não identificado")
            return
        self.resume_worker = PointResumeWorker(
            cart_id, terminal_id=terminal_id, parent=self
        )
        self.resume_worker.succeeded.connect(
            lambda data, token=expected_attempt, cid=cart_id:
            self._resume_started(token, cid, data)
        )
        self.resume_worker.failed.connect(
            lambda message, context, token=expected_attempt, cid=cart_id:
            self._resume_failed(token, cid, message, context)
        )
        self._track_worker("resume_worker", self.resume_worker)
        self.resume_worker.start()

    def _resume_started(self, attempt, cart_id, data):
        if attempt != self.current_attempt:
            return
        if cart_id != self.parent.compra_session.cart_id:
            return
        self._point_started(attempt, data)

    def _resume_failed(self, attempt, cart_id, message, context=None):
        if attempt != self.current_attempt:
            return
        if cart_id != self.parent.compra_session.cart_id:
            return
        if context and context.get("orderId"):
            recovery = {
                "cartId": context.get("cartId") or cart_id,
                "orderId": context.get("orderId"),
                "paymentAttemptId": context.get("paymentAttemptId"),
                "status": context.get("paymentStatus") or "WAITING_PAYMENT",
            }
            self.current_attempt = self.parent.compra_session.adopt_backend_payment(recovery)
            self.mostrar_reconciliacao_pendente(origin="PAYMENT_ALREADY_ACTIVE")
            return
        self._status_failed(None, message)

    def _status_received(self, expected_order, data):
        if expected_order != self.parent.compra_session.order_id:
            return
        self._apply_payload(data)

    def _status_failed(self, expected_order, message):
        if (
            expected_order is not None
            and expected_order != self.parent.compra_session.order_id
        ):
            return
        logger.warning("Não foi possível reconciliar pagamento: %s", message)
        self.reconciliation_failures += 1
        if self.reconciliation_failures > self.MAX_RECONCILIATION_FAILURES:
            self._abandon_to_background_reconciliation()
            return
        if self.parent.compra_session.order_id:
            self._show_attention(warning=True)
        else:
            self._show_pending_recovery()
        self.poll_timer.start(self.POLL_INTERVAL_MS)

    def _cancel_payment(self):
        session = self.parent.compra_session
        if session.cancellation_requested or not session.mark_cancelling():
            return
        terminal_id = self._terminal_id()
        if not terminal_id:
            self._cancel_failed("Terminal não identificado")
            return
        logger.info(
            "[PAYMENT-UI] cancelamento integral solicitado orderId=%s attemptId=%s",
            session.order_id, session.payment_attempt_id,
        )
        self._show_attention()
        self.cancel_worker = PointCancelWorker(
            session.order_id, terminal_id, parent=self
        )
        expected_order = session.order_id
        self.cancel_worker.succeeded.connect(
            lambda data, oid=expected_order: self._cancel_received(oid, data)
        )
        self.cancel_worker.failed.connect(
            lambda message, oid=expected_order: self._cancel_failed(message, oid)
        )
        self._track_worker("cancel_worker", self.cancel_worker)
        self.cancel_worker.start()

    def _cancel_received(self, expected_order, data):
        if expected_order != self.parent.compra_session.order_id:
            return
        self.reconciliation_failures = 0
        self.poll_timer.start(self.POLL_INTERVAL_MS)
        self._apply_payload(data)

    def _cancel_failed(self, message, expected_order=None):
        if expected_order and expected_order != self.parent.compra_session.order_id:
            return
        logger.warning(
            "[PAYMENT-UI] cancelamento inconclusivo orderId=%s reason=%s",
            self.parent.compra_session.order_id, message,
        )
        self.parent.compra_session.mark_cancelling()
        self._show_attention(warning=True)
        self.poll_timer.start(self.POLL_INTERVAL_MS)
        self.reconciliar_estado()

    def tratar_timeout_global(self, generation):
        session = self.parent.compra_session
        if generation != session.generation:
            return
        point_request_running = bool(
            self.point_worker is not None and self.point_worker.isRunning()
        )
        if (
            not session.order_id
            and not session.cart_id
            and not point_request_running
        ):
            self._finish_expired_session()
            return
        self.timeout_pending = True
        self.parent.setCurrentWidget(self)
        if session.order_id:
            self._cancel_payment()
            self._show_attention(warning=True)
        else:
            self._show_loading(
                "CONFIRMANDO PAGAMENTO",
                "Verificando se a cobrança foi criada...",
                "O tempo terminou. Não inicie outra compra.",
            )
        self.final_recovery_timer.start(self.FINAL_RECONCILIATION_GRACE_MS)
        self.poll_timer.start(self.POLL_INTERVAL_MS)
        if session.order_id:
            self.reconciliar_estado()
        else:
            self._discover_active_payment("CHECKOUT_TIMEOUT")

    def _show_definitive_failure(self, status):
        normalized = str(status or "FAILED").upper()
        self.error_reason.setText(
            self.FAILURE_MESSAGES.get(normalized, self.FAILURE_MESSAGES["FAILED"])
        )
        self.error_retry.setEnabled(True)
        self.pages.setCurrentWidget(self.error_page)
        self.parent.compra_session.prepare_retry()
        self.failure_return_timer.start(self.FAILURE_RETURN_MS)

    def _safe_failure(self, message):
        """Falha operacional antes de um resultado financeiro definitivo."""
        self._show_loading(
            "PAGAMENTO NÃO CONCLUÍDO",
            message,
            "Os produtos continuam na lista da compra.",
        )
        self.loading_spinner.hide()
        self.loading.setProperty("state", "error")
        self.loading.style().unpolish(self.loading)
        self.loading.style().polish(self.loading)
        self.operation_timer.stop()
        self.btn_voltar.show()
        self.btn_voltar.setText("VOLTAR À COMPRA")
        self.btn_voltar.setEnabled(True)
        self.parent.compra_session.prepare_retry()

    def _voltar_lista(self):
        if not self.parent.compra_session.payment_in_flight:
            self.failure_return_timer.stop()
            self.parent.setCurrentWidget(self.parent.terminal)

    def _attention_timeout(self):
        if not self.parent.compra_session.payment_in_flight:
            return
        self._show_attention(warning=True)
        self.reconciliar_estado()

    def _operational_timeout(self):
        session = self.parent.compra_session
        logger.warning(
            "[CHECKOUT-SESSION] timeout operacional state=%s orderId=%s",
            session.state, session.order_id,
        )
        if self.timeout_pending and not session.order_id and not session.cart_id:
            if self.point_worker is not None and self.point_worker.isRunning():
                self._show_loading(
                    "CONFIRMANDO PAGAMENTO",
                    "Aguardando a conclusão segura da operação...",
                    "Não inicie outra compra enquanto verificamos se houve cobrança.",
                )
                return
            self._finish_expired_session()
            return
        if session.state == "RECONCILIATION_PENDING":
            self._show_pending_recovery()
            self.poll_timer.start(self.DEGRADED_POLL_INTERVAL_MS)
            self.reconciliar_estado()
            return
        if session.order_id or session.cart_id:
            if session.order_id:
                self._show_attention(warning=True)
            else:
                self._show_pending_recovery()
            self.poll_timer.start(self.POLL_INTERVAL_MS)
            self.reconciliar_estado()
        else:
            self._safe_failure(
                "O servidor não respondeu a tempo. O carrinho foi preservado."
            )

    def _abandon_to_background_reconciliation(self):
        session = self.parent.compra_session
        if not session.payment_in_flight:
            return
        if not session.order_id and not session.cart_id:
            if self.point_worker is not None and self.point_worker.isRunning():
                self.final_recovery_timer.start(self.FINAL_RECONCILIATION_GRACE_MS)
                return
            self._finish_expired_session()
            return
        self.timeout_abandoned = True
        session.mark_reconciliation_pending()
        self.operation_timer.stop()
        self.parent.setCurrentWidget(self)
        self._show_pending_recovery()
        self.poll_timer.start(self.DEGRADED_POLL_INTERVAL_MS)

    def _finish_expired_session(self):
        generation = self.parent.compra_session.generation
        complete = getattr(self.parent, "complete_checkout_expiration", None)
        if complete is not None:
            complete(generation)
            return
        self.parent.reset_compra(outcome="cancelled")
        self.parent.setCurrentWidget(self.parent.welcome)

    def _disconnect_worker_callbacks(self):
        """Invalida callbacks locais sem interromper uma requisição financeira incerta."""
        for worker in (
            self.point_worker, self.status_worker, self.resume_worker,
            self.active_recovery_worker, self.cancel_worker,
        ):
            if worker is None:
                continue
            for signal_name in ("succeeded", "failed", "timed_out", "cart_created"):
                signal = getattr(worker, signal_name, None)
                if signal is None:
                    continue
                try:
                    signal.disconnect()
                except (TypeError, RuntimeError):
                    pass

    def _track_worker(self, attribute, worker):
        worker.finished.connect(
            lambda name=attribute, expected=worker:
            self._worker_finished(name, expected)
        )

    def _worker_finished(self, attribute, worker):
        if getattr(self, attribute, None) is worker:
            setattr(self, attribute, None)
        worker.deleteLater()

    def parar_espera(self):
        self.poll_timer.stop()
        self.operation_timer.stop()
        self.attention_recheck_timer.stop()
        self.failure_return_timer.stop()
        self.final_recovery_timer.stop()
        self.current_attempt = None
        self.timeout_pending = False
        self.timeout_abandoned = False
        self.recovered_amount = None
        self._disconnect_worker_callbacks()

    def parar_workers(self):
        self.parar_espera()
        for attribute in (
            "point_worker", "status_worker", "resume_worker",
            "active_recovery_worker", "cancel_worker",
        ):
            worker = getattr(self, attribute)
            if worker is not None and worker.isRunning():
                worker.requestInterruption()
                worker.wait(25000)
            if worker is not None and not worker.isRunning():
                if getattr(self, attribute, None) is worker:
                    setattr(self, attribute, None)
                worker.deleteLater()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        size = 128 if self.width() >= self.height() else 150
        self.loading_spinner.setFixedSize(size, size)
