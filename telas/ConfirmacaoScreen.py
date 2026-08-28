import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QStackedLayout, QVBoxLayout, QWidget
)

from styles.svg_icons import ColoredSvgLabel
from styles.theme import Theme
from styles.tokens import Colors, Spacing


class ConfirmacaoScreen(QWidget):
    """Resultado aprovado; mantém a compra até o cliente tocar em Finalizar."""

    POST_PURCHASE_TIMEOUT_SECONDS = 120

    UNAVAILABLE_MESSAGES = {
        "CPF": (
            "ADICIONAR CPF",
            "O backend ainda não possui um contrato para associar CPF a esta compra. "
            "Nenhum dado foi gravado.",
        ),
        "E-MAIL": (
            "COMPROVANTE POR E-MAIL",
            "O envio de comprovante por e-mail ainda não está disponível. "
            "O pagamento continua aprovado.",
        ),
        "WHATSAPP": (
            "COMPROVANTE POR WHATSAPP",
            "A integração de comprovante com WhatsApp ainda não está disponível. "
            "O pagamento continua aprovado.",
        ),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self.setObjectName("confirmationScreen")
        self.setStyleSheet(Theme.confirmation_stylesheet())
        self._post_deadline = None

        self.pages = QStackedLayout(self)
        self.pages.setContentsMargins(0, 0, 0, 0)
        self.success_page = self._build_success_page()
        self.notice_page = self._build_notice_page()
        self.pages.addWidget(self.success_page)
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
        self.btn_finalizar = self._button("FINALIZAR", "statePrimary")
        self.btn_finalizar.setProperty("primaryAction", True)
        self.btn_finalizar.clicked.connect(self.finalizar_e_voltar)
        self.btn_cpf = self._button("ADICIONAR CPF", "stateSecondary")
        self.btn_cpf.clicked.connect(lambda: self._show_unavailable("CPF"))
        self.btn_email = self._button(
            "ENVIAR COMPROVANTE POR E-MAIL", "stateSecondary"
        )
        self.btn_email.clicked.connect(lambda: self._show_unavailable("E-MAIL"))
        self.btn_whatsapp = self._button(
            "ENVIAR COMPROVANTE POR WHATSAPP", "stateSecondary"
        )
        self.btn_whatsapp.clicked.connect(lambda: self._show_unavailable("WHATSAPP"))
        for button in (self.btn_cpf, self.btn_email, self.btn_whatsapp):
            root.addWidget(button)
        root.addSpacing(Spacing.XS)
        root.addWidget(self.btn_finalizar)
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
        back.clicked.connect(lambda: self.pages.setCurrentWidget(self.success_page))
        root.addWidget(back)
        return page

    @staticmethod
    def _button(text, variant):
        button = QPushButton(text)
        button.setProperty("variant", variant)
        return button

    def mostrar_tela(self):
        total = "R$ 0,00"
        terminal = getattr(self.parent_app, "terminal", None)
        carrinho = getattr(terminal, "carrinho", None)
        if carrinho is not None:
            candidate = carrinho.total_formatado()
            if isinstance(candidate, str):
                total = candidate.replace(".", ",")
        self.lbl_total.setText(total)
        self.pages.setCurrentWidget(self.success_page)
        self.btn_finalizar.setFocus()
        self._post_deadline = time.monotonic() + self.POST_PURCHASE_TIMEOUT_SECONDS
        self._tick_post_timeout()
        self.post_timeout_timer.start()

    def _show_unavailable(self, action):
        title, message = self.UNAVAILABLE_MESSAGES[action]
        self.notice_title.setText(title)
        self.notice_message.setText(message)
        self.pages.setCurrentWidget(self.notice_page)

    def finalizar_e_voltar(self):
        self.post_timeout_timer.stop()
        self._post_deadline = None
        if self.parent_app:
            self.parent_app.reset_compra(outcome="finalized")
            self.parent_app.setCurrentWidget(self.parent_app.welcome)

    def stop(self):
        self.post_timeout_timer.stop()

    def _tick_post_timeout(self):
        if self._post_deadline is None:
            return
        remaining = max(0, int(self._post_deadline - time.monotonic() + 0.999))
        minutes, seconds = divmod(remaining, 60)
        text = f"Finalizando em {minutes:02}:{seconds:02}"
        self.post_timeout_label.setText(text)
        self.notice_timeout_label.setText(text)
        if remaining == 0:
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
