import json
import logging
import threading

import websocket

from config import (
    HEARTBEAT_ACK_TIMEOUT_SECONDS,
    HEARTBEAT_INTERVAL_SECONDS,
    HEARTBEAT_RETRY_SECONDS,
    TERMINAL_CONFIG_PATH,
    WS_URL,
)
from model.Terminal import Terminal


logger = logging.getLogger(__name__)


class TerminalSocket:

    def __init__(
        self,
        ws_url=WS_URL,
        terminal_path=TERMINAL_CONFIG_PATH,
        interval_seconds=HEARTBEAT_INTERVAL_SECONDS,
        retry_seconds=HEARTBEAT_RETRY_SECONDS,
        ack_timeout_seconds=HEARTBEAT_ACK_TIMEOUT_SECONDS,
        websocket_factory=websocket.WebSocket,
    ):
        self.ws_url = (ws_url or "").rstrip("/")
        self.terminal_path = terminal_path
        self.interval_seconds = interval_seconds
        self.retry_seconds = retry_seconds
        self.ack_timeout_seconds = ack_timeout_seconds
        self.websocket_factory = websocket_factory
        self.ws = None
        self._thread = None
        self._stop_event = threading.Event()

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return self._thread
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._heartbeat,
            name="terminal-heartbeat",
            daemon=True,
        )
        self._thread.start()
        return self._thread

    def _load_active_terminal(self):
        terminal = Terminal.load(self.terminal_path)
        if terminal is None or not terminal.activated or not terminal.ativo:
            return None
        return terminal

    def _connect(self):
        if not self.ws_url:
            raise ValueError("WS_URL não configurada")
        self.ws = self.websocket_factory()
        self.ws.settimeout(self.ack_timeout_seconds)
        self.ws.connect(f"{self.ws_url}/terminal-socket")
        logger.info("[HEARTBEAT] Conectado ao backend")

    def _send_and_confirm(self, terminal):
        payload = {
            "terminalId": terminal.terminalId,
            "status": "ONLINE",
        }
        self.ws.send(json.dumps(payload))
        acknowledgement = json.loads(self.ws.recv())
        if acknowledgement.get("type") != "HEARTBEAT_ACK":
            raise ValueError("resposta inesperada do heartbeat")
        if str(acknowledgement.get("terminalId")) != terminal.terminalId:
            raise ValueError("heartbeat confirmado para outro terminal")
        if not acknowledgement.get("lastPing"):
            raise ValueError("heartbeat confirmado sem lastPing")
        logger.info(
            "[HEARTBEAT] Enviado com sucesso; terminal=%s lastPing=%s",
            terminal.terminalId,
            acknowledgement["lastPing"],
        )

    def _heartbeat(self):
        while not self._stop_event.is_set():
            terminal = self._load_active_terminal()
            if terminal is None:
                logger.info("[HEARTBEAT] Terminal não ativado; aguardando ativação")
                self._stop_event.wait(self.retry_seconds)
                continue
            try:
                self._connect()
                while not self._stop_event.is_set():
                    self._send_and_confirm(terminal)
                    self._stop_event.wait(self.interval_seconds)
            except Exception as error:
                if not self._stop_event.is_set():
                    logger.warning("[HEARTBEAT] Backend indisponível: %s", error)
                    self._stop_event.wait(self.retry_seconds)
            finally:
                self._close_socket()

    def _close_socket(self):
        ws, self.ws = self.ws, None
        if ws is not None:
            try:
                ws.close()
            except Exception as error:
                logger.debug("Falha ao fechar WebSocket de heartbeat: %s", error)

    def stop(self):
        self._stop_event.set()
        self._close_socket()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
