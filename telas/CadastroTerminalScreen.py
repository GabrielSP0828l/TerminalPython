import json

import qrcode
import requests
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QFrame,
    QMessageBox
)

from config import API_URL
from model.Terminal import Terminal
from service.TerminalInfo import TerminalInfo


class CadastroTerminalScreen(QWidget):

    def __init__(self, parent):
        if not Terminal.is_activated():
            self.timer = QTimer()

            self.timer.timeout.connect(
                self.verificar_ativacao
            )

            self.timer.start(5000)

        super().__init__()

        self.parent = parent

        try:

            with open(
                    "css/cadastro_terminal.css",
                    "r",
                    encoding="utf-8"
            ) as file:

                self.setStyleSheet(
                    file.read()
                )

        except:
            pass

        root = QVBoxLayout(self)

        root.setAlignment(
            Qt.AlignCenter
        )

        card = QFrame()

        card.setObjectName(
            "card"
        )

        layout = QVBoxLayout(card)

        self.title = QLabel(
            "ATIVAÇÃO DO TERMINAL"
        )

        self.title.setObjectName(
            "title"
        )

        self.title.setAlignment(
            Qt.AlignCenter
        )

        self.subtitle = QLabel(
            "Escaneie o QR Code para cadastrar este terminal."
        )

        self.subtitle.setAlignment(
            Qt.AlignCenter
        )

        self.qrLabel = QLabel()

        self.qrLabel.setAlignment(
            Qt.AlignCenter
        )

        self.infoLabel = QLabel()

        self.infoLabel.setAlignment(
            Qt.AlignCenter
        )

        self.infoLabel.setWordWrap(
            True
        )

        layout.addWidget(
            self.title
        )

        layout.addSpacing(
            20
        )

        layout.addWidget(
            self.subtitle
        )

        layout.addSpacing(
            20
        )

        layout.addWidget(
            self.qrLabel
        )

        layout.addSpacing(
            20
        )

        layout.addWidget(
            self.infoLabel
        )

        root.addWidget(
            card
        )

        self.gerar_qrcode()

        self.timer = QTimer()

        self.timer.timeout.connect(
            self.verificar_ativacao
        )

        self.timer.start(
            5000
        )

    def gerar_qrcode(self):

        dados = TerminalInfo.to_dict()

        qr = qrcode.QRCode(
            version=1,
            box_size=10,
            border=2
        )

        qr.add_data(
            json.dumps(dados)
        )

        qr.make(
            fit=True
        )

        img = qr.make_image(
            fill_color="black",
            back_color="white"
        )

        qr_file = "/tmp/terminal_qr.png"

        img.save(
            qr_file
        )

        pixmap = QPixmap(
            qr_file
        )

        self.qrLabel.setPixmap(
            pixmap.scaled(
                320,
                320,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )

        self.infoLabel.setText(
            f"Serial: {dados['serialNumber']}\n"
            f"MAC: {dados['macAddress']}\n"
            f"IP: {dados['ipAddress']}"
        )

    def verificar_ativacao(self):

        try:

            if Terminal.is_activated():
                self.timer.stop()
                return

            serial = TerminalInfo.get_serial_number()

            response = requests.get(
                f"{API_URL}/terminal/serial/{serial}",
                timeout=5
            )

            if response.status_code != 200:
                return

            dados = response.json()

            if dados["activated"]:
                self.timer.stop()  # IMPORTANTE

                terminal = Terminal.from_dict(dados)
                terminal.save()

                self.parent.inicializar_terminal()

                QMessageBox.information(
                    self,
                    "Terminal Ativado",
                    "Terminal liberado com sucesso."
                )

                self.parent.setCurrentWidget(
                    self.parent.welcome
                )

        except Exception as e:

            print(
                f"Erro ao verificar ativação: {e}"
            )
