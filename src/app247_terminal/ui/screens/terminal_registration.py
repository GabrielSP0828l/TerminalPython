import logging
import time
from io import BytesIO

import qrcode
import requests
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app247_terminal.config.settings import API_URL
from app247_terminal.models.terminal import Terminal
from app247_terminal.services.terminal_info import TerminalInfo
from app247_terminal.services.terminal_lifecycle import TerminalLifecycleApi
from app247_terminal.services.terminal_auth import (
    TerminalCredentialMissing,
    TerminalCredentialStore,
    TerminalPairingExpired,
    claim_pairing,
    start_pairing,
)
from app247_terminal.services.backend_client import terminal_access_state
from app247_terminal.ui.styles.theme import Theme
from app247_terminal.ui.styles.tokens import Spacing


logger = logging.getLogger(__name__)


# Um pouco antes dos 15 min do backend. Conta pelo relógio monotônico porque o relógio do
# Raspberry pode estar errado; se o código expirar antes, o claim responde 410 e renova.
PAIRING_RENEW_SECONDS = 14 * 60


class ActivationCheckThread(QThread):
    """Ativa o equipamento sem comando local.

    Sem credencial, pede um código de pareamento, mostra-o na tela (texto e QR) e consulta
    o backend até o admin confirmar o código no app; então recebe e instala a credencial.
    Com credencial já instalada, só confirma a ativação pelo serial.
    """

    activation_found = pyqtSignal(dict)
    status_changed = pyqtSignal(str, bool)
    pairing_changed = pyqtSignal(object)

    def __init__(self, device_info, parent=None, lifecycle_api=None, session=requests):
        super().__init__(parent)
        self.device_info = dict(device_info)
        self.serial_number = self.device_info.get("serialNumber")
        self.lifecycle_api = lifecycle_api or TerminalLifecycleApi()
        self.session = session
        self.pairing = None
        self.pairing_deadline = 0.0

    def run(self):
        if not API_URL:
            self._status("Servidor não configurado. Verifique a instalação.", True)
            return

        try:
            # Se o processo anterior concluiu um reset, confirma ao backend antes de
            # procurar uma nova ativação. Falha aqui mantém o recibo para nova tentativa.
            self.lifecycle_api.confirm_pending_reset()
            if TerminalCredentialStore().load():
                self._check_activation_by_serial()
            else:
                self._pair()
        except (requests.RequestException, RuntimeError, ValueError) as error:
            self._status("Sem conexão com o servidor. Tentando novamente...", True)
            logger.warning("Falha ao consultar ativação: %s", error)
        except TerminalCredentialMissing as error:
            # Arquivo de credencial ilegível/inseguro: exige reprovisionamento,
            # mas não pode abortar o processo a partir da thread.
            self._status(
                "Credencial do equipamento inválida. Solicite reprovisionamento.",
                True,
            )
            logger.error("Credencial do dispositivo inutilizável: %s", error)

    def _pair(self):
        if self.pairing is None or time.monotonic() >= self.pairing_deadline:
            self.pairing = start_pairing(self.device_info, API_URL, self.session)
            self.pairing_deadline = time.monotonic() + PAIRING_RENEW_SECONDS
            self._emit_pairing(self.pairing)

        try:
            activation = claim_pairing(
                self.pairing["pairingToken"], API_URL, self.session, TerminalCredentialStore()
            )
        except TerminalPairingExpired:
            logger.info("Código de pareamento expirado; gerando outro")
            self.pairing = None
            self._emit_pairing(None)
            self._status("Código expirado. Gerando um novo...", False)
            return

        if activation is None:
            self._status("Aguardando a confirmação do código no app administrativo...", False)
            return

        self.pairing = None
        self._emit_pairing(None)
        if not self.isInterruptionRequested():
            self.activation_found.emit(activation)

    def _check_activation_by_serial(self):
        response = self.session.get(
            f"{API_URL}/terminal/serial/{self.serial_number}",
            timeout=5
        )
        if response.status_code == 404:
            self._status("Aguardando liberação do terminal...", False)
            return
        if response.status_code != 200:
            self._status("Não foi possível consultar a ativação.", True)
            logger.warning("Consulta de ativação falhou: status=%s", response.status_code)
            return

        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Resposta de ativação não é um objeto JSON")
        if data.get("activated") is True:
            if not (data.get("terminalId") or data.get("uuid")):
                raise ValueError("Ativacao sem terminalId")
            if not self.isInterruptionRequested():
                self.activation_found.emit(data)
        else:
            self._status("Aguardando liberação do terminal...", False)

    def _emit_pairing(self, pairing):
        if not self.isInterruptionRequested():
            self.pairing_changed.emit(
                None if pairing is None
                else {"code": pairing["code"], "qrPayload": pairing["qrPayload"]}
            )

    def _status(self, message, is_error):
        if not self.isInterruptionRequested():
            self.status_changed.emit(message, is_error)


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
        self.pairing_code = None
        self.activation_worker = ActivationCheckThread(self.device_info, self)
        self.activation_worker.activation_found.connect(self._concluir_ativacao)
        self.activation_worker.status_changed.connect(self._atualizar_status)
        self.activation_worker.pairing_changed.connect(self._mostrar_pareamento)

        self._carregar_estilo()
        self._montar_interface()
        self._mostrar_pareamento(None)

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

        self.title = QLabel("APP 24/7")
        self.title.setObjectName("activationTitle")
        self.title.setAlignment(Qt.AlignCenter)

        self.subtitle = QLabel(
            "Terminal não configurado. No app administrativo, escaneie o QR Code "
            "ou digite o código abaixo para ativar este equipamento."
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

        self.wifi_button = QPushButton("CONFIGURAR WI-FI")
        self.wifi_button.setProperty("variant", "secondary")
        if self.parent_app is not None and hasattr(
            self.parent_app, "abrir_wifi_pre_ativacao"
        ):
            self.wifi_button.clicked.connect(
                self.parent_app.abrir_wifi_pre_ativacao
            )
        else:
            self.wifi_button.setEnabled(False)

        self.details_panel = QWidget(self.card)
        self.details_panel.setObjectName("activationDetails")
        details_layout = QVBoxLayout(self.details_panel)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(Spacing.MD)
        details_layout.addStretch(1)
        details_layout.addWidget(self.info_label)
        details_layout.addWidget(self.status_label)
        details_layout.addWidget(self.wifi_button)
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

    def _mostrar_pareamento(self, pairing):
        """QR e código vêm do backend; sem sessão ativa, a tela só mostra o serial."""
        self.pairing_code = pairing["code"] if pairing else None
        if pairing:
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(pairing["qrPayload"])
            qr.make(fit=True)
            buffer = BytesIO()
            qr.make_image(fill_color="black", back_color="white").save(
                buffer,
                format="PNG"
            )
            self._qr_pixmap.loadFromData(buffer.getvalue(), "PNG")
            self._redimensionar_qrcode()
        else:
            self._qr_pixmap = QPixmap()
            self.qr_label.clear()

        if self.pairing_code:
            code_line = f"Código de pareamento: {self.pairing_code}\n"
        elif self._credential_available():
            code_line = ""
        else:
            code_line = "Gerando código de pareamento...\n"
        self.info_label.setText(
            code_line
            + f"Serial: {self.device_info['serialNumber']}\n"
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
        if terminal_access_state.get() in {"AUTH_REQUIRED", "FORBIDDEN"}:
            self._atualizar_status(
                "Operacao bloqueada. Apos o reprovisionamento administrativo, "
                "reinicie o Terminal.",
                True,
            )
            return
        if Terminal.is_activated() and self._credential_available():
            self.activation_timer.stop()
            terminal_access_state.set("OPERATIONAL")
            self.parent_app.iniciar_operacao_terminal()
            self.parent_app.setCurrentWidget(self.parent_app.welcome)
            return

        if self.activation_worker.isRunning():
            return

        self._atualizar_status("Consultando ativação...", False, state="loading")
        self.activation_worker.start()

    @staticmethod
    def _credential_available():
        try:
            return bool(TerminalCredentialStore().load())
        except TerminalCredentialMissing as error:
            logger.error("Credencial do dispositivo inutilizável: %s", error)
            return False

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
        terminal_access_state.set("OPERATIONAL")
        self._atualizar_status("Terminal ativado com sucesso.", False, state="success")
        self.parent_app.iniciar_operacao_terminal()
        self.parent_app.setCurrentWidget(self.parent_app.welcome)
