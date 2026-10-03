import json
import logging

from PyQt5.QtCore import QThread, pyqtSignal
from websocket import WebSocket, WebSocketTimeoutException

from config import WS_URL
from model.Terminal import Terminal
from service.TerminalAuth import terminal_auth_headers
from service.BackendClient import terminal_access_state


class PaymentListener(QThread):
    payment_status_signal = pyqtSignal(dict)
    product_sync_required = pyqtSignal(dict)
    factory_reset_required = pyqtSignal(dict)
    lifecycle_check_requested = pyqtSignal(str)
    sync_requested = pyqtSignal(str)
    connected = pyqtSignal()
    disconnected = pyqtSignal()

    def __init__(self, parent=None, credential_store=None):
        self.terminal_id = Terminal.load().uuidTerminal
        super().__init__(parent)

        self.is_running = True
        self.ws = None
        self._has_connected = False
        self.connection_state = "DISCONNECTED"
        self.credential_store = credential_store

    def _notify_connected(self):
        origin = "WEBSOCKET_RECONNECT" if self._has_connected else "WEBSOCKET_CONNECTED"
        self._has_connected = True
        self.connection_state = "CONNECTED"
        logging.getLogger(__name__).info("[WEBSOCKET] conectado")
        self.connected.emit()
        self.sync_requested.emit(origin)
        self.lifecycle_check_requested.emit(origin)

    def route_message(self, data):
        if not isinstance(data, dict):
            logging.getLogger(__name__).warning("Evento WebSocket não é um objeto")
            return
        event_type = data.get("type")
        if event_type == "PAYMENT_STATUS":
            self.payment_status_signal.emit(data)
        elif event_type == "PRODUCT_SYNC_REQUIRED":
            self.product_sync_required.emit(data)
        elif event_type in {"TERMINAL_FACTORY_RESET_REQUIRED", "FACTORY_RESET_REQUIRED"}:
            # WebSocket somente acelera. A aplicação consulta HTTP antes de apagar dados.
            self.factory_reset_required.emit(data)
        else:
            logging.getLogger(__name__).warning(
                "Evento WebSocket ignorado: type=%s", event_type
            )

    def run(self):

        while self.is_running:

            try:

                self.ws = WebSocket()
                self.ws.settimeout(5)

                logging.getLogger(__name__).info(
                    "[PAYMENT-WS] conectando socket nativo terminalId=%s configured=%s",
                    self.terminal_id, bool(WS_URL),
                )
                headers = terminal_auth_headers(
                    self.terminal_id, store=self.credential_store
                )
                connect_options = {}
                if headers:
                    connect_options["header"] = [
                        f"{name}: {value}" for name, value in headers.items()
                    ]
                self.ws.connect(
                    f"{WS_URL}/payment-socket/{self.terminal_id}",
                    suppress_origin=True,
                    **connect_options,
                )
                self._notify_connected()

                while self.is_running:

                    try:
                        message = self.ws.recv()
                    except WebSocketTimeoutException:
                        continue

                    if not message:
                        continue

                    try:

                        data = json.loads(message)

                        self.route_message(data)

                    except json.JSONDecodeError:

                        logging.getLogger(__name__).warning("Evento WebSocket com JSON inválido")

            except Exception as e:
                if self.is_running:
                    if self._is_auth_failure(e):
                        self.connection_state = "AUTH_REQUIRED"
                        terminal_access_state.set("AUTH_REQUIRED")
                        logging.getLogger(__name__).error(
                            "[PAYMENT-WS] credencial individual recusada; "
                            "reprovisionamento necessario"
                        )
                        self.disconnected.emit()
                        return
                    self.connection_state = "RECONNECTING"
                    logging.getLogger(__name__).warning("WebSocket de pagamento desconectado: %s", e)
                    self.disconnected.emit()
                    self.sleep(5)

    @staticmethod
    def _is_auth_failure(error):
        return getattr(error, "status_code", None) == 401

    def stop(self):

        self.is_running = False
        self.connection_state = "DISCONNECTED"
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass
        self.wait(6000)
