import json
import logging

from PyQt5.QtCore import QThread, pyqtSignal
from websocket import WebSocket, WebSocketTimeoutException

from config import WS_URL
from model.Terminal import Terminal


class PaymentListener(QThread):
    payment_status_signal = pyqtSignal(dict)
    product_sync_required = pyqtSignal(dict)
    sync_requested = pyqtSignal(str)
    connected = pyqtSignal()
    disconnected = pyqtSignal()

    def __init__(self, parent=None):
        self.terminal_id = Terminal.load().uuidTerminal
        super().__init__(parent)

        self.is_running = True
        self.ws = None
        self._has_connected = False

    def _notify_connected(self):
        origin = "WEBSOCKET_RECONNECT" if self._has_connected else "WEBSOCKET_CONNECTED"
        self._has_connected = True
        logging.getLogger(__name__).info("[WEBSOCKET] conectado")
        self.connected.emit()
        self.sync_requested.emit(origin)

    def route_message(self, data):
        if not isinstance(data, dict):
            logging.getLogger(__name__).warning("Evento WebSocket não é um objeto")
            return
        event_type = data.get("type")
        if event_type == "PAYMENT_STATUS":
            self.payment_status_signal.emit(data)
        elif event_type == "PRODUCT_SYNC_REQUIRED":
            self.product_sync_required.emit(data)
        else:
            logging.getLogger(__name__).warning(
                "Evento WebSocket ignorado: type=%s", event_type
            )

    def run(self):

        while self.is_running:

            try:

                self.ws = WebSocket()
                self.ws.settimeout(5)

                self.ws.connect(
                    f"{WS_URL}/payment-socket/{self.terminal_id}"
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
                    logging.getLogger(__name__).warning("WebSocket de pagamento desconectado: %s", e)
                    self.disconnected.emit()
                    self.sleep(5)

    def stop(self):

        self.is_running = False
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass
        self.wait(6000)
