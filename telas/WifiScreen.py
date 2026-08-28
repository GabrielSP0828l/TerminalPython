from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from service.WifiService import WifiService, WifiWorker
from styles.animated_svg import AnimatedSvgWidget
from styles.theme import Theme
from styles.tokens import Colors, Spacing
from telas.teclado import VirtualKeyboard


class WifiScreen(QWidget):
    """Tela administrativa touchscreen; comandos permanecem no WifiService."""

    def __init__(self, parent_app, on_back, service=None, parent=None):
        super().__init__(parent)
        self.parent_app = parent_app
        self.on_back = on_back
        self.service = service or WifiService()
        self.worker = None
        self._operation_token = 0
        self._selected_network = None
        self._retry_action = None
        self._page_active = False

        self.setProperty("role", "page")
        self.setObjectName("wifiScreen")
        self.setStyleSheet(Theme.wifi_stylesheet())
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget(self)
        root.addWidget(self.pages)
        self.main_page = self._build_main_page()
        self.password_page = self._build_password_page()
        self.feedback_page = self._build_feedback_page()
        for page in (self.main_page, self.password_page, self.feedback_page):
            self.pages.addWidget(page)

    def _build_main_page(self):
        page = QWidget(self)
        page.setProperty("role", "page")
        root = QVBoxLayout(page)
        root.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        root.setSpacing(Spacing.MD)

        header = QHBoxLayout()
        title = QLabel("WI-FI")
        title.setProperty("role", "pageTitle")
        self.refresh_button = QPushButton("ATUALIZAR REDES")
        self.refresh_button.setProperty("variant", "primary")
        self.refresh_button.clicked.connect(self.refresh)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.refresh_button)

        status_card = QFrame(page)
        status_card.setObjectName("wifiStatusCard")
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        current = QVBoxLayout()
        self.current_state = QLabel("Verificando Wi-Fi...")
        self.current_state.setObjectName("wifiCurrentSsid")
        self.current_details = QLabel()
        self.current_details.setObjectName("wifiCurrentDetails")
        current.addWidget(self.current_state)
        current.addWidget(self.current_details)
        self.disconnect_button = QPushButton("DESCONECTAR")
        self.disconnect_button.setProperty("variant", "danger")
        self.disconnect_button.clicked.connect(self.confirm_disconnect)
        self.enable_button = QPushButton("ATIVAR WI-FI")
        self.enable_button.setProperty("variant", "primary")
        self.enable_button.clicked.connect(self.enable_wifi)
        status_layout.addLayout(current, 1)
        status_layout.addWidget(self.disconnect_button)
        status_layout.addWidget(self.enable_button)
        self.disconnect_button.hide()
        self.enable_button.hide()

        section = QLabel("REDES DISPONÍVEIS")
        section.setProperty("role", "sectionTitle")
        self.network_scroll = QScrollArea(page)
        self.network_scroll.setWidgetResizable(True)
        self.network_container = QWidget()
        self.network_layout = QVBoxLayout(self.network_container)
        self.network_layout.setContentsMargins(0, 0, Spacing.SM, 0)
        self.network_layout.setSpacing(Spacing.SM)
        self.network_scroll.setWidget(self.network_container)
        self.empty_networks = QLabel("Atualizando redes...")
        self.empty_networks.setProperty("role", "pageSubtitle")
        self.empty_networks.setAlignment(Qt.AlignCenter)
        self.network_layout.addWidget(self.empty_networks)
        self.network_layout.addStretch(1)

        back = QPushButton("VOLTAR")
        back.setProperty("variant", "secondary")
        back.clicked.connect(self.leave)
        root.addLayout(header)
        root.addWidget(status_card)
        root.addWidget(section)
        root.addWidget(self.network_scroll, 1)
        root.addWidget(back)
        return page

    def _build_password_page(self):
        page = QWidget(self)
        page.setProperty("role", "page")
        root = QVBoxLayout(page)
        root.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        root.setSpacing(Spacing.SM)
        title = QLabel("CONECTAR AO WI-FI")
        title.setProperty("role", "pageTitle")
        title.setAlignment(Qt.AlignCenter)
        self.password_ssid = QLabel()
        self.password_ssid.setProperty("role", "sectionTitle")
        self.password_ssid.setAlignment(Qt.AlignCenter)
        input_row = QHBoxLayout()
        self.password_input = QLineEdit()
        self.password_input.setProperty("role", "input")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Senha da rede")
        self.show_password_button = QPushButton("MOSTRAR")
        self.show_password_button.setProperty("variant", "secondary")
        self.show_password_button.clicked.connect(self.toggle_password)
        input_row.addWidget(self.password_input, 1)
        input_row.addWidget(self.show_password_button)
        self.keyboard = VirtualKeyboard(page)
        self.keyboard.set_target(self.password_input)
        actions = QHBoxLayout()
        cancel = QPushButton("CANCELAR")
        cancel.setProperty("variant", "secondary")
        cancel.clicked.connect(self.show_main)
        connect = QPushButton("CONECTAR")
        connect.setProperty("variant", "primary")
        connect.setProperty("primaryAction", True)
        connect.clicked.connect(self.connect_with_password)
        actions.addWidget(cancel, 1)
        actions.addWidget(connect, 2)
        root.addWidget(title)
        root.addWidget(self.password_ssid)
        root.addLayout(input_row)
        root.addWidget(self.keyboard, 1)
        root.addLayout(actions)
        return page

    def _build_feedback_page(self):
        page = QWidget(self)
        page.setProperty("role", "page")
        root = QVBoxLayout(page)
        root.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        root.setSpacing(Spacing.LG)
        root.addStretch(1)
        self.feedback_spinner = AnimatedSvgWidget("tube-spinner.svg", Colors.INFO, page)
        self.feedback_spinner.setFixedSize(112, 112)
        self.feedback_title = QLabel()
        self.feedback_title.setProperty("role", "pageTitle")
        self.feedback_title.setAlignment(Qt.AlignCenter)
        self.feedback_message = QLabel()
        self.feedback_message.setObjectName("wifiFeedbackMessage")
        self.feedback_message.setAlignment(Qt.AlignCenter)
        self.feedback_message.setWordWrap(True)
        self.feedback_ssid = QLabel()
        self.feedback_ssid.setProperty("role", "sectionTitle")
        self.feedback_ssid.setAlignment(Qt.AlignCenter)
        self.feedback_actions = QHBoxLayout()
        self.retry_button = QPushButton("TENTAR NOVAMENTE")
        self.retry_button.setProperty("variant", "primary")
        self.retry_button.clicked.connect(self.retry)
        self.feedback_back_button = QPushButton("VOLTAR")
        self.feedback_back_button.setProperty("variant", "secondary")
        self.feedback_back_button.clicked.connect(self.show_main)
        self.feedback_actions.addWidget(self.feedback_back_button, 1)
        self.feedback_actions.addWidget(self.retry_button, 2)
        root.addWidget(self.feedback_spinner, 0, Qt.AlignHCenter)
        root.addWidget(self.feedback_title)
        root.addWidget(self.feedback_ssid)
        root.addWidget(self.feedback_message)
        root.addStretch(1)
        root.addLayout(self.feedback_actions)
        return page

    def show_page(self):
        self._page_active = True
        self.show_main()
        self.refresh()

    def show_main(self):
        self.password_input.clear()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.show_password_button.setText("MOSTRAR")
        self.pages.setCurrentWidget(self.main_page)

    def refresh(self):
        if self._worker_running():
            return
        self.pages.setCurrentWidget(self.main_page)
        self.refresh_button.setEnabled(False)
        self.current_state.setText("Verificando Wi-Fi...")
        self.current_details.setText("Buscando redes disponíveis")
        self._set_network_message("Atualizando redes...")
        self._start_worker("snapshot", {}, self._snapshot_ready, self._snapshot_failed)

    def _snapshot_ready(self, snapshot):
        self.refresh_button.setEnabled(True)
        self._render_status(snapshot.status)
        self._render_networks(snapshot.networks)

    def _snapshot_failed(self, code, message):
        self.refresh_button.setEnabled(True)
        self.current_state.setText("Wi-Fi indisponível")
        self.current_details.setText(message)
        self.disconnect_button.hide()
        self.enable_button.hide()
        self._set_network_message("Não foi possível listar as redes.")

    def _render_status(self, status):
        self.disconnect_button.setVisible(status.connected)
        self.enable_button.setVisible(not status.enabled)
        if not status.enabled:
            self.current_state.setText("Wi-Fi desativado")
            self.current_details.setText("Ative o Wi-Fi para procurar redes.")
        elif status.connected:
            self.current_state.setText(f"Conectado: {status.ssid}")
            details = f"Sinal: {status.signal_label} ({status.signal}%)"
            if status.ip_address:
                details += f"    IP: {status.ip_address}"
            self.current_details.setText(details)
        else:
            self.current_state.setText("Sem conexão")
            self.current_details.setText("Selecione uma rede abaixo.")

    def _render_networks(self, networks):
        self._clear_networks()
        if not networks:
            self._set_network_message("Nenhuma rede encontrada. Toque em ATUALIZAR REDES.")
            return
        for network in networks:
            security = "Protegida" if network.protected else "Aberta"
            known = " • Salva" if network.known and not network.connected else ""
            connected = " • CONECTADO" if network.connected else ""
            button = QPushButton(
                f"{network.ssid}{connected}\nSinal {network.signal_label} ({network.signal}%) • {security}{known}"
            )
            button.setProperty("wifiNetwork", True)
            button.setProperty("connected", network.connected)
            button.setMinimumHeight(76)
            button.clicked.connect(
                lambda checked=False, selected=network: self.select_network(selected)
            )
            self.network_layout.addWidget(button)
        self.network_layout.addStretch(1)

    def select_network(self, network):
        if network.connected or self._worker_running():
            return
        self._selected_network = network
        if network.known:
            if self._confirm_network_change(network.ssid):
                self._connect(network, None)
            return
        if network.protected:
            self.password_ssid.setText(network.ssid)
            self.password_input.clear()
            self.keyboard.set_target(self.password_input)
            self.pages.setCurrentWidget(self.password_page)
            return
        if self._confirm_network_change(network.ssid):
            self._connect(network, None)

    def connect_with_password(self):
        if self._selected_network is None or self._worker_running():
            return
        password = self.password_input.text()
        if not password:
            self.password_input.setProperty("state", "error")
            self.password_input.style().unpolish(self.password_input)
            self.password_input.style().polish(self.password_input)
            return
        if not self._confirm_network_change(self._selected_network.ssid):
            return
        self.password_input.setProperty("state", "")
        self._connect(self._selected_network, password)
        self.password_input.clear()

    def _connect(self, network, password):
        self._show_loading("CONECTANDO AO WI-FI...", network.ssid, "Aguarde a confirmação da rede.")
        self._retry_action = (network, None)
        self._start_worker(
            "connect", {"network": network, "password": password},
            self._connect_ready, self._connect_failed,
        )

    def _connect_ready(self, status):
        self.feedback_spinner.hide()
        self.feedback_title.setText("CONECTADO COM SUCESSO")
        self._set_feedback_state("success")
        self.feedback_ssid.setText(status.ssid)
        detail = f"Sinal {status.signal_label}"
        if status.ip_address:
            detail += f" • IP {status.ip_address}"
        self.feedback_message.setText(detail)
        self.retry_button.hide()
        self.feedback_back_button.setText("VOLTAR AO WI-FI")
        self.feedback_back_button.show()
        QTimer.singleShot(1600, self._refresh_after_success)

    def _refresh_after_success(self):
        if self._page_active:
            self.refresh()

    def _connect_failed(self, code, message):
        if code in {"AUTH_FAILED", "AUTH_REQUIRED"} and self._selected_network is not None:
            self.feedback_spinner.hide()
            self.feedback_title.setText("NÃO FOI POSSÍVEL CONECTAR")
            self._set_feedback_state("error")
            self.feedback_ssid.setText(self._selected_network.ssid)
            self.feedback_message.setText(message)
            self._retry_action = "password"
            self.retry_button.show()
            self.feedback_back_button.show()
            return
        self._show_error(message)
        self._retry_action = "refresh" if code == "NETWORK_UNAVAILABLE" else self._retry_action

    def confirm_disconnect(self):
        if self._worker_running():
            return
        message = (
            "Desconectar do Wi-Fi?\n\n"
            "O Terminal poderá ficar sem acesso ao servidor."
        )
        if self._payment_active():
            message += (
                "\n\nATENÇÃO: existe um pagamento em andamento. A cobrança não será "
                "cancelada e o acompanhamento poderá ser interrompido temporariamente."
            )
        if not self._confirm_action("Desconectar do Wi-Fi", message, "DESCONECTAR"):
            return
        self._show_loading("DESCONECTANDO WI-FI...", "", "Aguarde alguns instantes.")
        self._retry_action = "refresh"
        self._start_worker("disconnect", {}, self._disconnect_ready, self._generic_failed)

    def _disconnect_ready(self, _status):
        # O sinal de sucesso pode chegar um instante antes de QThread encerrar.
        # Adiar evita que refresh() veja o worker anterior como ainda ativo.
        QTimer.singleShot(0, self.refresh)

    def enable_wifi(self):
        if self._worker_running():
            return
        self._show_loading("ATIVANDO WI-FI...", "", "Aguarde alguns instantes.")
        self._retry_action = "refresh"
        self._start_worker("enable_wifi", {}, self._enable_ready, self._generic_failed)

    def _enable_ready(self, snapshot):
        self.pages.setCurrentWidget(self.main_page)
        self._snapshot_ready(snapshot)

    def _generic_failed(self, _code, message):
        self._show_error(message)

    def _show_loading(self, title, ssid, message):
        self.pages.setCurrentWidget(self.feedback_page)
        self.feedback_title.setText(title)
        self._set_feedback_state("loading")
        self.feedback_ssid.setText(ssid)
        self.feedback_message.setText(message)
        self.feedback_spinner.show()
        self.retry_button.hide()
        self.feedback_back_button.hide()

    def _show_error(self, message):
        self.pages.setCurrentWidget(self.feedback_page)
        self.feedback_spinner.hide()
        self.feedback_title.setText("NÃO FOI POSSÍVEL CONCLUIR")
        self._set_feedback_state("error")
        self.feedback_message.setText(message)
        self.retry_button.show()
        self.feedback_back_button.show()

    def _set_feedback_state(self, state):
        self.feedback_title.setProperty("state", state)
        self.feedback_title.style().unpolish(self.feedback_title)
        self.feedback_title.style().polish(self.feedback_title)

    def retry(self):
        action = self._retry_action
        if action == "password" and self._selected_network is not None:
            self.password_ssid.setText(self._selected_network.ssid)
            self.password_input.clear()
            self.pages.setCurrentWidget(self.password_page)
        elif action == "refresh" or action is None:
            self.refresh()
        elif isinstance(action, tuple):
            network, password = action
            if network.protected and password is None and not network.known:
                self.password_ssid.setText(network.ssid)
                self.pages.setCurrentWidget(self.password_page)
            else:
                self._connect(network, password)

    def toggle_password(self):
        visible = self.password_input.echoMode() == QLineEdit.Normal
        self.password_input.setEchoMode(QLineEdit.Password if visible else QLineEdit.Normal)
        self.show_password_button.setText("MOSTRAR" if visible else "OCULTAR")

    def _confirm_network_change(self, ssid):
        message = f"Conectar à rede {ssid}?"
        if self._payment_active():
            message += (
                "\n\nATENÇÃO: existe um pagamento em andamento. Alterar a rede pode "
                "interromper temporariamente o acompanhamento. A cobrança não será cancelada."
            )
        return self._confirm_action("Conectar ao Wi-Fi", message, "CONECTAR")

    def _payment_active(self):
        session = self.parent_app.compra_session
        return bool(
            session.payment_in_flight or session.order_id or session.cart_id
            or session.state in {
                "STARTING_PAYMENT", "WAITING_PAYMENT", "PROCESSING",
                "TIMEOUT_CHECK", "RECONCILIATION_PENDING",
            }
        )

    def _confirm_action(self, title, message, confirm_text):
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setStyleSheet(Theme.component_stylesheet())
        cancel = dialog.addButton("CANCELAR", QMessageBox.RejectRole)
        confirm = dialog.addButton(confirm_text, QMessageBox.AcceptRole)
        dialog.setDefaultButton(cancel)
        dialog.exec_()
        return dialog.clickedButton() is confirm

    def _start_worker(self, operation, parameters, success, failure):
        self._operation_token += 1
        token = self._operation_token
        self.worker = WifiWorker(self.service, operation, parameters, self)
        self.worker.succeeded.connect(
            lambda result, expected=token: self._worker_success(expected, success, result)
        )
        self.worker.failed.connect(
            lambda code, message, expected=token:
            self._worker_failure(expected, failure, code, message)
        )
        self.worker.start()

    def _worker_success(self, token, callback, result):
        if token != self._operation_token:
            return
        callback(result)

    def _worker_failure(self, token, callback, code, message):
        if token != self._operation_token:
            return
        callback(code, message)

    def _worker_running(self):
        return self.worker is not None and self.worker.isRunning()

    def _clear_networks(self):
        while self.network_layout.count():
            item = self.network_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _set_network_message(self, message):
        self._clear_networks()
        label = QLabel(message)
        label.setProperty("role", "pageSubtitle")
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        self.network_layout.addWidget(label)
        self.network_layout.addStretch(1)

    def leave(self):
        self._page_active = False
        self.stop_worker()
        self.password_input.clear()
        self.on_back()

    def stop_worker(self, wait=False):
        self._page_active = False
        self._operation_token += 1
        if self._worker_running():
            self.worker.requestInterruption()
            if wait:
                # subprocess.run não é interrompido pelo flag do QThread; a
                # espera acompanha o timeout máximo e continua sendo limitada.
                self.worker.wait(20000)
