import logging
import time

import requests
from PyQt5.QtCore import QThread, pyqtSignal

from app247_terminal.config.settings import API_URL
from app247_terminal.services import shutdown_budget


logger = logging.getLogger(__name__)


class InternetMonitor(QThread):
    """Deriva a conectividade do heartbeat; HTTP só com o canal WebSocket caído.

    Frames do WebSocket já aberto não consomem cota de requisições da entrada
    pública. O teste HTTP é limitado a ``http_interval`` para uma rede que
    bloqueie WebSocket não voltar a gerar uma requisição a cada ciclo.
    """

    HEALTH_PATH = "/terminal/health"

    status_changed = pyqtSignal(bool)

    def __init__(self, interval=3, target_url=API_URL, request_get=requests.get,
                 channel_state_provider=None, http_interval=30,
                 clock=time.monotonic):
        super().__init__()
        self.interval = interval
        target_url = str(target_url or "").strip().rstrip("/")
        self.target_url = f"{target_url}{self.HEALTH_PATH}" if target_url else ""
        self.request_get = request_get
        self.channel_state_provider = channel_state_provider
        self.http_interval = http_interval
        self.clock = clock
        self.status = None
        self._next_http_check = 0.0
        self._last_http_result = False

    def _channel_connected(self):
        if self.channel_state_provider is None:
            return False
        return self.channel_state_provider() == "CONNECTED"

    def _check_backend_http(self):
        if not self.target_url:
            return False
        try:
            response = self.request_get(self.target_url, timeout=3)
        except requests.RequestException:
            return False
        # Erro do túnel/proxy também chega como HTTP: só 2xx prova o backend.
        return 200 <= response.status_code < 300

    def check_internet(self):
        if self._channel_connected():
            # Queda do canal testa HTTP de imediato no ciclo seguinte.
            self._next_http_check = 0.0
            return True
        now = self.clock()
        if now < self._next_http_check:
            return self._last_http_result
        self._next_http_check = now + self.http_interval
        self._last_http_result = self._check_backend_http()
        return self._last_http_result

    def run(self):
        while not self.isInterruptionRequested():
            new_status = self.check_internet()

            if new_status != self.status:
                self.status = new_status
                logger.info("[NETWORK] backend=%s", "online" if new_status else "offline")
                self.status_changed.emit(self.status)
            self.msleep(max(250, int(self.interval * 1000)))

    def stop(self):
        self.requestInterruption()
        self.wait(shutdown_budget.wait_ms(3500))
