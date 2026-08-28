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


class ConfirmacaoCompraScreen(QWidget):
    """Resumo pré-pagamento que lê o carrinho ativo sem duplicá-lo."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent_app = parent
        self.setProperty("role", "page")
        self.setObjectName("purchaseConfirmationScreen")
        self.setStyleSheet(Theme.purchase_confirmation_stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        root.setSpacing(Spacing.LG)

        title = QLabel("CONFIRME SUA COMPRA")
        title.setProperty("role", "pageTitle")
        title.setAlignment(Qt.AlignCenter)
        self.item_count = QLabel()
        self.item_count.setObjectName("confirmationItemCount")
        self.item_count.setAlignment(Qt.AlignCenter)

        self.card = QFrame(self)
        self.card.setObjectName("purchaseConfirmationCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.items_widget = QWidget()
        self.items_layout = QVBoxLayout(self.items_widget)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(Spacing.MD)
        self.items_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.items_widget)
        card_layout.addWidget(self.scroll)

        total_row = QHBoxLayout()
        total_caption = QLabel("TOTAL")
        total_caption.setProperty("role", "sectionTitle")
        self.total = QLabel("R$ 0,00")
        self.total.setObjectName("confirmationTotal")
        total_row.addWidget(total_caption)
        total_row.addStretch(1)
        total_row.addWidget(self.total)

        self.btn_voltar = QPushButton("VOLTAR")
        self.btn_voltar.setProperty("variant", "secondary")
        self.btn_voltar.clicked.connect(self.voltar)
        self.btn_confirmar = QPushButton("CONFIRMAR E PAGAR")
        self.btn_confirmar.setProperty("variant", "primary")
        self.btn_confirmar.setProperty("primaryAction", True)
        self.btn_confirmar.setMinimumHeight(TouchSize.PRIMARY_BUTTON)
        self.btn_confirmar.clicked.connect(self.confirmar)

        root.addWidget(title)
        root.addWidget(self.item_count)
        root.addWidget(self.card, 1)
        root.addLayout(total_row)
        root.addWidget(self.btn_confirmar)
        root.addWidget(self.btn_voltar)

    @property
    def carrinho(self):
        return self.parent_app.terminal.carrinho

    def mostrar_resumo(self):
        self.btn_confirmar.setEnabled(True)
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
            layout = QVBoxLayout(row)
            layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
            name = QLabel(f"{cart_item.quantidade} × {cart_item.produto.nome}")
            name.setProperty("role", "productName")
            name.setWordWrap(True)
            price = QLabel(f"R$ {cart_item.subtotal():.2f}")
            price.setProperty("role", "productPrice")
            price.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            layout.addWidget(name)
            layout.addWidget(price)
            self.items_layout.addWidget(row)
        self.total.setText(self.carrinho.total_formatado())

    def voltar(self):
        self.parent_app.setCurrentWidget(self.parent_app.terminal)

    def confirmar(self):
        if self.carrinho.vazio() or not self.btn_confirmar.isEnabled():
            return
        self.btn_confirmar.setEnabled(False)
        self.btn_confirmar.setText("PREPARANDO...")
        self.parent_app.terminal.iniciar_pagamento_confirmado()
