import logging
from decimal import Decimal

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFontMetrics
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
from model.Money import format_brl, persisted


logger = logging.getLogger(__name__)


class ProductCard(QFrame):
    """Card touchscreen que apresenta somente dados úteis ao consumidor."""

    HEIGHT = 280

    def __init__(self, item, remove_callback, parent=None):
        super().__init__(parent)
        self.item = item
        self.setObjectName("productRow")
        self.setFixedHeight(self.HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        layout.setSpacing(Spacing.SM)

        self.name = QLabel()
        self.name.setProperty("role", "productCardName")
        self.name.setWordWrap(True)
        self.name.setAlignment(Qt.AlignCenter)
        self.name.setFixedHeight(68)
        self.price = QLabel()
        self.price.setProperty("role", "productCardPrice")
        self.price.setAlignment(Qt.AlignCenter)
        self.original_price = QLabel()
        self.original_price.setProperty("role", "productCardOriginalPrice")
        self.original_price.setAlignment(Qt.AlignCenter)
        self.promotion_badge = QLabel("PROMOÇÃO")
        self.promotion_badge.setProperty("role", "promotionBadge")
        self.promotion_badge.setAlignment(Qt.AlignCenter)
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
        layout.addWidget(self.original_price)
        layout.addWidget(self.price)
        layout.addWidget(self.promotion_badge, alignment=Qt.AlignHCenter)
        layout.addStretch(1)
        layout.addLayout(bottom)
        self.update_item(item)

    def update_item(self, item):
        self.item = item
        self.full_name = str(item.produto.nome or "Produto")
        self._update_display_name()
        self.name.setToolTip(self.full_name)
        self.name.setAccessibleName(self.full_name)
        if item.produto.em_promocao:
            original_subtotal = item.produto.preco_original * item.quantidade
            self.original_price.setText(
                f"De {format_brl(original_subtotal)}".replace(".", ",")
            )
            self.original_price.show()
            self.promotion_badge.setText(
                str(item.produto.promocao_nome or "PROMOÇÃO").upper()
            )
            self.promotion_badge.show()
            self.price.setText(
                f"Por {format_brl(item.subtotal())}".replace(".", ",")
            )
        else:
            self.original_price.hide()
            self.promotion_badge.hide()
            self.price.setText(format_brl(item.subtotal()).replace(".", ","))
        self.quantity.setText(f"Qtd: {item.quantidade}")

    def set_card_width(self, width):
        self.setFixedWidth(width)
        self._update_display_name()

    def _update_display_name(self):
        """Limita visualmente o nome a duas linhas sem reduzir a fonte."""
        self.name.ensurePolished()
        metrics = QFontMetrics(self.name.font())
        available_width = max(1, self.width() - (2 * Spacing.LG))
        words = self.full_name.split()
        if not words:
            self.name.setText("Produto")
            return

        first_line = words.pop(0)
        while words:
            candidate = f"{first_line} {words[0]}"
            if metrics.horizontalAdvance(candidate) > available_width:
                break
            first_line = candidate
            words.pop(0)

        display_first_line = metrics.elidedText(
            first_line, Qt.ElideRight, available_width
        )
        if not words:
            self.name.setText(
                display_first_line
            )
            return

        second_line = metrics.elidedText(
            " ".join(words), Qt.ElideRight, available_width
        )
        self.name.setText(f"{display_first_line}\n{second_line}")


class TerminalScreen(QWidget):
    """Carrinho visual; o objeto ``carrinho`` é a fonte única da compra atual."""

    GRID_MIN_CARD_WIDTH = 250
    GRID_MAX_CARD_WIDTH = 292
    GRID_MAX_COLUMNS = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self.parent = parent
        self.db = DatabaseProdutos()
        self.carrinho = Carrinho()
        self.linhas = {}
        self.total = Decimal("0")
        self.id_contador = 1
        self.peso_total_venda = 0.0
        self._grid_columns = 3
        self._grid_card_width = self.GRID_MAX_CARD_WIDTH
        self._checkout_interactions_enabled = True

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
        self.setAttribute(Qt.WA_StyledBackground, True)
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
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
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
        footer = QHBoxLayout(self.footer_card)
        footer.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.MD)
        footer.setSpacing(Spacing.MD)

        total_label = QLabel("TOTAL")
        total_label.setObjectName("cartTotalLabel")
        self.totalBox = QLabel("R$ 0,00")
        self.totalBox.setObjectName("cartTotal")
        self.totalBox.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

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
        footer.addWidget(total_label)
        footer.addWidget(self.totalBox)
        footer.addStretch(1)
        footer.addLayout(actions, 2)

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
        self.productsContainer.setMinimumHeight(0)
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
            card.set_card_width(self._grid_card_width)
            self.productsLayout.addWidget(card, row, column)
        row_count = (len(cards) + self._grid_columns - 1) // self._grid_columns
        content_height = (
            row_count * ProductCard.HEIGHT
            + max(0, row_count - 1) * self.productsLayout.verticalSpacing()
        )
        self.productsContainer.setMinimumHeight(content_height)

    def _update_grid_geometry(self):
        """Dimensiona o catálogo pelo viewport, já descontada a barra vertical."""
        available_width = self.scroll.viewport().width()
        if available_width <= 0:
            available_width = max(0, self.width() - (2 * Spacing.LG) - 14)

        spacing = self.productsLayout.horizontalSpacing()
        possible_columns = max(
            1,
            (available_width + spacing) // (self.GRID_MIN_CARD_WIDTH + spacing),
        )
        columns = min(self.GRID_MAX_COLUMNS, possible_columns)
        card_width = min(
            self.GRID_MAX_CARD_WIDTH,
            max(
                1,
                (available_width - (spacing * (columns - 1))) // columns,
            ),
        )

        geometry_changed = (
            columns != self._grid_columns or card_width != self._grid_card_width
        )
        self._grid_columns = columns
        self._grid_card_width = card_width

        if self.empty_label is not None:
            self.productsLayout.removeWidget(self.empty_label)
            self.productsLayout.addWidget(
                self.empty_label, 0, 0, 1, self._grid_columns
            )
        elif geometry_changed:
            self._relayout_product_cards()

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
        self.total = Decimal("0")
        self.id_contador = 1
        self.peso_total_venda = 0.0
        self.atualizar_interface()

    def set_checkout_interactions_enabled(self, enabled):
        self._checkout_interactions_enabled = bool(enabled)
        self.codigo_barras.setEnabled(enabled)
        self.btn_finalizar.setEnabled(enabled)
        self.btn_cancelar.setEnabled(enabled)
        for card, _, _ in self.linhas.values():
            card.setEnabled(enabled)

    def _can_accept_checkout_action(self):
        if not self._checkout_interactions_enabled:
            return False
        if self.parent_app.stacked_widget.currentWidget() is not self:
            return False
        return self.parent_app.compra_session.can_accept_checkout_actions()

    def garantir_foco(self):
        if self.parent and self.parent.stacked_widget.currentWidget() == self:
            if not self.codigo_barras.hasFocus():
                self.codigo_barras.setFocus()

    def ir_para_pagamento(self):
        """Abre o resumo; nenhuma chamada remota é iniciada neste toque."""
        if not self._can_accept_checkout_action():
            return
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
        if self.parent_app is None:
            logger.error("[PAYMENT-UI] início recusado: parent ausente")
            return False
        if not self._checkout_interactions_enabled:
            logger.warning("[PAYMENT-UI] início recusado: interações bloqueadas")
            return False
        if self.parent_app.stacked_widget.currentWidget() is not self.parent_app.confirmacao_compra:
            logger.warning("[PAYMENT-UI] início recusado: tela atual não é confirmação")
            return False
        if not self.parent_app.compra_session.can_accept_checkout_actions():
            logger.warning("[PAYMENT-UI] início recusado: sessão indisponível")
            return False
        if self.parent_app.compra_session.payment_in_flight or self.carrinho.vazio():
            logger.warning("[PAYMENT-UI] início recusado: pagamento ativo ou carrinho vazio")
            return False

        logger.info("[PAYMENT-UI] navegando para preparação do pagamento")
        return self.parent_app.pagamento.iniciar_pagamento(
            self.carrinho.to_dict(), self.totalBox.text()
        )

    def cancelar_venda(self):
        if self.parent_app and self._can_accept_checkout_action():
            self.parent_app.reset_compra()
            self.parent_app.setCurrentWidget(self.parent_app.welcome)

    def remover_produto(self, codigo_produto, widget_linha):
        if not self._can_accept_checkout_action():
            return
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
        if not self._can_accept_checkout_action():
            self.codigo_barras.clear()
            return
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
            if not self.parent_app.compra_session.start_if_needed():
                self.codigo_barras.clear()
                return

            item_existente = self.carrinho.buscar_item(produto.id)
            if item_existente is not None:
                codigo_existente = item_existente.produto.codigo
                item = item_existente
                item.quantidade += 1
                _, label, _ = self.linhas[codigo_existente]
                self.atualizar_interface()
                self.atualizar_linha(codigo_existente, label)
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

    def aplicar_precos_atualizados(self, payload):
        for change in (payload or {}).get("items", []):
            product_id = str(change.get("produtoId") or "")
            for item in self.carrinho.listar_itens():
                if str(item.produto.id) != product_id:
                    continue
                item.produto.preco_original = persisted(change.get("precoOriginal"))
                item.produto.preco = persisted(change.get("precoAtual"))
                item.produto.em_promocao = bool(change.get("emPromocao"))
                item.produto.promocao_id = change.get("promocaoId")
                item.produto.promocao_nome = change.get("promocaoNome")
                self.atualizar_linha(item.produto.codigo, None)
        self.atualizar_interface()

    def mostrar_aviso(self, titulo, mensagem):
        QMessageBox.warning(self, titulo, mensagem, QMessageBox.Ok)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_grid_geometry()
        # O viewport recebe sua largura final depois que o layout raiz conclui o
        # resize; recalcular no próximo ciclo evita usar a largura provisória.
        QTimer.singleShot(0, self._update_grid_geometry)
