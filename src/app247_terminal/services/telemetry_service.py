import logging
import threading
from datetime import datetime, timezone

import requests

from app247_terminal.config.settings import API_URL, TELEMETRY_INTERVAL_SECONDS, TELEMETRY_TIMEOUT_SECONDS, TERMINAL_CONFIG_PATH
from app247_terminal.models.terminal import Terminal
from app247_terminal.services.application_metrics import ApplicationMetricsCollector
from app247_terminal.services.display_metrics import DisplayMetricsCollector
from app247_terminal.services.network_metrics import NetworkMetricsCollector
from app247_terminal.services.system_metrics import SystemMetricsCollector
from app247_terminal.services.backend_client import BackendClient, BackendHttpError


logger = logging.getLogger(__name__)


class TelemetryService:
    def __init__(self, sync_service, purchase_session, websocket_state_provider,
                 screen_provider, api_url=API_URL, terminal_path=TERMINAL_CONFIG_PATH,
                 interval_seconds=TELEMETRY_INTERVAL_SECONDS,
                 timeout_seconds=TELEMETRY_TIMEOUT_SECONDS, session=None,
                 system_collector=None, network_collector=None,
                 application_collector=None, display_collector=None,
                 credential_store=None):
        self.api_url = (api_url or "").rstrip("/")
        self.terminal_path = terminal_path
        self.interval_seconds = interval_seconds
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self.client = BackendClient(
            self.api_url, self.session, credential_store=credential_store
        )
        self.system = system_collector or SystemMetricsCollector()
        self.network = network_collector or NetworkMetricsCollector(self.api_url)
        self.application = application_collector or ApplicationMetricsCollector(
            sync_service, purchase_session, websocket_state_provider)
        self.display = display_collector or DisplayMetricsCollector(screen_provider)
        self._stop_event = threading.Event()
        self._thread = None

    def build_payload(self, terminal):
        return {
            "terminalUuid": terminal.terminalId,
            "capturedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "system": self.system.collect(), "network": self.network.collect(),
            "application": self.application.collect(), "display": self.display.collect(),
        }

    def collect_and_send(self):
        try:
            terminal = Terminal.load(self.terminal_path)
            if terminal is None or not terminal.activated or not terminal.ativo or not self.api_url:
                return False
            payload = self.build_payload(terminal)
            self.client.request(
                "POST",
                "/terminal/telemetry",
                terminal_id=terminal.terminalId,
                json=payload,
                timeout=self.timeout_seconds,
                expected=(200, 202, 204),
            )
            logger.info("[TELEMETRY] amostra enviada terminal=%s", terminal.terminalId)
            return True
        except requests.RequestException as error:
            logger.warning("[TELEMETRY] envio descartado; nova tentativa no próximo ciclo: %s", error)
            return False
        except BackendHttpError as error:
            logger.warning(
                "[TELEMETRY] backend recusou amostra status=%s code=%s",
                error.status, error.code,
            )
            return False
        except Exception:
            logger.exception("[TELEMETRY] coleta descartada; Terminal continuará operando")
            return False

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self.collect_and_send()
            except Exception:
                logger.exception("[TELEMETRY] falha inesperada; Terminal continuará operando")
            if self._stop_event.wait(self.interval_seconds):
                break

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return self._thread
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="terminal-telemetry", daemon=True)
        self._thread.start()
        return self._thread

    def stop(self):
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=min(2, self.timeout_seconds))
