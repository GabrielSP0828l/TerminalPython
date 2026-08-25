from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QPushButton
)

from service.PurchaseApi import AppCheckoutWorker


class AppPaymentScreen(QWidget):

    def __init__(self, parent):
        super().__init__()

        self.parent = parent
        try:
            with open("css/terminal_screen.css", "r", encoding="utf-8") as file:
                self.setStyleSheet(file.read())
        except:
            pass

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # SIDEBAR
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(400)

        layout_lateral = QVBoxLayout(self.sidebar)

        self.logo = QLabel()
        pixmap = QPixmap("css/ima.png")
        if not pixmap.isNull():
            self.logo.setPixmap(
                pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

        layout_lateral.addWidget(self.logo, alignment=Qt.AlignCenter)
        layout_lateral.addSpacing(30)

        titulo_total = QLabel("TOTAL")
        titulo_total.setStyleSheet("color:#8dd4ff;font-size:18px;")

        self.total_label = QLabel("R$ 0,00")
        self.total_label.setObjectName("totalBox")

        layout_lateral.addWidget(titulo_total, alignment=Qt.AlignCenter)
        layout_lateral.addWidget(self.total_label)
        layout_lateral.addStretch()

        self.status = QLabel("Aguardando...")
        self.status.setObjectName("api")
        layout_lateral.addWidget(self.status)

        # CONTENT
        self.content = QFrame()
        self.content.setObjectName("content")

        layout_content = QVBoxLayout(self.content)
        layout_content.setContentsMargins(40, 40, 40, 40)

        self.titulo = QLabel("CONTINUE O PAGAMENTO NO APP")
        self.titulo.setObjectName("header")
        self.titulo.setAlignment(Qt.AlignCenter)

        self.timer_label = QLabel("05:00")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setStyleSheet(
            "font-size:28px;color:#8dd4ff;font-weight:bold;"
        )

        self.checkout_worker = None
        self.parent.compra_session.remaining_changed.connect(self.atualizar_contador)

        self.loading = QLabel("Gerando QR Code...")
        self.loading.setAlignment(Qt.AlignCenter)
        self.loading.setStyleSheet("font-size:20px;color:white;")

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)

        # ✅ Botão conectado uma única vez
        self.btn_cancelar = QPushButton("CANCELAR")
        self.btn_cancelar.setStyleSheet(
            """
            background:#e74c3c;
            color:white;
            border-radius:12px;
            padding:15px;
            font-size:18px;
            """
        )
        self.btn_cancelar.clicked.connect(self.cancelar_pagamento)

        layout_content.addWidget(self.titulo)
        layout_content.addSpacing(10)
        layout_content.addWidget(self.timer_label)
        layout_content.addSpacing(20)
        layout_content.addWidget(self.loading)
        layout_content.addWidget(self.qr_label, 1)
        layout_content.addStretch()
        layout_content.addWidget(self.btn_cancelar)

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.content)

    def iniciar_pagamento(self, valor):
        self.total_label.setText(valor)
        self.loading.show()
        self.loading.setText("Gerando pagamento no aplicativo...")
        self.qr_label.clear()
        self.status.setText("Gerando checkout...")
        self.status.setStyleSheet("color:#62c8ff;")

        self.atualizar_contador(self.parent.compra_session.remaining_seconds())
        if self.checkout_worker and self.checkout_worker.isRunning():
            return
        self.checkout_worker = AppCheckoutWorker(
            self.parent.terminal.carrinho.to_dict(), parent=self
        )
        self.checkout_worker.succeeded.connect(self._checkout_ready)
        self.checkout_worker.failed.connect(self._checkout_failed)
        self.checkout_worker.start()

    def _checkout_ready(self, data):
        pixmap = QPixmap()
        pixmap.loadFromData(data["image"])
        self.loading.hide()
        self.qr_label.setPixmap(
            pixmap.scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        self.status.setText("Escaneie o QR Code com o aplicativo")
        self.status.setProperty("state", "info")

    def _checkout_failed(self, message):
        self.loading.show()
        self.loading.setText("Não foi possível gerar o pagamento no aplicativo.")
        self.status.setText("O carrinho foi preservado. Tente novamente.")

    def atualizar_contador(self, remaining_seconds):
        minutos = remaining_seconds // 60
        segundos = remaining_seconds % 60
        self.timer_label.setText(f"{minutos:02}:{segundos:02}")

    def cancelar_pagamento(self):
        self.parent.setCurrentWidget(self.parent.terminal)

    def parar_espera(self):
        self.qr_label.clear()
