import logging

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from model.Terminal import Terminal
from service.PurchaseApi import OrderStatusWorker, PointCheckoutWorker, PointResumeWorker
from styles.theme import Theme


logger = logging.getLogger(__name__)


class PagamentoScreen(QWidget):
    POLL_INTERVAL_MS = 5000

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.current_attempt = None
        self.point_worker = None
        self.status_worker = None
        self.resume_worker = None
        self.timeout_pending = False

        self.setObjectName("pointPaymentScreen")
        self.setStyleSheet(Theme.payment_stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setAlignment(Qt.AlignCenter)

        self.card = QFrame(self)
        self.card.setObjectName("paymentCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(40, 32, 40, 32)
        card_layout.setSpacing(18)

        self.title = QLabel("PREPARANDO PAGAMENTO")
        self.title.setObjectName("paymentTitle")
        self.title.setAlignment(Qt.AlignCenter)

        self.total_final = QLabel("R$ 0,00")
        self.total_final.setObjectName("paymentTotal")
        self.total_final.setAlignment(Qt.AlignCenter)

        self.loading = QLabel("●  Preparando compra...")
        self.loading.setObjectName("paymentLoading")
        self.loading.setProperty("state", "loading")
        self.loading.setAlignment(Qt.AlignCenter)

        self.instructions = QLabel()
        self.instructions.setObjectName("paymentInstructions")
        self.instructions.setAlignment(Qt.AlignCenter)
        self.instructions.setWordWrap(True)

        self.timer_label = QLabel("Tempo restante: 15:00")
        self.timer_label.setObjectName("paymentTimer")
        self.timer_label.setAlignment(Qt.AlignCenter)

        self.btn_voltar = QPushButton("VOLTAR PARA A COMPRA")
        self.btn_voltar.setProperty("variant", "secondary")
        self.btn_voltar.clicked.connect(self._voltar_lista)
        self.btn_voltar.hide()

        card_layout.addWidget(self.title)
        card_layout.addWidget(self.total_final)
        card_layout.addStretch(1)
        card_layout.addWidget(self.loading)
        card_layout.addWidget(self.instructions)
        card_layout.addWidget(self.timer_label)
        card_layout.addStretch(1)
        card_layout.addWidget(self.btn_voltar)
        root.addWidget(self.card)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.reconciliar_estado)
        self.parent.compra_session.remaining_changed.connect(self._update_countdown)

    def iniciar_pagamento(self, cart_payload, total_text):
        attempt = self.parent.compra_session.begin_payment()
        if attempt is None:
            return
        self.current_attempt = attempt
        self.timeout_pending = False
        self.total_final.setText(total_text)
        self.title.setText("PREPARANDO PAGAMENTO")
        self.loading.setText("●  Criando pedido e enviando para a maquininha...")
        self.loading.setProperty("state", "loading")
        self.instructions.setText("Aguarde. Esta operação pode levar alguns segundos.")
        self.btn_voltar.hide()
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

    def _point_started(self, attempt, data):
        if attempt != self.current_attempt:
            return
        payment = data.get("pagamento") or {}
        self.parent.compra_session.set_remote_ids(
            data.get("cartId"),
            data.get("orderId"),
            payment.get("pagamentoId"),
        )
        self.parent.compra_session.mark_waiting()
        self.title.setText("AGUARDANDO PAGAMENTO")
        self.loading.setText("●  Pagamento enviado para a maquininha")
        self.instructions.setText(
            "Pressione o botão verde da maquininha para visualizar ou continuar "
            "o pagamento.\nSiga as instruções exibidas na maquininha.\n\n"
            "Não feche esta tela."
        )
        self.poll_timer.start(self.POLL_INTERVAL_MS)
        self._apply_payload(data)

    def _point_failed(self, attempt, message, stage, ambiguous, context):
        if attempt != self.current_attempt:
            return
        logger.warning("Falha ao iniciar Point: stage=%s ambiguous=%s message=%s", stage, ambiguous, message)
        if context:
            self.parent.compra_session.set_remote_ids(
                context.get("cartId"), context.get("orderId")
            )
        if ambiguous and self.parent.compra_session.cart_id:
            self.parent.compra_session.mark_waiting()
            self.title.setText("CONFIRMANDO PAGAMENTO")
            self.loading.setText("●  Verificando se a cobrança foi enviada...")
            self.instructions.setText(
                "A conexão oscilou. Não tente pagar novamente enquanto confirmamos o estado."
            )
            self.poll_timer.start(self.POLL_INTERVAL_MS)
            self._retomar_inicio_point()
            return
        self._safe_failure("Não foi possível iniciar o pagamento. O carrinho foi preservado.")

    def processar_evento(self, data):
        session = self.parent.compra_session
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
            data.get("orderId"), status, payment.get("transactionId")
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
            if self.timeout_pending:
                self.parent.reset_compra()
                self.parent.setCurrentWidget(self.parent.welcome)
            else:
                self._safe_failure("Pagamento não confirmado. Você pode tentar novamente.")
        elif result == "PROCESSING":
            self.loading.setText("●  Pagamento enviado. Aguardando confirmação...")

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
        self.status_worker = OrderStatusWorker(
            order_id, terminal.terminalId, parent=self
        )
        self.status_worker.succeeded.connect(
            lambda data, oid=expected_order: self._status_received(oid, data)
        )
        self.status_worker.failed.connect(self._status_failed)
        self.status_worker.start()

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
        self.loading.setText("●  Reconectando e confirmando o pagamento...")

    def tratar_timeout_global(self, generation):
        session = self.parent.compra_session
        if generation != session.generation:
            return
        if not session.order_id and not session.cart_id:
            self.parent.reset_compra()
            self.parent.setCurrentWidget(self.parent.welcome)
            return
        self.timeout_pending = True
        self.parent.setCurrentWidget(self)
        self.title.setText("CONFIRMANDO PAGAMENTO")
        self.loading.setText("●  Verificando o estado final da compra...")
        self.instructions.setText(
            "O tempo da compra terminou. Aguarde a confirmação antes de iniciar outra compra."
        )
        self.poll_timer.start(self.POLL_INTERVAL_MS)
        if session.order_id:
            self.reconciliar_estado()
        else:
            self._retomar_inicio_point()

    def _safe_failure(self, message):
        self.loading.setProperty("state", "error")
        self.loading.style().unpolish(self.loading)
        self.loading.style().polish(self.loading)
        self.loading.setText(message)
        self.instructions.setText("Os produtos continuam na lista da compra.")
        self.btn_voltar.show()
        self.parent.compra_session.prepare_retry()

    def _voltar_lista(self):
        if not self.parent.compra_session.payment_in_flight:
            self.parent.setCurrentWidget(self.parent.terminal)

    def _update_countdown(self, seconds):
        minutes, remainder = divmod(max(0, seconds), 60)
        self.timer_label.setText(f"Tempo restante: {minutes:02}:{remainder:02}")

    def parar_espera(self):
        self.poll_timer.stop()
        self.current_attempt = None
