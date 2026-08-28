import json
import logging
from io import BytesIO

import qrcode
import requests
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from config import API_URL
from model.Terminal import Terminal
from service.TerminalInfo import TerminalInfo
from styles.theme import Theme
from styles.tokens import Spacing


logger = logging.getLogger(__name__)


class ActivationCheckThread(QThread):
    activation_found = pyqtSignal(dict)
    status_changed = pyqtSignal(str, bool)

    def __init__(self, serial_number, parent=None):
        super().__init__(parent)
        self.serial_number = serial_number

    def run(self):
        if not API_URL:
            if not self.isInterruptionRequested():
                self.status_changed.emit("Servidor não configurado. Verifique a instalação.", True)
            return

        try:
            response = requests.get(
                f"{API_URL}/terminal/serial/{self.serial_number}",
                timeout=5
            )

            if response.status_code == 404:
                if not self.isInterruptionRequested():
                    self.status_changed.emit("Aguardando liberação do terminal...", False)
                return

            if response.status_code != 200:
                if not self.isInterruptionRequested():
                    self.status_changed.emit("Não foi possível consultar a ativação.", True)
                logger.warning(
                    "Consulta de ativação falhou: status=%s",
                    response.status_code
                )
                return

            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Resposta de ativação não é um objeto JSON")

            if data.get("activated") is True:
                if not self.isInterruptionRequested():
                    self.activation_found.emit(data)
            else:
                if not self.isInterruptionRequested():
                    self.status_changed.emit("Aguardando liberação do terminal...", False)

        except (requests.RequestException, ValueError) as error:
            if not self.isInterruptionRequested():
                self.status_changed.emit("Sem conexão com o servidor. Tentando novamente...", True)
            logger.warning("Falha ao consultar ativação: %s", error)


class CadastroTerminalScreen(QWidget):
    POLL_INTERVAL_MS = 5000

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("activationScreen")
        self.parent_app = parent
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.device_info = TerminalInfo.to_dict()
        self._qr_pixmap = QPixmap()
        self._layout_mode = None
        self.activation_worker = ActivationCheckThread(
            self.device_info["serialNumber"],
            self
        )
        self.activation_worker.activation_found.connect(self._concluir_ativacao)
        self.activation_worker.status_changed.connect(self._atualizar_status)

        self._carregar_estilo()
        self._montar_interface()
        self._gerar_qrcode()

        self.activation_timer = QTimer(self)
        self.activation_timer.timeout.connect(self.verificar_ativacao)

        if not Terminal.is_activated():
            self.activation_timer.start(self.POLL_INTERVAL_MS)
            QTimer.singleShot(0, self.verificar_ativacao)

    def _carregar_estilo(self):
        self.setStyleSheet(Theme.activation_stylesheet())

    def _montar_interface(self):
        root = QVBoxLayout(self)
        root.setSizeConstraint(QVBoxLayout.SetNoConstraint)
        root.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        root.setSpacing(0)

        self.card = QFrame(self)
        self.card.setObjectName("activationCard")
        self.card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(Spacing.XXL, Spacing.XL, Spacing.XXL, Spacing.XL)
        layout.setSpacing(Spacing.MD)

        self.title = QLabel("ATIVAÇÃO DO TERMINAL")
        self.title.setObjectName("activationTitle")
        self.title.setAlignment(Qt.AlignCenter)

        self.subtitle = QLabel(
            "Escaneie o QR Code no painel administrativo para vincular este equipamento."
        )
        self.subtitle.setObjectName("activationSubtitle")
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setWordWrap(True)

        self.qr_label = QLabel()
        self.qr_label.setObjectName("activationQrCode")
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.info_label = QLabel()
        self.info_label.setObjectName("activationDeviceInfo")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setWordWrap(True)
        self.info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.status_label = QLabel("Preparando consulta de ativação...")
        self.status_label.setObjectName("activationStatus")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.details_panel = QWidget(self.card)
        self.details_panel.setObjectName("activationDetails")
        details_layout = QVBoxLayout(self.details_panel)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(Spacing.MD)
        details_layout.addStretch(1)
        details_layout.addWidget(self.info_label)
        details_layout.addWidget(self.status_label)
        details_layout.addStretch(1)

        self.body = QWidget(self.card)
        self.body.setObjectName("activationBody")
        self.body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.body_layout = QGridLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setHorizontalSpacing(Spacing.XL)
        self.body_layout.setVerticalSpacing(Spacing.MD)

        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addWidget(self.body, 1)
        root.addWidget(self.card, 1)

        self._aplicar_layout_responsivo(self.width(), self.height())

    def _gerar_qrcode(self):
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(json.dumps(self.device_info))
        qr.make(fit=True)

        buffer = BytesIO()
        qr.make_image(fill_color="black", back_color="white").save(
            buffer,
            format="PNG"
        )

        self._qr_pixmap.loadFromData(buffer.getvalue(), "PNG")
        self._redimensionar_qrcode()

        self.info_label.setText(
            f"Serial: {self.device_info['serialNumber']}\n"
            f"MAC: {self.device_info['macAddress']}  •  "
            f"IP: {self.device_info['ipAddress']}"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._aplicar_layout_responsivo(event.size().width(), event.size().height())
        self._redimensionar_qrcode()

    def _aplicar_layout_responsivo(self, width, height):
        mode = "portrait" if height > width or width < 760 else "landscape"
        if mode == self._layout_mode:
            return

        self._layout_mode = mode
        if mode == "portrait":
            self.body_layout.addWidget(self.qr_label, 0, 0, Qt.AlignCenter)
            self.body_layout.addWidget(self.details_panel, 1, 0)
            self.body_layout.setColumnStretch(0, 1)
            self.body_layout.setColumnStretch(1, 0)
            self.body_layout.setRowStretch(0, 3)
            self.body_layout.setRowStretch(1, 2)
        else:
            self.body_layout.addWidget(self.qr_label, 0, 0, Qt.AlignCenter)
            self.body_layout.addWidget(self.details_panel, 0, 1)
            self.body_layout.setColumnStretch(0, 1)
            self.body_layout.setColumnStretch(1, 1)
            self.body_layout.setRowStretch(0, 1)
            self.body_layout.setRowStretch(1, 0)

    def _redimensionar_qrcode(self):
        if self._qr_pixmap.isNull():
            return

        if self._layout_mode == "portrait":
            target = min(300, max(160, int(min(self.width() * 0.62, self.height() * 0.42))))
        else:
            target = min(280, max(160, int(min(self.width() * 0.32, self.height() * 0.52))))

        self.qr_label.setPixmap(
            self._qr_pixmap.scaled(
                target,
                target,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    def verificar_ativacao(self):
        if Terminal.is_activated():
            self.activation_timer.stop()
            return

        if self.activation_worker.isRunning():
            return

        self._atualizar_status("Consultando ativação...", False, state="loading")
        self.activation_worker.start()

    def _atualizar_status(self, message, is_error, state=None):
        self.status_label.setText(message)
        self.status_label.setProperty(
            "state",
            state or ("error" if is_error else "info")
        )
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _concluir_ativacao(self, data):
        try:
            terminal = Terminal.from_dict(data)
            terminal.save()
        except (OSError, TypeError, ValueError) as error:
            logger.error("Não foi possível persistir a ativação: %s", error)
            self._atualizar_status(
                "A ativação foi recebida, mas não pôde ser salva. Tentando novamente...",
                True
            )
            return

        self.activation_timer.stop()
        self._atualizar_status("Terminal ativado com sucesso.", False, state="success")
        self.parent_app.iniciar_operacao_terminal()
        self.parent_app.setCurrentWidget(self.parent_app.welcome)
