import logging

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from database.DatabaseProdutos import DatabaseProdutos
from database.PaymentListener import PaymentListener
from model.Carrinho import Carrinho
from model.Item import Item
from model.Produtos import Produtos
from styles.theme import Theme
from styles.tokens import Spacing, TouchSize
from telas.SessionTimerLabel import SessionTimerLabel


logger = logging.getLogger(__name__)


class ProductCard(QFrame):
    """Card touchscreen que apresenta somente dados úteis ao consumidor."""

    def __init__(self, item, remove_callback, parent=None):
        super().__init__(parent)
        self.item = item
        self.setObjectName("productRow")
        self.setMinimumHeight(190)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        layout.setSpacing(Spacing.SM)

        self.name = QLabel()
        self.name.setProperty("role", "productCardName")
        self.name.setWordWrap(True)
        self.name.setAlignment(Qt.AlignCenter)
        self.name.setMaximumHeight(68)
        self.price = QLabel()
        self.price.setProperty("role", "productCardPrice")
        self.price.setAlignment(Qt.AlignCenter)
        self.quantity = QLabel()
        self.quantity.setProperty("role", "productCardQuantity")
        self.quantity.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        remove = QPushButton("REMOVER")
        remove.setProperty("variant", "remove")
        remove.setMinimumHeight(TouchSize.MINIMUM)
        remove.setAccessibleName(f"Remover {item.produto.nome}")
        remove.clicked.connect(remove_callback)

        bottom = QHBoxLayout()
        bottom.setSpacing(Spacing.MD)
        bottom.addWidget(self.quantity, 1)
        bottom.addWidget(remove)
        layout.addWidget(self.name)
        layout.addWidget(self.price)
        layout.addStretch(1)
        layout.addLayout(bottom)
        self.update_item(item)

    def update_item(self, item):
        self.item = item
        full_name = str(item.produto.nome or "Produto")
        display_name = full_name if len(full_name) <= 52 else f"{full_name[:49].rstrip()}…"
        self.name.setText(display_name)
        self.name.setToolTip(full_name)
        self.name.setAccessibleName(full_name)
        self.price.setText(f"R$ {item.subtotal():.2f}".replace(".", ","))
        self.quantity.setText(f"Qtd: {item.quantidade}")


class TerminalScreen(QWidget):
    """Carrinho visual; o objeto ``carrinho`` é a fonte única da compra atual."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self.parent = parent
        self.db = DatabaseProdutos()
        self.carrinho = Carrinho()
        self.linhas = {}
        self.total = 0.0
        self.id_contador = 1
        self.peso_total_venda = 0.0
        self._grid_columns = 2

        self.listener = PaymentListener(self)
        self.listener.payment_status_signal.connect(
            self.processar_evento_pagamento, Qt.QueuedConnection
        )
        self.listener.product_sync_required.connect(
            self.processar_evento_produto, Qt.QueuedConnection
        )
        self.listener.sync_requested.connect(
            self.solicitar_sync_produtos, Qt.QueuedConnection
        )
        self.listener.connected.connect(
            self.verificar_pagamento_apos_reconexao, Qt.QueuedConnection
        )
        self.listener.start()

        self.setProperty("role", "page")
        self.setObjectName("cartScreen")
        self.setStyleSheet(Theme.cart_stylesheet())
        self._montar_interface()

        self.timer_foco = QTimer(self)
        self.timer_foco.timeout.connect(self.garantir_foco)
        self.timer_foco.start(1000)

    def _montar_interface(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        root.setSpacing(Spacing.MD)

        self.header_card = QFrame(self)
        self.header_card.setObjectName("cartHeader")
        header = QHBoxLayout(self.header_card)
        header.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM)
        header.setSpacing(Spacing.MD)

        title = QLabel("SUA COMPRA")
        title.setProperty("role", "pageTitle")
        title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.session_timer = SessionTimerLabel(self.parent_app.compra_session, self)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.session_timer)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.productsContainer = QWidget()
        self.productsLayout = QGridLayout(self.productsContainer)
        self.productsLayout.setContentsMargins(0, 0, 0, 0)
        self.productsLayout.setSpacing(Spacing.MD)
        self.productsLayout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.scroll.setWidget(self.productsContainer)

        self.empty_label = None
        self._show_empty_state()

        scanner_layout = QHBoxLayout()
        scanner_layout.setSpacing(Spacing.MD)
        self.codigo_barras = QLineEdit()
        self.codigo_barras.setProperty("role", "input")
        self.codigo_barras.setPlaceholderText("Aguardando leitura do produto...")
        self.codigo_barras.returnPressed.connect(self.readProduct)

        self.peso_display = QLineEdit("0.000 KG")
        self.peso_display.setProperty("role", "input")
        self.peso_display.setReadOnly(True)
        self.peso_display.setMaximumWidth(190)
        self.peso_display.setAlignment(Qt.AlignCenter)
        scanner_layout.addWidget(self.codigo_barras, 3)
        scanner_layout.addWidget(self.peso_display, 1)

        self.footer_card = QFrame(self)
        self.footer_card.setObjectName("cartFooter")
        footer = QVBoxLayout(self.footer_card)
        footer.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.MD)
        footer.setSpacing(Spacing.SM)

        total_row = QHBoxLayout()
        total_label = QLabel("TOTAL")
        total_label.setObjectName("cartTotalLabel")
        self.totalBox = QLabel("R$ 0,00")
        self.totalBox.setObjectName("cartTotal")
        self.totalBox.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        total_row.addWidget(total_label)
        total_row.addStretch(1)
        total_row.addWidget(self.totalBox)

        actions = QHBoxLayout()
        actions.setSpacing(Spacing.MD)
        self.btn_cancelar = QPushButton("CANCELAR COMPRA")
        self.btn_cancelar.setProperty("variant", "ghost")
        self.btn_cancelar.clicked.connect(self.cancelar_venda)

        self.btn_finalizar = QPushButton("FINALIZAR")
        self.btn_finalizar.setProperty("variant", "primary")
        self.btn_finalizar.setProperty("primaryAction", True)
        self.btn_finalizar.setMinimumHeight(TouchSize.PRIMARY_BUTTON)
        self.btn_finalizar.clicked.connect(self.ir_para_pagamento)
        # Alias interno para compatibilidade com integrações/testes antigos.
        self.btn_pagar = self.btn_finalizar

        actions.addWidget(self.btn_cancelar, 1)
        actions.addWidget(self.btn_finalizar, 2)
        footer.addLayout(total_row)
        footer.addLayout(actions)

        root.addWidget(self.header_card)
        root.addWidget(self.scroll, 1)
        root.addLayout(scanner_layout)
        root.addWidget(self.footer_card)

    def atualizar_interface(self):
        self.totalBox.setText(self.carrinho.total_formatado().replace(".", ","))
        self.peso_display.setText(f"{self.peso_total_venda:.3f} KG")

    def atualizar_linha(self, codigo, label):
        item = self.carrinho.buscar_item(codigo)
        if not item or codigo not in self.linhas:
            return
        _, card, _ = self.linhas[codigo]
        card.update_item(item)

    def _show_empty_state(self):
        self.empty_label = QLabel("Nenhum produto escaneado")
        self.empty_label.setProperty("role", "pageSubtitle")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setMinimumHeight(120)
        self.productsLayout.addWidget(self.empty_label, 0, 0, 1, self._grid_columns)

    def _relayout_product_cards(self):
        cards = [entry[0] for entry in self.linhas.values()]
        for card in cards:
            self.productsLayout.removeWidget(card)
        for index, card in enumerate(cards):
            row, column = divmod(index, self._grid_columns)
            self.productsLayout.addWidget(card, row, column)
        for column in range(self._grid_columns):
            self.productsLayout.setColumnStretch(column, 1)

    def processar_evento_pagamento(self, data):
        if self.parent_app:
            self.parent_app.pagamento.processar_evento(data)

    def processar_evento_produto(self, event):
        self.solicitar_sync_produtos("WEBSOCKET_EVENT")

    def solicitar_sync_produtos(self, origin):
        sync_service = getattr(self.parent_app, "sync_service", None)
        if sync_service is not None:
            sync_service.request_sync(origin)

    def reconciliar_pagamento(self):
        if self.parent_app and self.parent_app.compra_session.payment_in_flight:
            self.parent_app.pagamento.reconciliar_estado()

    def verificar_pagamento_apos_reconexao(self):
        if self.parent_app and self.parent_app.compra_session.payment_in_flight:
            self.parent_app.pagamento.verificar_apos_reconexao()

    def liberar_tela(self):
        self.carrinho = Carrinho()
        self.linhas.clear()
        while self.productsLayout.count():
            layout_item = self.productsLayout.takeAt(0)
            widget = layout_item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.empty_label = None
        self._show_empty_state()
        self.total = 0.0
        self.id_contador = 1
        self.peso_total_venda = 0.0
        self.atualizar_interface()

    def garantir_foco(self):
        if self.parent and self.parent.stacked_widget.currentWidget() == self:
            if not self.codigo_barras.hasFocus():
                self.codigo_barras.setFocus()

    def ir_para_pagamento(self):
        """Abre o resumo; nenhuma chamada remota é iniciada neste toque."""
        if not self.linhas:
            self.mostrar_aviso(
                "Carrinho vazio", "Adicione pelo menos um produto antes de continuar."
            )
            return
        if self.parent_app:
            self.parent_app.confirmacao_compra.mostrar_resumo()
            self.parent_app.setCurrentWidget(self.parent_app.confirmacao_compra)

    def iniciar_pagamento_confirmado(self):
        """Único ponto visual que encaminha o carrinho atual ao fluxo Point."""
        if self.parent_app and not self.carrinho.vazio():
            self.parent_app.pagamento.iniciar_pagamento(
                self.carrinho.to_dict(), self.totalBox.text()
            )

    def cancelar_venda(self):
        if self.parent_app:
            self.parent_app.reset_compra()
            self.parent_app.setCurrentWidget(self.parent_app.welcome)

    def remover_produto(self, codigo_produto, widget_linha):
        item = self.carrinho.buscar_item(codigo_produto)
        if not item:
            return
        self.carrinho.remover_item(codigo_produto)
        self.linhas.pop(codigo_produto, None)
        widget_linha.deleteLater()
        self._relayout_product_cards()
        self.atualizar_interface()
        if self.carrinho.vazio():
            self.parent_app.compra_session.cancel()
            self._show_empty_state()

    def readProduct(self):
        barcode = self.codigo_barras.text().strip()
        if not barcode:
            return
        try:
            product_tuple = self.db.buscar_por_codigo(barcode)
            if not product_tuple:
                self.mostrar_aviso(
                    "Produto não encontrado", "O produto informado não está cadastrado."
                )
                self.codigo_barras.clear()
                return

            produto = Produtos.from_tuple(product_tuple)
            codigo = produto.codigo
            self.parent_app.compra_session.start_if_needed()

            if codigo in self.linhas:
                item = self.carrinho.buscar_item(codigo)
                item.quantidade += 1
                _, label, _ = self.linhas[codigo]
                self.atualizar_interface()
                self.atualizar_linha(codigo, label)
                self.codigo_barras.clear()
                self.codigo_barras.setFocus()
                return

            if self.empty_label is not None:
                self.empty_label.setParent(None)
                self.empty_label.deleteLater()
                self.empty_label = None

            novo_item = Item(produto=produto, quantidade=1, received_weight=None)
            self.carrinho.adicionar_item(novo_item)
            item = self.carrinho.buscar_item(codigo)
            id_linha = self.id_contador

            linha_widget = ProductCard(
                item,
                lambda _, c=codigo: self.remover_produto(
                    c, self.linhas[c][0]
                ),
                self.productsContainer,
            )
            self.linhas[codigo] = (linha_widget, linha_widget, id_linha)
            self._relayout_product_cards()

            self.atualizar_interface()
            self.id_contador += 1
            self.codigo_barras.clear()
            self.codigo_barras.setFocus()
        except Exception:
            logger.exception("Erro ao processar leitura do produto")
            self.mostrar_aviso(
                "Não foi possível ler o produto",
                "Tente escanear novamente. Se o problema continuar, chame o responsável.",
            )

    def mostrar_aviso(self, titulo, mensagem):
        QMessageBox.warning(self, titulo, mensagem, QMessageBox.Ok)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        columns = 2 if self.width() >= 800 else 1
        if columns != self._grid_columns:
            self._grid_columns = columns
            if self.empty_label is not None:
                self.productsLayout.removeWidget(self.empty_label)
                self.productsLayout.addWidget(
                    self.empty_label, 0, 0, 1, self._grid_columns
                )
            else:
                self._relayout_product_cards()
