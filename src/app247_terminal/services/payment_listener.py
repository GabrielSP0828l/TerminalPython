import json
import logging
import time

from PyQt5.QtCore import QThread, pyqtSignal
from websocket import ABNF, WebSocket, WebSocketTimeoutException

from app247_terminal.config.settings import WS_URL
from app247_terminal.models.terminal import Terminal
from app247_terminal.services.terminal_auth import terminal_auth_headers
from app247_terminal.services import shutdown_budget


class PaymentSocketStale(ConnectionError):
    """O servidor parou de responder sem fechar a conexão (BUG-049)."""


class PaymentListener(QThread):
    AUTH_RETRY_SECONDS = 60
    # Sem nenhum frame por PING_INTERVAL_SECONDS, envia ping; sem resposta em
    # PONG_TIMEOUT_SECONDS, considera a conexão meio-aberta e reconecta.
    PING_INTERVAL_SECONDS = 20
    PONG_TIMEOUT_SECONDS = 15

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
        self._clock = time.monotonic
        self._last_frame_at = None
        self._ping_sent_at = None

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
                self._mark_alive()
                self._notify_connected()

                while self.is_running:

                    self._check_liveness()
                    try:
                        opcode, payload = self.ws.recv_data(control_frame=True)
                    except WebSocketTimeoutException:
                        continue
                    self._handle_frame(opcode, payload)

            except Exception as e:
                if self.is_running:
                    if self._is_auth_failure(e):
                        # O handshake não traz código do backend: quem bloqueia a
                        # operação é o HTTP. Aqui só se reduz o ritmo de tentativas.
                        self.connection_state = "AUTH_REQUIRED"
                        logging.getLogger(__name__).error(
                            "[PAYMENT-WS] handshake recusado com 401; "
                            "nova tentativa em %ss", self.AUTH_RETRY_SECONDS
                        )
                        self.disconnected.emit()
                        self._sleep_while_running(self.AUTH_RETRY_SECONDS)
                        continue
                    self.connection_state = "RECONNECTING"
                    logging.getLogger(__name__).warning("WebSocket de pagamento desconectado: %s", e)
                    self.disconnected.emit()
                    self.sleep(5)

    def _mark_alive(self):
        self._last_frame_at = self._clock()
        self._ping_sent_at = None

    def _check_liveness(self):
        """Envia ping quando a conexão está quieta; derruba se o pong não vier."""
        now = self._clock()
        if self._ping_sent_at is not None:
            if now - self._ping_sent_at > self.PONG_TIMEOUT_SECONDS:
                raise PaymentSocketStale(
                    f"sem resposta ao ping em {self.PONG_TIMEOUT_SECONDS}s"
                )
            return
        if now - self._last_frame_at >= self.PING_INTERVAL_SECONDS:
            self.ws.ping()
            self._ping_sent_at = now

    def _handle_frame(self, opcode, payload):
        # Qualquer frame (evento, ping ou pong do servidor) prova a conexão viva.
        self._mark_alive()
        if opcode == ABNF.OPCODE_CLOSE:
            raise ConnectionError("servidor fechou o WebSocket de pagamento")
        if opcode != ABNF.OPCODE_TEXT or not payload:
            return
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logging.getLogger(__name__).warning("Evento WebSocket com JSON inválido")
            return
        self.route_message(data)

    def _sleep_while_running(self, seconds):
        for _ in range(seconds):
            if not self.is_running:
                return
            self.sleep(1)

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
        self.wait(shutdown_budget.wait_ms(6000))
