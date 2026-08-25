from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame,
    QLineEdit, QScrollArea, QMessageBox
)
from database.DatabaseProdutos import DatabaseProdutos
from database.PaymentListener import PaymentListener
from model.Carrinho import Carrinho
from model.Item import Item
from model.Produtos import Produtos


STYLE_BTN_MAIS = """
    QPushButton {
        background-color: #238636;
        color: #ffffff;
        font-size: 18px;
        font-weight: bold;
        border: none;
        border-radius: 8px;
        min-width: 40px;
        max-width: 40px;
        min-height: 36px;
        max-height: 36px;
    }
    QPushButton:hover  { background-color: #2ea043; }
    QPushButton:pressed { background-color: #196127; }
"""

STYLE_BTN_MENOS = """
    QPushButton {
        background-color: #1f3a5f;
        color: #58a6ff;
        font-size: 20px;
        font-weight: bold;
        border: 1px solid #58a6ff;
        border-radius: 8px;
        min-width: 40px;
        max-width: 40px;
        min-height: 36px;
        max-height: 36px;
    }
    QPushButton:hover  { background-color: #264a75; }
    QPushButton:pressed { background-color: #163050; }
"""

STYLE_BTN_REMOVER = """
    QPushButton {
        background-color: #3d1a1a;
        color: #f85149;
        font-size: 16px;
        font-weight: bold;
        border: 1px solid #f85149;
        border-radius: 8px;
        min-width: 40px;
        max-width: 40px;
        min-height: 36px;
        max-height: 36px;
    }
    QPushButton:hover  { background-color: #5a2020; }
    QPushButton:pressed { background-color: #2a0f0f; }
"""

STYLE_BTN_CANCELAR = """
    QPushButton {
        background-color: transparent;
        color: #f85149;
        font-size: 15px;
        font-weight: bold;
        border: 1px solid #f85149;
        border-radius: 10px;
        padding: 14px;
        letter-spacing: 1px;
    }
    QPushButton:hover  { background-color: #3d1a1a; }
    QPushButton:pressed { background-color: #2a0f0f; }
"""


class TerminalScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self.db = DatabaseProdutos()
        self.carrinho = Carrinho()
        self.linhas: dict = {}

        self.listener = PaymentListener(self)
        self.listener.pagamento_aprovado_signal.connect(self.pagamento_aprovado, Qt.QueuedConnection)
        self.listener.start()

        try:
            with open("css/terminal_screen.css", "r", encoding="utf-8") as file:
                self.setStyleSheet(file.read())
        except FileNotFoundError:
            print("Erro: Arquivo css/terminal_screen.css não encontrado!")

        self.parent = parent
        self.total = 0.0
        self.id_contador = 1
        self.peso_total_venda = 0.0

        # -----------------------------
        # LAYOUT PRINCIPAL (VERTICAL - RETRATO)
        # -----------------------------
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # -----------------------------
        # SIDEBAR (TOPO, HORIZONTAL)
        # -----------------------------
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedHeight(220)

        layout_lateral = QHBoxLayout(self.sidebar)
        layout_lateral.setContentsMargins(20, 10, 20, 10)
        layout_lateral.setSpacing(20)

        self.logo = QLabel()
        pixmap = QPixmap("css/ima.png")
        if not pixmap.isNull():
            self.logo.setPixmap(
                pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        self.logo.setAlignment(Qt.AlignCenter)

        self.totalBox = QLabel("R$ 0,00")
        self.totalBox.setObjectName("totalBox")
        self.totalBox.setAlignment(Qt.AlignCenter)

        valor_box = QVBoxLayout()
        valor_box.setSpacing(5)
        valor_box.setAlignment(Qt.AlignVCenter)

        label_valor_total = QLabel("VALOR TOTAL")
        label_valor_total.setObjectName("labelValorTotal")
        label_valor_total.setAlignment(Qt.AlignCenter)
        label_valor_total.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: #8b949e;
            letter-spacing: 3px;
            background-color: transparent;
        """)
        valor_box.addWidget(label_valor_total)
        valor_box.addWidget(self.totalBox)

        layout_lateral.addWidget(self.logo)
        layout_lateral.addLayout(valor_box, 1)

        # -----------------------------
        # CONTENT (RESTANTE DA TELA)
        # -----------------------------
        self.content = QFrame()
        self.content.setObjectName("content")
        layout_conteudo = QVBoxLayout(self.content)

        self.cabecalho = QLabel(
            "ID        CÓDIGO        PRODUTO        QTD        VALOR"
        )
        self.cabecalho.setObjectName("header")

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border:none; background:transparent;")

        self.productsContainer = QWidget()
        self.productsLayout = QVBoxLayout(self.productsContainer)
        self.productsLayout.setAlignment(Qt.AlignTop)
        self.productsLayout.setSpacing(5)
        self.scroll.setWidget(self.productsContainer)

        # INPUTS
        layout_inputs = QHBoxLayout()
        self.codigo_barras = QLineEdit()
        self.codigo_barras.setPlaceholderText("Aguardando leitura do produto...")
        self.codigo_barras.returnPressed.connect(self.readProduct)

        self.peso_display = QLineEdit("0.000 KG")
        self.peso_display.setFixedWidth(180)
        self.peso_display.setReadOnly(True)

        layout_inputs.addWidget(self.codigo_barras)
        layout_inputs.addWidget(self.peso_display)

        # BOTÕES
        layout_botoes = QHBoxLayout()
        layout_botoes.setSpacing(12)

        self.btn_pagar = QPushButton("PAGAR AGORA")
        self.btn_pagar.setObjectName("pay")
        self.btn_pagar.clicked.connect(self.ir_para_pagamento)

        self.btn_app = QPushButton("PAGAR NO APP")
        self.btn_app.setObjectName("app")
        self.btn_app.clicked.connect(self.ir_para_app)

        self.btn_cancelar = QPushButton("CANCELAR VENDA")
        self.btn_cancelar.setStyleSheet(STYLE_BTN_CANCELAR)
        self.btn_cancelar.setMinimumHeight(52)
        self.btn_cancelar.clicked.connect(self.cancelar_venda)

        layout_botoes.addWidget(self.btn_cancelar, 1)
        layout_botoes.addWidget(self.btn_app, 2)
        layout_botoes.addWidget(self.btn_pagar, 2)

        layout_conteudo.addWidget(self.cabecalho)
        layout_conteudo.addWidget(self.scroll, 1)
        layout_conteudo.addLayout(layout_inputs)
        layout_conteudo.addSpacing(10)
        layout_conteudo.addLayout(layout_botoes)

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.content, 1)

        # FOCO
        self.timer_foco = QTimer()
        self.timer_foco.timeout.connect(self.garantir_foco)
        self.timer_foco.start(1000)

    # ================= UI =================
    def _texto_linha(self, id_linha, codigo, item):
        return (
            f"{id_linha:<8} "
            f"{codigo:<18} "
            f"{item.produto.nome:<25} "
            f"{item.quantidade:>3}x   "
            f"R$ {item.subtotal():>7.2f}"
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

    def aumentar_quantidade(self, codigo, label):
        item = self.carrinho.buscar_item(codigo)
        if not item:
            return
        item.quantidade += 1
        self.peso_total_venda += 1.0
        self.atualizar_interface()
        self.atualizar_linha(codigo, label)

    def diminuir_quantidade(self, codigo, widget, label):
        item = self.carrinho.buscar_item(codigo)
        if not item:
            return
        item.quantidade -= 1
        self.peso_total_venda -= 1.0
        if item.quantidade <= 0:
            self.remover_produto(codigo, widget)
        else:
            self.atualizar_interface()
            self.atualizar_linha(codigo, label)

    def pagamento_aprovado(self, data):
        print("Pagamento confirmado via Redis!")
        if self.parent_app:
            self.parent_app.setCurrentWidget(self.parent_app.confirmacao)
            self.parent_app.confirmacao.mostrar_tela()

    def liberar_tela(self):
        print("Limpando a tela...")
        self.carrinho = Carrinho()
        self.linhas.clear()
        while self.productsLayout.count():
            item = self.productsLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.total = 0.0
        self.id_contador = 1
        self.peso_total_venda = 0.0
        self.totalBox.setText("R$ 0,00")
        self.peso_display.setText("0.000 KG")
        print("Terminal resetado!")

    def garantir_foco(self):
        if self.parent and self.parent.stacked_widget.currentWidget() == self:
            if not self.codigo_barras.hasFocus():
                self.codigo_barras.setFocus()

    def ir_para_pagamento(self):
        if not self.linhas:
            self.mostrar_aviso(
                "Carrinho vazio",
                "Adicione pelo menos um produto antes de continuar."
            )
            return
        if self.parent_app:
            self.parent_app.pagamento.total_final.setText(self.totalBox.text())
            self.parent_app.setCurrentWidget(self.parent_app.pagamento)

    def ir_para_app(self):
        if not self.linhas:
            self.mostrar_aviso(
                "Carrinho vazio",
                "Adicione pelo menos um produto antes de continuar."
            )

            return
        if self.parent_app:
            self.parent_app.app_payment.iniciar_pagamento(self.totalBox.text())
            self.parent_app.setCurrentWidget(self.parent_app.app_payment)

    def cancelar_venda(self):
        self.liberar_tela()
        if self.parent_app:
            self.parent_app.setCurrentWidget(self.parent_app.welcome)

    def remover_produto(self, codigo_produto, widget_linha):
        item = self.carrinho.buscar_item(codigo_produto)
        if not item:
            return
        self.peso_total_venda -= item.quantidade * 1.0
        self.carrinho.remover_item(codigo_produto)
        self.linhas.pop(codigo_produto, None)
        self.totalBox.setText(self.carrinho.total_formatado())
        self.peso_display.setText(f"{self.peso_total_venda:.3f} KG")
        widget_linha.deleteLater()

    # ================= LEITURA =================
    def readProduct(self):
        barcode = self.codigo_barras.text().strip()
        if not barcode:
            return
        try:
            tupla = self.db.buscar_por_codigo(barcode)
            if not tupla:
                self.mostrar_aviso(
                    "Produto não encontrado",
                    "O produto informado não está cadastrado."
                )
                self.codigo_barras.clear()
                return

            produto = Produtos.from_tuple(tupla)
            codigo = produto.codigo

            if codigo in self.linhas:
                item = self.carrinho.buscar_item(codigo)
                item.quantidade += 1
                self.peso_total_venda += 1.0
                _, lbl_texto, _ = self.linhas[codigo]
                self.atualizar_interface()
                self.atualizar_linha(codigo, lbl_texto)
                self.codigo_barras.clear()
                self.codigo_barras.setFocus()
                return

            # Produto novo: cria linha no layout
            novo_item = Item(produto=produto, quantidade=1, received_weight=1.0)
            self.carrinho.adicionar_item(novo_item)
            self.peso_total_venda += 1.0

            item = self.carrinho.buscar_item(codigo)
            id_linha = self.id_contador

            linha_widget = QFrame()
            layout_linha = QHBoxLayout(linha_widget)
            layout_linha.setContentsMargins(10, 5, 10, 5)

            lbl_texto = QLabel(self._texto_linha(id_linha, codigo, item))

            btn_menos = QPushButton("-")
            btn_mais = QPushButton("+")
            btn_remover = QPushButton("x")

            btn_menos.setStyleSheet(STYLE_BTN_MENOS)
            btn_mais.setStyleSheet(STYLE_BTN_MAIS)
            btn_remover.setStyleSheet(STYLE_BTN_REMOVER)

            btn_menos.clicked.connect(
                lambda _, c=codigo, w=linha_widget, l=lbl_texto:
                self.diminuir_quantidade(c, w, l)
            )
            btn_mais.clicked.connect(
                lambda _, c=codigo, l=lbl_texto:
                self.aumentar_quantidade(c, l)
            )
            btn_remover.clicked.connect(
                lambda _, c=codigo, w=linha_widget:
                self.remover_produto(c, w)
            )

            layout_linha.addWidget(lbl_texto, 1)
            layout_linha.addWidget(btn_menos)
            layout_linha.addWidget(btn_mais)
            layout_linha.addWidget(btn_remover)

            self.productsLayout.addWidget(linha_widget)

            # Registra no dicionário: codigo -> (widget, label, id_linha)
            self.linhas[codigo] = (linha_widget, lbl_texto, id_linha)

            self.totalBox.setText(self.carrinho.total_formatado())
            self.id_contador += 1

            self.codigo_barras.clear()
            self.codigo_barras.setFocus()

        except Exception as e:
            print("Erro:", e)

    def mostrar_aviso(self, titulo, mensagem):
        QMessageBox.warning(
            self,
            titulo,
            mensagem,
            QMessageBox.Ok
        )