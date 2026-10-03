import logging
import time
from decimal import Decimal

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QStackedLayout, QVBoxLayout, QWidget
)

from model.Terminal import Terminal
from service.PurchaseApi import PurchaseApi, PurchaseApiError, ReceiptSendWorker
from styles.svg_icons import ColoredSvgLabel
from styles.theme import Theme
from styles.tokens import Colors, Spacing
from model.Money import format_brl
from telas.teclado import EmailKeyboard, NumericKeyboard


logger = logging.getLogger(__name__)


class ConfirmacaoScreen(QWidget):
    """Resultado aprovado; mantém a compra até o cliente tocar em Finalizar."""

    POST_PURCHASE_TIMEOUT_SECONDS = 120

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self.setObjectName("confirmationScreen")
        self.setStyleSheet(Theme.confirmation_stylesheet())
        self._post_deadline = None
        self.post_purchase_order_id = None
        self.receipt_send_in_progress = False
        self.receipt_worker = None
        self.receipt_channel = None

        self.pages = QStackedLayout(self)
        self.pages.setContentsMargins(0, 0, 0, 0)
        self.success_page = self._build_success_page()
        self.input_page = self._build_input_page()
        self.notice_page = self._build_notice_page()
        self.pages.addWidget(self.success_page)
        self.pages.addWidget(self.input_page)
        self.pages.addWidget(self.notice_page)
        self.post_timeout_timer = QTimer(self)
        self.post_timeout_timer.setInterval(1000)
        self.post_timeout_timer.timeout.connect(self._tick_post_timeout)

    def _build_success_page(self):
        page = QWidget(self)
        page.setProperty("paymentState", "success")
        root = QVBoxLayout(page)
        root.setContentsMargins(Spacing.XL, Spacing.MD, Spacing.XL, Spacing.MD)
        root.setSpacing(Spacing.SM)
        top = QHBoxLayout()
        top.addStretch(1)
        self.post_timeout_label = QLabel()
        self.post_timeout_label.setProperty("role", "sessionTimer")
        top.addWidget(self.post_timeout_label)
        root.addLayout(top)

        self.lbl_icon = ColoredSvgLabel(
            "checked.svg", Colors.PAYMENT_STATE_FOREGROUND, "✓", page
        )
        self.lbl_icon.setObjectName("paymentStateIcon")
        self.lbl_icon.setMinimumSize(88, 88)
        self.lbl_icon.setMaximumSize(112, 112)
        root.addWidget(self.lbl_icon, 0, Qt.AlignHCenter)

        self.lbl_sucesso = QLabel("PAGAMENTO APROVADO")
        self.lbl_sucesso.setObjectName("paymentStateTitle")
        self.lbl_sucesso.setAlignment(Qt.AlignCenter)
        self.lbl_sucesso.setWordWrap(True)
        root.addWidget(self.lbl_sucesso)

        self.lbl_subtext = QLabel("TOTAL")
        self.lbl_subtext.setObjectName("paymentStateSupporting")
        self.lbl_subtext.setAlignment(Qt.AlignCenter)
        root.addWidget(self.lbl_subtext)

        self.lbl_total = QLabel("R$ 0,00")
        self.lbl_total.setObjectName("paymentStateTotal")
        self.lbl_total.setAlignment(Qt.AlignCenter)
        root.addWidget(self.lbl_total)
        actions = QGridLayout()
        actions.setHorizontalSpacing(Spacing.MD)
        actions.setVerticalSpacing(Spacing.SM)
        self.btn_finalizar = self._button("FINALIZAR", "statePrimary")
        self.btn_finalizar.setProperty("primaryAction", True)
        self.btn_finalizar.clicked.connect(self.finalizar_e_voltar)
        self.btn_cpf = self._button("ADICIONAR CPF", "stateSecondary")
        self.btn_cpf.setEnabled(False)
        self.btn_cpf.setToolTip(
            "Aguardando contrato do backend para associar CPF à compra"
        )
        self.btn_email = self._button(
            "ENVIAR POR E-MAIL", "stateSecondary"
        )
        self.btn_email.clicked.connect(lambda: self._open_receipt_input("EMAIL"))
        self.btn_whatsapp = self._button(
            "ENVIAR POR WHATSAPP", "stateSecondary"
        )
        self.btn_whatsapp.clicked.connect(
            lambda: self._open_receipt_input("WHATSAPP")
        )
        actions.addWidget(self.btn_finalizar, 0, 0)
        actions.addWidget(self.btn_cpf, 0, 1)
        actions.addWidget(self.btn_whatsapp, 1, 0)
        actions.addWidget(self.btn_email, 1, 1)
        root.addLayout(actions)
        return page

    def _build_input_page(self):
        page = QWidget(self)
        page.setObjectName("receiptInputPage")
        page.setProperty("paymentState", "success")
        root = QVBoxLayout(page)
        root.setContentsMargins(Spacing.XL, Spacing.MD, Spacing.XL, Spacing.MD)
        root.setSpacing(Spacing.SM)

        self.input_title = QLabel()
        self.input_title.setObjectName("postPaymentNoticeTitle")
        self.input_title.setAlignment(Qt.AlignCenter)
        root.addWidget(self.input_title)

        container = QFrame(page)
        container.setObjectName("inputContainer")
        container_layout = QVBoxLayout(container)
        self.destination_input = QLineEdit(container)
        self.destination_input.setProperty("role", "input")
        self.destination_input.setAlignment(Qt.AlignCenter)
        self.destination_input.setReadOnly(True)
        self.destination_input.setInputMethodHints(Qt.ImhNoPredictiveText)
        self.input_error = QLabel()
        self.input_error.setObjectName("receiptInputError")
        self.input_error.setAlignment(Qt.AlignCenter)
        self.input_error.setWordWrap(True)
        container_layout.addWidget(self.destination_input)
        container_layout.addWidget(self.input_error)
        root.addWidget(container)

        self.keyboard_container = QWidget(page)
        self.keyboard_pages = QStackedLayout(self.keyboard_container)
        self.numeric_keyboard = NumericKeyboard(self.keyboard_container)
        self.email_keyboard = EmailKeyboard(self.keyboard_container)
        self.numeric_keyboard.set_target(self.destination_input)
        self.email_keyboard.set_target(self.destination_input)
        self.numeric_keyboard.key_pressed.connect(self._format_phone_input)
        self.email_keyboard.key_pressed.connect(self._clear_input_error)
        self.keyboard_pages.addWidget(self.numeric_keyboard)
        self.keyboard_pages.addWidget(self.email_keyboard)
        root.addWidget(self.keyboard_container, 1)

        actions = QHBoxLayout()
        actions.setSpacing(Spacing.MD)
        self.btn_input_cancel = self._button("CANCELAR", "stateSecondary")
        self.btn_input_cancel.clicked.connect(self._cancel_receipt_input)
        self.btn_send_receipt = self._button("ENVIAR", "statePrimary")
        self.btn_send_receipt.setProperty("primaryAction", True)
        self.btn_send_receipt.clicked.connect(self._send_receipt)
        actions.addWidget(self.btn_input_cancel, 1)
        actions.addWidget(self.btn_send_receipt, 2)
        root.addLayout(actions)
        return page

    def _build_notice_page(self):
        page = QWidget(self)
        page.setProperty("paymentState", "success")
        root = QVBoxLayout(page)
        root.setContentsMargins(Spacing.XL, Spacing.LG, Spacing.XL, Spacing.LG)
        root.setSpacing(Spacing.XL)
        top = QHBoxLayout()
        top.addStretch(1)
        self.notice_timeout_label = QLabel()
        self.notice_timeout_label.setProperty("role", "sessionTimer")
        top.addWidget(self.notice_timeout_label)
        root.addLayout(top)
        root.addStretch(2)
        self.notice_title = QLabel()
        self.notice_title.setObjectName("postPaymentNoticeTitle")
        self.notice_title.setAlignment(Qt.AlignCenter)
        self.notice_title.setWordWrap(True)
        self.notice_message = QLabel()
        self.notice_message.setObjectName("postPaymentNoticeMessage")
        self.notice_message.setAlignment(Qt.AlignCenter)
        self.notice_message.setWordWrap(True)
        root.addWidget(self.notice_title)
        root.addWidget(self.notice_message)
        root.addStretch(3)
        back = self._button("VOLTAR", "statePrimary")
        back.clicked.connect(self._return_to_success)
        self.btn_notice_back = back
        root.addWidget(back)
        return page

    @staticmethod
    def _button(text, variant):
        button = QPushButton(text)
        button.setProperty("variant", variant)
        return button

    def mostrar_tela(self, recovered_amount=None):
        total = "R$ 0,00"
        carrinho = None
        if recovered_amount is not None:
            total = format_brl(Decimal(str(recovered_amount))).replace(".", ",")
        else:
            terminal = getattr(self.parent_app, "terminal", None)
            carrinho = getattr(terminal, "carrinho", None)
        if recovered_amount is None and carrinho is not None:
            candidate = carrinho.total_formatado()
            if isinstance(candidate, str):
                total = candidate.replace(".", ",")
        self.lbl_total.setText(total)
        session = getattr(self.parent_app, "compra_session", None)
        self.post_purchase_order_id = getattr(session, "order_id", None)
        approved = bool(
            self.post_purchase_order_id
            and getattr(session, "state", None) in {"APPROVED", "SUCCESS"}
        )
        self.btn_whatsapp.setEnabled(approved)
        self.btn_email.setEnabled(approved)
        self.btn_finalizar.setEnabled(approved)
        self.receipt_send_in_progress = False
        self.pages.setCurrentWidget(self.success_page)
        self.btn_finalizar.setFocus()
        if approved:
            self._start_post_timeout()
        else:
            self.post_timeout_timer.stop()
            self._post_deadline = None

    def _start_post_timeout(self):
        self._post_deadline = time.monotonic() + self.POST_PURCHASE_TIMEOUT_SECONDS
        self._tick_post_timeout()
        self.post_timeout_timer.start()

    def _show_notice(self, title, message):
        self.notice_title.setText(title)
        self.notice_message.setText(message)
        self.pages.setCurrentWidget(self.notice_page)

    def _open_receipt_input(self, channel):
        if not self._post_purchase_is_approved() or self.receipt_send_in_progress:
            return
        self.post_timeout_timer.stop()
        self._post_deadline = None
        self.receipt_channel = channel
        self.destination_input.clear()
        self._clear_input_error()
        if channel == "WHATSAPP":
            self.input_title.setText("ENVIAR COMPROVANTE POR WHATSAPP")
            self.destination_input.setPlaceholderText("(75) 99999-9999")
            self.destination_input.setMaxLength(19)
            self.keyboard_pages.setCurrentWidget(self.numeric_keyboard)
            self.numeric_keyboard.set_target(self.destination_input)
        else:
            self.input_title.setText("ENVIAR COMPROVANTE POR E-MAIL")
            self.destination_input.setPlaceholderText("cliente@email.com")
            self.destination_input.setMaxLength(160)
            self.keyboard_pages.setCurrentWidget(self.email_keyboard)
            self.email_keyboard.set_target(self.destination_input)
        logger.info(
            "[RECEIPT-UI] %s solicitado orderId=%s",
            channel.lower(), self.post_purchase_order_id,
        )
        self.pages.setCurrentWidget(self.input_page)

    def _cancel_receipt_input(self):
        if self.receipt_send_in_progress:
            return
        self.receipt_channel = None
        self.destination_input.clear()
        self._return_to_success()

    def _return_to_success(self):
        self.pages.setCurrentWidget(self.success_page)
        self._start_post_timeout()

    def _clear_input_error(self, _key=None):
        self.input_error.clear()

    def _format_phone_input(self, _key=None):
        self._clear_input_error()
        digits = "".join(filter(str.isdigit, self.destination_input.text()))[:13]
        local = digits
        prefix = ""
        if digits.startswith("55") and len(digits) > 11:
            prefix, local = "+55 ", digits[2:]
        formatted = local
        if len(local) > 2:
            formatted = f"({local[:2]}) {local[2:]}"
        subscriber_digits = local[2:]
        if len(subscriber_digits) > 4:
            split = 5 if len(subscriber_digits) > 8 else 4
            formatted = (
                f"({local[:2]}) {subscriber_digits[:split]}-"
                f"{subscriber_digits[split:]}"
            )
        self.destination_input.setText(prefix + formatted)

    def _send_receipt(self):
        if self.receipt_send_in_progress or not self._post_purchase_is_approved():
            return
        try:
            destination = PurchaseApi.normalize_receipt_destination(
                self.receipt_channel, self.destination_input.text()
            )
        except PurchaseApiError as error:
            self.input_error.setText(str(error))
            return
        terminal = Terminal.load()
        terminal_id = getattr(terminal, "terminalId", None) if terminal else None
        if not terminal_id:
            self.input_error.setText(
                "Terminal não identificado. Não foi possível enviar o comprovante."
            )
            return

        self.receipt_send_in_progress = True
        self.btn_send_receipt.setEnabled(False)
        self.btn_send_receipt.setText("ENVIANDO...")
        self.btn_input_cancel.setEnabled(False)
        logger.info(
            "[RECEIPT-UI] envio iniciado orderId=%s canal=%s destinatario=%s",
            self.post_purchase_order_id, self.receipt_channel,
            self._mask_destination(destination),
        )
        worker = ReceiptSendWorker(
            self.post_purchase_order_id, terminal_id, self.receipt_channel,
            destination, parent=self,
        )
        self.receipt_worker = worker
        worker.succeeded.connect(self._receipt_succeeded)
        worker.failed.connect(self._receipt_failed)
        worker.finished.connect(self._receipt_worker_finished)
        worker.start()

    def _receipt_succeeded(self, _response):
        channel = self.receipt_channel
        logger.info(
            "[RECEIPT-UI] envio concluído orderId=%s canal=%s",
            self.post_purchase_order_id, channel,
        )
        self._reset_send_controls()
        self._show_notice(
            "COMPROVANTE ENVIADO",
            "Comprovante enviado com sucesso. O pagamento continua aprovado.",
        )
        self._start_post_timeout()

    def _receipt_failed(self, message, reason):
        channel = self.receipt_channel
        logger.warning(
            "[RECEIPT-UI] envio falhou orderId=%s canal=%s reason=%s",
            self.post_purchase_order_id, channel, reason,
        )
        self._reset_send_controls()
        self._show_notice(
            "ENVIO NÃO CONCLUÍDO",
            message + " O pagamento continua aprovado.",
        )
        self._start_post_timeout()

    def _receipt_worker_finished(self):
        worker, self.receipt_worker = self.receipt_worker, None
        if worker is not None:
            worker.deleteLater()

    def _reset_send_controls(self):
        self.receipt_send_in_progress = False
        self.btn_send_receipt.setEnabled(True)
        self.btn_send_receipt.setText("ENVIAR")
        self.btn_input_cancel.setEnabled(True)

    def _post_purchase_is_approved(self):
        session = getattr(self.parent_app, "compra_session", None)
        return bool(
            self.post_purchase_order_id
            and self.post_purchase_order_id == getattr(session, "order_id", None)
            and getattr(session, "state", None) in {"APPROVED", "SUCCESS"}
        )

    @staticmethod
    def _mask_destination(destination):
        value = str(destination)
        if "@" in value:
            _, domain = value.split("@", 1)
            return f"***@{domain}"
        return "*" * max(0, len(value) - 4) + value[-4:]

    def finalizar_e_voltar(self):
        if self.receipt_send_in_progress or not self._post_purchase_is_approved():
            return
        self.post_timeout_timer.stop()
        self._post_deadline = None
        self.post_purchase_order_id = None
        if self.parent_app:
            self.parent_app.reset_compra(outcome="finalized")
            self.parent_app.setCurrentWidget(self.parent_app.welcome)

    def stop(self):
        self.post_timeout_timer.stop()
        worker = self.receipt_worker
        if worker is not None and hasattr(worker, "isRunning") and worker.isRunning():
            worker.requestInterruption()
            worker.wait(50000)
        if (worker is not None and hasattr(worker, "isRunning")
                and not worker.isRunning()):
            if self.receipt_worker is worker:
                self.receipt_worker = None
            worker.deleteLater()

    def _tick_post_timeout(self):
        if self._post_deadline is None:
            return
        remaining = max(0, int(self._post_deadline - time.monotonic() + 0.999))
        minutes, seconds = divmod(remaining, 60)
        text = f"Finalizando em {minutes:02}:{seconds:02}"
        self.post_timeout_label.setText(text)
        self.notice_timeout_label.setText(text)
        if remaining == 0 and not self.receipt_send_in_progress \
                and self.pages.currentWidget() is not self.input_page:
            self.finalizar_e_voltar()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.height() > self.width():
            self.success_page.layout().setContentsMargins(
                Spacing.XXXL, Spacing.XXL, Spacing.XXXL, Spacing.XXL
            )
            self.lbl_icon.setMinimumSize(160, 160)
            self.lbl_icon.setMaximumSize(200, 200)
        else:
            self.success_page.layout().setContentsMargins(
                Spacing.XL, Spacing.MD, Spacing.XL, Spacing.MD
            )
            self.lbl_icon.setMinimumSize(88, 88)
            self.lbl_icon.setMaximumSize(120, 120)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.pages.currentWidget() is self.success_page:
                self.finalizar_e_voltar()
        else:
            super().keyPressEvent(event)
