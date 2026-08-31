import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from styles.theme import Theme
from styles.tokens import Spacing, TouchSize
from telas.SessionTimerLabel import SessionTimerLabel
from model.Money import format_brl


logger = logging.getLogger(__name__)


class ConfirmacaoCompraScreen(QWidget):
    """Resumo pré-pagamento que lê o carrinho ativo sem duplicá-lo."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent_app = parent
        self.setProperty("role", "page")
        self.setObjectName("purchaseConfirmationScreen")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(Theme.purchase_confirmation_stylesheet())
        self._checkout_interactions_enabled = True

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        root.setSpacing(Spacing.SM)

        title = QLabel("CONFIRME SUA COMPRA")
        title.setObjectName("purchaseConfirmationTitle")
        title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        title_row = QHBoxLayout()
        title_row.setSpacing(Spacing.MD)
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.session_timer = SessionTimerLabel(self.parent_app.compra_session, self)
        title_row.addWidget(self.session_timer)
        self.item_count = QLabel()
        self.item_count.setObjectName("confirmationItemCount")
        self.item_count.setAlignment(Qt.AlignLeft)

        self.card = QFrame(self)
        self.card.setObjectName("purchaseConfirmationCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.items_widget = QWidget()
        self.items_layout = QVBoxLayout(self.items_widget)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(Spacing.MD)
        self.items_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.items_widget)
        card_layout.addWidget(self.scroll)

        total_card = QFrame(self)
        total_card.setObjectName("confirmationTotalCard")
        total_row = QHBoxLayout(total_card)
        total_row.setContentsMargins(Spacing.LG, Spacing.XS, Spacing.LG, Spacing.XS)
        total_caption = QLabel("TOTAL")
        total_caption.setObjectName("confirmationTotalCaption")
        self.total = QLabel("R$ 0,00")
        self.total.setObjectName("confirmationTotal")
        total_row.addWidget(total_caption)
        total_row.addStretch(1)
        total_row.addWidget(self.total)

        self.btn_voltar = QPushButton("VOLTAR")
        self.btn_voltar.setProperty("variant", "secondary")
        self.btn_voltar.setProperty("confirmationAction", True)
        self.btn_voltar.setMinimumHeight(TouchSize.PRIMARY_BUTTON)
        self.btn_voltar.clicked.connect(self.voltar)
        self.btn_confirmar = QPushButton("CONFIRMAR E PAGAR")
        self.btn_confirmar.setProperty("variant", "primary")
        self.btn_confirmar.setProperty("primaryAction", True)
        self.btn_confirmar.setProperty("confirmationAction", True)
        self.btn_confirmar.setMinimumHeight(TouchSize.PRIMARY_BUTTON)
        self.btn_confirmar.clicked.connect(self.confirmar)

        actions = QHBoxLayout()
        actions.setSpacing(Spacing.MD)
        actions.addWidget(self.btn_voltar, 1)
        actions.addWidget(self.btn_confirmar, 2)

        root.addLayout(title_row)
        root.addWidget(self.item_count)
        root.addWidget(self.card, 1)
        root.addWidget(total_card)
        root.addLayout(actions)

    @property
    def carrinho(self):
        return self.parent_app.terminal.carrinho

    def mostrar_resumo(self):
        enabled = (
            self._checkout_interactions_enabled
            and self.parent_app.compra_session.can_accept_checkout_actions()
        )
        self.btn_confirmar.setEnabled(enabled)
        self.btn_voltar.setEnabled(enabled)
        self.btn_confirmar.setText("CONFIRMAR E PAGAR")
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        quantity = self.carrinho.quantidade_total_itens()
        suffix = "item" if quantity == 1 else "itens"
        self.item_count.setText(f"{quantity} {suffix}")
        for cart_item in self.carrinho.listar_itens():
            row = QFrame()
            row.setProperty("role", "information")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
            details = QVBoxLayout()
            details.setSpacing(Spacing.XS)
            name = QLabel(str(cart_item.produto.nome))
            name.setProperty("role", "confirmationProductName")
            name.setWordWrap(True)
            quantity = QLabel(f"Qtd: {cart_item.quantidade}")
            quantity.setProperty("role", "confirmationProductQuantity")
            if cart_item.produto.em_promocao:
                original = cart_item.produto.preco_original * cart_item.quantidade
                details.addWidget(QLabel(
                    f"De {format_brl(original)} · PROMOÇÃO".replace(".", ",")
                ))
            price = QLabel(format_brl(cart_item.subtotal()).replace(".", ","))
            price.setProperty("role", "confirmationProductPrice")
            price.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            details.addWidget(name)
            details.addWidget(quantity)
            layout.addLayout(details, 3)
            layout.addWidget(price, 1)
            self.items_layout.addWidget(row)
        self.total.setText(self.carrinho.total_formatado().replace(".", ","))

    def voltar(self):
        if not self._checkout_interactions_enabled:
            return
        self.parent_app.setCurrentWidget(self.parent_app.terminal)

    def confirmar(self):
        logger.info("[PAYMENT-UI] confirmar clicado")
        if (
            not self._checkout_interactions_enabled
            or not self.parent_app.compra_session.can_accept_checkout_actions()
            or self.carrinho.vazio()
            or not self.btn_confirmar.isEnabled()
        ):
            logger.warning("[PAYMENT-UI] confirmar ignorado por estado inválido")
            return
        self.btn_confirmar.setEnabled(False)
        self.btn_voltar.setEnabled(False)
        self.btn_confirmar.setText("PREPARANDO...")
        started = self.parent_app.terminal.iniciar_pagamento_confirmado()
        if not started:
            logger.error("[PAYMENT-UI] inicialização recusada antes do worker")
            self.btn_confirmar.setText("CONFIRMAR E PAGAR")
            self.btn_confirmar.setEnabled(True)
            self.btn_voltar.setEnabled(True)

    def set_checkout_interactions_enabled(self, enabled):
        self._checkout_interactions_enabled = bool(enabled)
        self.btn_voltar.setEnabled(enabled)
        self.btn_confirmar.setEnabled(enabled)
