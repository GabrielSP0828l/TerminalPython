from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy
from PyQt5.QtCore import Qt
import requests

from config import API_URL
from styles.theme import Theme
from styles.tokens import Spacing


class LoginScreen(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.setProperty("role", "page")
        self.setStyleSheet(Theme.page_stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        card = QFrame()
        card.setProperty("role", "card")
        card.setMaximumWidth(680)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(Spacing.XXL, Spacing.XXL, Spacing.XXL, Spacing.XXL)
        layout.setSpacing(Spacing.LG)

        title = QLabel("Como deseja continuar?")
        title.setProperty("role", "pageTitle")
        title.setAlignment(Qt.AlignCenter)

        btn_identificar = QPushButton("IDENTIFICAR-SE (CPF)")
        btn_identificar.setProperty("variant", "primary")
        btn_identificar.setProperty("primaryAction", True)
        btn_identificar.clicked.connect(lambda: self.parent.setCurrentWidget(self.parent.teclado))

        btn_anonimo = QPushButton("CONTINUAR ANÔNIMO")
        btn_anonimo.setProperty("variant", "secondary")
        btn_anonimo.clicked.connect(self.continuar_anonimo)

        layout.addWidget(title)
        layout.addSpacing(30)
        layout.addWidget(btn_identificar)
        layout.addSpacing(15)
        layout.addWidget(btn_anonimo)

        root.addStretch()
        root.addWidget(card, alignment=Qt.AlignCenter)
        root.addStretch()

    def continuar_anonimo(self):
        url = f"{API_URL}/usuarios/anonimo"
        try:
            requests.post(url, json={"nome": "Visitante"}, timeout=2)
        except:
            print("Aviso: Back-end offline, continuando local...")

        self.ir_terminal()

    def ir_terminal(self):
        self.parent.setCurrentWidget(self.parent.terminal)
