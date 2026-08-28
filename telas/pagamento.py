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

from model.Terminal import Terminal
from service.PurchaseApi import OrderStatusWorker, PointCheckoutWorker, PointResumeWorker
from styles.animated_svg import AnimatedSvgWidget
from styles.theme import Theme
from styles.tokens import Colors, Spacing
from telas.PaymentStateWidget import PaymentStateWidget
from telas.SessionTimerLabel import SessionTimerLabel


logger = logging.getLogger(__name__)


class PagamentoScreen(QWidget):
    POLL_INTERVAL_MS = 10000
    OPERATION_TIMEOUT_MS = 30000
    ATTENTION_RECHECK_MS = 90000
    FAILURE_RETURN_MS = 8000
    FINAL_RECONCILIATION_GRACE_MS = 30000
    FAILURE_MESSAGES = {
        "REJECTED": "Pagamento recusado",
        "FAILED": "Não foi possível concluir o pagamento",
        "CANCELED": "Pagamento cancelado",
        "CANCELLED": "Pagamento cancelado",
        "EXPIRED": "O tempo para pagamento terminou",
        "REFUNDED": "Pagamento estornado",
    }

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.current_attempt = None
        self.point_worker = None
        self.status_worker = None
        self.resume_worker = None
        self.timeout_pending = False
        self.timeout_abandoned = False

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
        self.btn_voltar.clicked.connect(self._voltar_lista)
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
            "PRESSIONE O BOTÃO VERDE\nDA MAQUININHA",
            "Siga as instruções exibidas na maquininha\npara concluir o pagamento.",
            parent=self,
        )
        self.attention_session_timer = SessionTimerLabel(
            self.parent.compra_session, page
        )
        page.set_timer_widget(self.attention_session_timer)
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
        attempt = self.parent.compra_session.begin_payment()
        if attempt is None:
            return
        self.current_attempt = attempt
        self.timeout_pending = False
        self.timeout_abandoned = False
        self.total_final.setText(total_text)
        self._show_loading(
            "PREPARANDO PAGAMENTO",
            "Preparando pagamento...",
            "Aguarde só um momento.",
        )
        self.parent.setCurrentWidget(self)

        self.point_worker = PointCheckoutWorker(cart_payload, parent=self)
        self.point_worker.succeeded.connect(
            lambda data, token=attempt: self._point_started(token, data)
        )
        self.point_worker.failed.connect(
            lambda message, stage, ambiguous, context, token=attempt:
            self._point_failed(token, message, stage, ambiguous, context)
        )
        self.point_worker.start()

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

    def _show_attention(self):
        self.operation_timer.stop()
        self.failure_return_timer.stop()
        self.pages.setCurrentWidget(self.attention_page)
        self.attention_recheck_timer.start(self.ATTENTION_RECHECK_MS)

    def _point_started(self, attempt, data):
        if attempt != self.current_attempt:
            return
        payment = data.get("pagamento") or {}
        self.parent.compra_session.set_remote_ids(
            data.get("cartId"), data.get("orderId"),
            data.get("paymentId") or data.get("transactionId") or payment.get("pagamentoId")
        )
        self.parent.compra_session.mark_waiting()
        self._show_attention()
        self.poll_timer.start(self.POLL_INTERVAL_MS)
        self._apply_payload(data)

    def _point_failed(self, attempt, message, stage, ambiguous, context):
        if attempt != self.current_attempt:
            return
        logger.warning(
            "Falha ao iniciar Point: stage=%s ambiguous=%s message=%s",
            stage, ambiguous, message,
        )
        if context:
            self.parent.compra_session.set_remote_ids(
                context.get("cartId"), context.get("orderId")
            )
        if ambiguous and self.parent.compra_session.cart_id:
            self.parent.compra_session.mark_waiting()
            self._show_loading(
                "CONFIRMANDO PAGAMENTO",
                "Verificando se a cobrança foi enviada...",
                "A conexão oscilou. Não tente pagar novamente enquanto confirmamos o estado.",
            )
            self.poll_timer.start(self.POLL_INTERVAL_MS)
            self._retomar_inicio_point()
            return
        self._safe_failure("Não foi possível iniciar o pagamento. O carrinho foi preservado.")

    def processar_evento(self, data):
        terminal = Terminal.load()
        terminal_id = data.get("terminalId")
        if not terminal or str(terminal_id) != str(terminal.terminalId):
            logger.warning("Evento de pagamento ignorado por terminal divergente")
            return
        status = data.get("status") or data.get("paid")
        self._apply_status(data.get("orderId"), status, data.get("transactionId"))

    def _apply_payload(self, data):
        payment = data.get("pagamento") or {}
        status = data.get("status") or payment.get("status")
        self._apply_status(
            data.get("orderId"), status,
            data.get("paymentId") or data.get("transactionId") or payment.get("transactionId"),
        )

    def _apply_status(self, order_id, status, transaction_id=None):
        session = self.parent.compra_session
        if transaction_id:
            session.set_remote_ids(payment_id=transaction_id)
        result = session.apply_status(order_id, status)
        if result == "APPROVED":
            self.parar_espera()
            session.mark_success()
            self.parent.confirmacao.mostrar_tela()
            self.parent.setCurrentWidget(self.parent.confirmacao)
        elif result == "FAILED":
            self.parar_espera()
            if self.timeout_abandoned:
                self.parent.reset_compra(outcome="cancelled")
                self.parent.setCurrentWidget(self.parent.welcome)
            else:
                self._show_definitive_failure(session.last_status)
        elif result == "PROCESSING":
            if self.timeout_abandoned:
                self.poll_timer.start(self.POLL_INTERVAL_MS)
                return
            if self.timeout_pending:
                self._show_loading(
                    "CONFIRMANDO PAGAMENTO",
                    "A compra atingiu o limite de tempo.",
                    "Estamos verificando o resultado antes de liberar o terminal.",
                )
                return
            if session.last_status == "PROCESSING":
                self._show_loading(
                    "PROCESSANDO PAGAMENTO",
                    "Confirmando o resultado do pagamento...",
                    "Aguarde e não retire o cartão até a maquininha orientar.",
                )
            else:
                # Mantém também o estado textual legado coerente para leitores
                # de acessibilidade, embora a página visível seja a laranja.
                self.loading.setText("Aguardando interação com a maquininha...")
                self._show_attention()

    def reconciliar_estado(self):
        order_id = self.parent.compra_session.order_id
        if not order_id:
            if self.parent.compra_session.cart_id:
                self._retomar_inicio_point()
            return
        if self.status_worker and self.status_worker.isRunning():
            return
        expected_order = order_id
        terminal = Terminal.load()
        if terminal is None:
            return
        self.status_worker = OrderStatusWorker(order_id, terminal.terminalId, parent=self)
        self.status_worker.succeeded.connect(
            lambda data, oid=expected_order: self._status_received(oid, data)
        )
        self.status_worker.failed.connect(self._status_failed)
        self.status_worker.start()

    def verificar_apos_reconexao(self):
        if not self.parent.compra_session.payment_in_flight:
            return
        if self.parent.compra_session.state == "RECONCILIATION_PENDING":
            self.reconciliar_estado()
            return
        self.parent.setCurrentWidget(self)
        self._show_loading(
            "VERIFICANDO PAGAMENTO",
            "Conexão restaurada. Confirmando o estado da compra...",
            "Aguarde a confirmação do servidor antes de tentar um novo pagamento.",
        )
        self.reconciliar_estado()

    def mostrar_reconciliacao_pendente(self):
        self.parent.stacked_widget.setCurrentWidget(self)
        self._show_loading(
            "VERIFICANDO COMPRA ANTERIOR",
            "Ainda estamos confirmando o resultado do pagamento.",
            "Uma nova compra será liberada assim que o servidor responder.",
        )
        self.reconciliar_estado()

    def _retomar_inicio_point(self):
        cart_id = self.parent.compra_session.cart_id
        if not cart_id or (self.resume_worker and self.resume_worker.isRunning()):
            return
        self.resume_worker = PointResumeWorker(cart_id, parent=self)
        self.resume_worker.succeeded.connect(
            lambda data: self._point_started(self.current_attempt, data)
        )
        self.resume_worker.failed.connect(self._status_failed)
        self.resume_worker.start()

    def _status_received(self, expected_order, data):
        if expected_order != self.parent.compra_session.order_id:
            return
        self._apply_payload(data)

    def _status_failed(self, message):
        logger.warning("Não foi possível reconciliar pagamento: %s", message)
        self._show_loading(
            "CONFIRMANDO PAGAMENTO",
            "Verificando o pagamento com o servidor...",
            "Não inicie outra tentativa enquanto verificamos o resultado.",
        )
        self.poll_timer.start(self.POLL_INTERVAL_MS)

    def tratar_timeout_global(self, generation):
        session = self.parent.compra_session
        if generation != session.generation:
            return
        if not session.order_id and not session.cart_id:
            self.parent.reset_compra(outcome="cancelled")
            self.parent.setCurrentWidget(self.parent.welcome)
            return
        self.timeout_pending = True
        self.parent.setCurrentWidget(self)
        self._show_loading(
            "CONFIRMANDO PAGAMENTO",
            "Verificando o estado final da compra...",
            "O tempo terminou. Aguarde a confirmação antes de iniciar outra compra.",
        )
        self.final_recovery_timer.start(self.FINAL_RECONCILIATION_GRACE_MS)
        self.poll_timer.start(self.POLL_INTERVAL_MS)
        if session.order_id:
            self.reconciliar_estado()
        else:
            self._retomar_inicio_point()

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
        self.btn_voltar.setEnabled(True)
        self.parent.compra_session.prepare_retry()

    def _voltar_lista(self):
        if not self.parent.compra_session.payment_in_flight:
            self.failure_return_timer.stop()
            self.parent.setCurrentWidget(self.parent.terminal)

    def _attention_timeout(self):
        if not self.parent.compra_session.payment_in_flight:
            return
        self._show_loading(
            "VERIFICANDO PAGAMENTO",
            "A maquininha ainda não confirmou o resultado.",
            "Estamos consultando o servidor antes de liberar uma nova tentativa.",
        )
        self.reconciliar_estado()

    def _operational_timeout(self):
        session = self.parent.compra_session
        logger.warning(
            "[CHECKOUT-SESSION] timeout operacional state=%s orderId=%s",
            session.state, session.order_id,
        )
        if session.state == "RECONCILIATION_PENDING":
            self.parent.setCurrentWidget(self.parent.welcome)
            self.poll_timer.start(self.POLL_INTERVAL_MS)
            self.reconciliar_estado()
            return
        if session.order_id or session.cart_id:
            self._show_loading(
                "VERIFICANDO PAGAMENTO",
                "A operação demorou mais que o esperado.",
                "Consultando o servidor para evitar uma cobrança duplicada.",
            )
            self.poll_timer.start(self.POLL_INTERVAL_MS)
            self.reconciliar_estado()
        else:
            self._safe_failure(
                "O servidor não respondeu a tempo. O carrinho foi preservado."
            )

    def _abandon_to_background_reconciliation(self):
        session = self.parent.compra_session
        if not self.timeout_pending or not session.payment_in_flight:
            return
        self.timeout_abandoned = True
        session.mark_reconciliation_pending()
        self.operation_timer.stop()
        self.parent.setCurrentWidget(self.parent.welcome)
        self.poll_timer.start(self.POLL_INTERVAL_MS)
        self.reconciliar_estado()

    def parar_espera(self):
        self.poll_timer.stop()
        self.operation_timer.stop()
        self.attention_recheck_timer.stop()
        self.failure_return_timer.stop()
        self.final_recovery_timer.stop()
        self.current_attempt = None

    def parar_workers(self):
        self.parar_espera()
        for worker in (self.point_worker, self.status_worker, self.resume_worker):
            if worker is not None and worker.isRunning():
                worker.requestInterruption()
                worker.wait(500)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        size = 128 if self.width() >= self.height() else 150
        self.loading_spinner.setFixedSize(size, size)
