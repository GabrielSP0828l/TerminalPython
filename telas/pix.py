from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QHBoxLayout
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
import base64


class PixScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__()

        self.parent = parent

        self.setStyleSheet("""
        QWidget {
            background: #0f1117;
            color: white;
            font-family: Consolas;
        }
        #container {
            background: #161a23;
            border-radius: 20px;
            padding: 30px;
        }
        #title {
            font-size: 34px;
            font-weight: bold;
            color: #62c8ff;
        }
        #total {
            font-size: 42px;
            font-weight: bold;
            color: #00ff88;
        }
        #timer {
            font-size: 28px;
            font-weight: bold;
            color: #8dd4ff;
        }
        #status {
            font-size: 22px;
            font-weight: bold;
            color: #ffcc00;
        }
        QPushButton {
            background: #62c8ff;
            border: none;
            border-radius: 12px;
            padding: 15px;
            font-size: 18px;
            font-weight: bold;
            color: black;
        }
        QPushButton:hover {
            background: #7fd6ff;
        }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        container = QFrame()
        container.setObjectName("container")
        container.setFixedWidth(700)

        layout = QVBoxLayout(container)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignCenter)

        titulo = QLabel("PAGAMENTO PIX")
        titulo.setObjectName("title")
        titulo.setAlignment(Qt.AlignCenter)

        self.total_label = QLabel("R$ 0,00")
        self.total_label.setObjectName("total")
        self.total_label.setAlignment(Qt.AlignCenter)

        self.qrcode = QLabel()
        self.qrcode.setAlignment(Qt.AlignCenter)

        self.timer_label = QLabel("05:00")
        self.timer_label.setObjectName("timer")
        self.timer_label.setAlignment(Qt.AlignCenter)

        self.remaining_seconds = 300

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.atualizar_contador)

        self.status = QLabel("AGUARDANDO PAGAMENTO...")
        self.status.setObjectName("status")
        self.status.setAlignment(Qt.AlignCenter)

        botoes = QHBoxLayout()

        self.btn_confirmar = QPushButton("CONFIRMAR")
        self.btn_cancelar = QPushButton("CANCELAR")

        self.btn_confirmar.clicked.connect(self.finalizar_pagamento)
        self.btn_cancelar.clicked.connect(self.cancelar)

        botoes.addWidget(self.btn_confirmar)
        botoes.addWidget(self.btn_cancelar)

        layout.addWidget(titulo)
        layout.addWidget(self.total_label)
        layout.addWidget(self.qrcode)
        layout.addWidget(self.timer_label)
        layout.addWidget(self.status)
        layout.addLayout(botoes)

        main_layout.addWidget(container)

    def iniciar_pagamento(self, valor, qr_code, qr_code_base64):
        try:
            self.total_label.setText(f"R$ {valor}")

            imagem_bytes = base64.b64decode(qr_code_base64)
            pixmap = QPixmap()
            pixmap.loadFromData(imagem_bytes)
            self.qrcode.setPixmap(
                pixmap.scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

            self.status.setText("ESCANEIE O QR CODE")
            self.status.setStyleSheet(
                "font-size:22px;font-weight:bold;color:#ffcc00;"
            )

            self.pix_code = qr_code
            print("PIX COPIA E COLA:")
            print(qr_code)

            # Inicia o timer
            self.remaining_seconds = 300
            self.timer_label.setText("05:00")
            self.countdown_timer.start(1000)

        except Exception as e:
            print("ERRO PIX:", e)
            self.status.setText(str(e))

    def atualizar_contador(self):
        minutos = self.remaining_seconds // 60
        segundos = self.remaining_seconds % 60
        self.timer_label.setText(f"{minutos:02}:{segundos:02}")
        self.remaining_seconds -= 1

        if self.remaining_seconds < 0:
            self.countdown_timer.stop()
            self.status.setText("PAGAMENTO EXPIRADO")
            self.status.setStyleSheet(
                "font-size:22px;font-weight:bold;color:#ff4d4d;"
            )
            self.parent.setCurrentWidget(self.parent.pagamento)

    def finalizar_pagamento(self):
        self.countdown_timer.stop()
        self.parent.pagamento.finalizar_venda()

    def cancelar(self):
        self.countdown_timer.stop()
        self.parent.setCurrentWidget(self.parent.pagamento)