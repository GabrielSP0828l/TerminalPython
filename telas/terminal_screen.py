import logging

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QFrame,
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


logger = logging.getLogger(__name__)


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
        root.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        root.setSpacing(Spacing.LG)

        self.header_card = QFrame(self)
        self.header_card.setObjectName("cartHeader")
        header = QVBoxLayout(self.header_card)
        header.setContentsMargins(Spacing.XL, Spacing.LG, Spacing.XL, Spacing.LG)
        header.setSpacing(Spacing.XS)

        title = QLabel("SUA COMPRA")
        title.setProperty("role", "pageTitle")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("Escaneie os produtos e confira a lista abaixo")
        subtitle.setProperty("role", "pageSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        header.addWidget(title)
        header.addWidget(subtitle)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.productsContainer = QWidget()
        self.productsLayout = QVBoxLayout(self.productsContainer)
        self.productsLayout.setContentsMargins(0, 0, 0, 0)
        self.productsLayout.setSpacing(Spacing.MD)
        self.productsLayout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.productsContainer)

        self.empty_label = QLabel("Nenhum produto escaneado")
        self.empty_label.setProperty("role", "pageSubtitle")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setMinimumHeight(120)
        self.productsLayout.addWidget(self.empty_label)

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
        footer.setContentsMargins(Spacing.XL, Spacing.LG, Spacing.XL, Spacing.XL)
        footer.setSpacing(Spacing.MD)

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

    def _texto_linha(self, id_linha, codigo, item):
        return (
            f"{item.produto.nome}\n"
            f"{item.quantidade} × R$ {item.produto.preco:.2f}  •  "
            f"Código {codigo}\nSubtotal: R$ {item.subtotal():.2f}"
        )

    def atualizar_interface(self):
        self.totalBox.setText(self.carrinho.total_formatado())
        self.peso_display.setText(f"{self.peso_total_venda:.3f} KG")

    def atualizar_linha(self, codigo, label):
        item = self.carrinho.buscar_item(codigo)
        if not item or codigo not in self.linhas:
            return
        _, _, id_linha = self.linhas[codigo]
        label.setText(self._texto_linha(id_linha, codigo, item))

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
        self.empty_label = QLabel("Nenhum produto escaneado")
        self.empty_label.setProperty("role", "pageSubtitle")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setMinimumHeight(120)
        self.productsLayout.addWidget(self.empty_label)
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
        self.atualizar_interface()
        if self.carrinho.vazio():
            self.parent_app.compra_session.reset()
            self.empty_label = QLabel("Nenhum produto escaneado")
            self.empty_label.setProperty("role", "pageSubtitle")
            self.empty_label.setAlignment(Qt.AlignCenter)
            self.empty_label.setMinimumHeight(120)
            self.productsLayout.addWidget(self.empty_label)

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

            linha_widget = QFrame()
            linha_widget.setObjectName("productRow")
            layout_linha = QHBoxLayout(linha_widget)
            layout_linha.setContentsMargins(
                Spacing.LG, Spacing.MD, Spacing.MD, Spacing.MD
            )
            layout_linha.setSpacing(Spacing.MD)

            lbl_texto = QLabel(self._texto_linha(id_linha, codigo, item))
            lbl_texto.setProperty("role", "productName")
            lbl_texto.setWordWrap(True)
            lbl_texto.setMinimumHeight(82)

            btn_remover = QPushButton("×")
            btn_remover.setProperty("variant", "remove")
            btn_remover.setFixedSize(TouchSize.MINIMUM, TouchSize.MINIMUM)
            btn_remover.setAccessibleName(f"Remover {produto.nome}")
            btn_remover.clicked.connect(
                lambda _, c=codigo, w=linha_widget: self.remover_produto(c, w)
            )

            layout_linha.addWidget(lbl_texto, 1)
            layout_linha.addWidget(btn_remover)
            self.productsLayout.addWidget(linha_widget)
            self.linhas[codigo] = (linha_widget, lbl_texto, id_linha)

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
