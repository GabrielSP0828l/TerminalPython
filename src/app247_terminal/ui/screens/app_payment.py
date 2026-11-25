import logging
import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from app247_terminal.models.purchase_session import APP_PAYMENT_TIMEOUT_SECONDS
from app247_terminal.services.purchase_api import AppCheckoutWorker
from app247_terminal.ui.styles.theme import Theme
from app247_terminal.ui.styles.tokens import Spacing
from app247_terminal.services import shutdown_budget


logger = logging.getLogger(__name__)


class AppPaymentScreen(QWidget):
    """Fluxo legado preservado, mas sem entrada na tela principal da compra."""

    SCREEN_TIMEOUT_SECONDS = APP_PAYMENT_TIMEOUT_SECONDS

    def __init__(self, parent, clock=None):
        super().__init__(parent)
        self.parent = parent
        self.checkout_worker = None
        self._clock = clock or time.monotonic
        self._screen_deadline = None
        self.screen_timer = QTimer(self)
        self.screen_timer.setInterval(1000)
        self.screen_timer.timeout.connect(self._tick_screen_timeout)
        self.setProperty("role", "page")
        self.setObjectName("appPaymentScreen")
        self.setStyleSheet(Theme.app_payment_stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        root.setAlignment(Qt.AlignCenter)

        self.card = QFrame(self)
        self.card.setObjectName("appPaymentCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(Spacing.XXL, Spacing.XL, Spacing.XXL, Spacing.XL)
        card_layout.setSpacing(Spacing.LG)

        title = QLabel("CONTINUE O PAGAMENTO NO APP")
        title.setProperty("role", "pageTitle")
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)

        self.total_label = QLabel("R$ 0,00")
        self.total_label.setObjectName("appPaymentTotal")
        self.total_label.setAlignment(Qt.AlignCenter)
        self.timer_label = QLabel()
        self.timer_label.setObjectName("appPaymentTimer")
        self.timer_label.setAlignment(Qt.AlignCenter)

        self.loading = QLabel("Gerando QR Code...")
        self.loading.setProperty("state", "loading")
        self.loading.setAlignment(Qt.AlignCenter)
        self.loading.setWordWrap(True)
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)

        self.status = QLabel("Aguardando...")
        self.status.setProperty("role", "pageSubtitle")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)

        self.btn_cancelar = QPushButton("VOLTAR PARA A COMPRA")
        self.btn_cancelar.setProperty("variant", "secondary")
        self.btn_cancelar.clicked.connect(self.cancelar_pagamento)

        card_layout.addWidget(title)
        card_layout.addWidget(self.total_label)
        card_layout.addWidget(self.timer_label)
        card_layout.addWidget(self.loading)
        card_layout.addWidget(self.qr_label, 1)
        card_layout.addWidget(self.status)
        card_layout.addWidget(self.btn_cancelar)
        root.addWidget(self.card, 1)

        self.parent.compra_session.remaining_changed.connect(self.atualizar_contador)
        self.atualizar_contador(self.parent.compra_session.remaining_seconds())

    def iniciar_pagamento(self, valor):
        self.total_label.setText(valor)
        self.loading.show()
        self.loading.setText("Gerando pagamento no aplicativo...")
        self.qr_label.clear()
        self.status.setText("Preparando checkout...")
        self.status.setProperty("state", "loading")
        self._screen_deadline = self._clock() + self.SCREEN_TIMEOUT_SECONDS
        self.screen_timer.start()
        self.atualizar_contador(self.parent.compra_session.remaining_seconds())
        if self.checkout_worker and self.checkout_worker.isRunning():
            return
        self.checkout_worker = AppCheckoutWorker(
            self.parent.terminal.carrinho.to_dict(), parent=self
        )
        self.checkout_worker.succeeded.connect(self._checkout_ready)
        self.checkout_worker.failed.connect(self._checkout_failed)
        self.checkout_worker.finished.connect(self._checkout_worker_finished)
        self.checkout_worker.start()

    def _checkout_worker_finished(self):
        worker, self.checkout_worker = self.checkout_worker, None
        if worker is not None:
            worker.deleteLater()

    def _checkout_ready(self, data):
        pixmap = QPixmap()
        pixmap.loadFromData(data["image"])
        self.loading.hide()
        target = max(240, min(420, int(min(self.width(), self.height()) * 0.48)))
        self.qr_label.setPixmap(
            pixmap.scaled(target, target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        self.status.setText("Escaneie o QR Code com o aplicativo")
        self.status.setProperty("state", "info")

    def _checkout_failed(self, message):
        self.loading.show()
        self.loading.setProperty("state", "error")
        self.loading.setText("Não foi possível gerar o pagamento no aplicativo.")
        self.status.setText("O carrinho foi preservado. Tente novamente.")

    def remaining_seconds(self, session_remaining=None):
        """O menor entre o limite desta tela e o teto da compra."""
        if session_remaining is None:
            session_remaining = self.parent.compra_session.remaining_seconds()
        remaining = max(0, int(session_remaining))
        if self._screen_deadline is not None:
            screen_remaining = int(self._screen_deadline - self._clock() + 0.999)
            remaining = min(remaining, max(0, screen_remaining))
        return remaining

    def atualizar_contador(self, remaining_seconds):
        minutos, segundos = divmod(self.remaining_seconds(remaining_seconds), 60)
        self.timer_label.setText(f"{minutos:02}:{segundos:02}")

    def _tick_screen_timeout(self):
        session_remaining = self.parent.compra_session.remaining_seconds()
        self.atualizar_contador(session_remaining)
        if self._screen_deadline is None or session_remaining <= 0:
            # O teto já encerra a compra pelo próprio sinal.
            return
        if self.remaining_seconds(session_remaining) > 0:
            return
        logger.warning("[APP-PAYMENT] tempo da tela esgotado")
        self._stop_screen_timeout()
        self.parent.encerrar_compra_por_inatividade()

    def _stop_screen_timeout(self):
        self.screen_timer.stop()
        self._screen_deadline = None

    def cancelar_pagamento(self):
        self._stop_screen_timeout()
        self.parent.setCurrentWidget(self.parent.terminal)

    def parar_espera(self):
        self._stop_screen_timeout()
        self.qr_label.clear()
        if self.checkout_worker is not None and self.checkout_worker.isRunning():
            self.checkout_worker.requestInterruption()
            self.checkout_worker.wait(shutdown_budget.wait_ms(25000))
        if self.checkout_worker is not None and not self.checkout_worker.isRunning():
            worker, self.checkout_worker = self.checkout_worker, None
            worker.deleteLater()
