from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
from datetime import datetime

from service.HoldToExitLabel import HoldToExitLabel


class TelaBemVindos(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        try:
            with open("css/bemvindo.css", "r", encoding="utf-8") as arquivo_css:
                self.setStyleSheet(arquivo_css.read())
        except:
            self.setStyleSheet("background-color: black;")

        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(20, 20, 20, 20)
        layout_principal.setAlignment(Qt.AlignCenter)
        layout_principal.setSizeConstraint(QVBoxLayout.SetNoConstraint)

        self.card = QFrame()
        self.card.setObjectName("centralCard")
        self.card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout_cartao = QVBoxLayout(self.card)
        layout_cartao.setAlignment(Qt.AlignCenter)
        layout_cartao.setContentsMargins(30, 30, 30, 30)
        layout_cartao.setSpacing(15)

        self.logo = HoldToExitLabel(hold_time=2000)
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        logo_pixmap = QPixmap("css/ima.png")
        self.logo_pixmap_original = logo_pixmap
        self.atualizar_logo(logo_pixmap)

        titulo = QLabel("BEM VINDO")
        titulo.setObjectName("title")
        titulo.setAlignment(Qt.AlignCenter)

        subtitulo = QLabel("SEMPRE AQUI")
        subtitulo.setObjectName("subtitle")
        subtitulo.setAlignment(Qt.AlignCenter)

        self.relogio = QLabel()
        self.relogio.setObjectName("relogio")
        self.relogio.setAlignment(Qt.AlignCenter)

        self.botao_entrar = QPushButton("TOQUE PARA CONTINUAR")
        self.botao_entrar.setCursor(Qt.PointingHandCursor)
        self.botao_entrar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.botao_entrar.clicked.connect(
            lambda: self.parent.setCurrentWidget(self.parent.terminal)
        )

        layout_cartao.addStretch(1)
        layout_cartao.addWidget(self.logo, stretch=3)
        layout_cartao.addWidget(subtitulo)
        layout_cartao.addWidget(titulo)
        layout_cartao.addWidget(self.relogio)
        layout_cartao.addWidget(self.botao_entrar)
        layout_cartao.addStretch(1)

        layout_principal.addWidget(self.card)

        timer = QTimer(self)
        timer.timeout.connect(self.atualizarRelogio)
        timer.start(1000)
        self.atualizarRelogio()

    def atualizarRelogio(self):
        self.relogio.setText(datetime.now().strftime("%H:%M:%S"))

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if self.logo_pixmap_original and not self.logo_pixmap_original.isNull():
            w = self.width()
            size = max(120, min(300, w // 4))

            self.atualizar_logo(
                self.logo_pixmap_original.scaled(
                    size, size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
            )

    def atualizar_logo(self, pixmap):
        self.logo.setPixmap(pixmap)