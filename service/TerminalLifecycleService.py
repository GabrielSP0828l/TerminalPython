import logging

import requests
from PyQt5.QtCore import QThread, pyqtSignal

from config import API_URL
from service.FactoryResetService import FactoryResetService
from service.BackendClient import BackendClient, BackendHttpError
from service.TerminalAuth import TerminalCredentialMissing


logger = logging.getLogger(__name__)


class TerminalLifecycleApi:
    """Consulta autoritativa do lifecycle; falha de rede nunca significa reset."""

    KNOWN_STATES = {
        "ACTIVE", "PAYMENT_NOT_CONFIGURED", "DISABLED",
        "RESET_REQUIRED", "UNACTIVATED",
    }

    def __init__(self, base_url=API_URL, session=None, timeout=5,
                 reset_service=None, credential_store=None):
        self.base_url = (base_url or "").rstrip("/")
        self.http = session or requests.Session()
        self.client = BackendClient(
            self.base_url, self.http, credential_store=credential_store
        )
        self.timeout = timeout
        self.reset_service = reset_service or FactoryResetService()

    def check(self, terminal_id):
        if not self.base_url or not terminal_id:
            return None
        try:
            response = self.client.request(
                "GET",
                f"/terminal/{terminal_id}/bootstrap",
                terminal_id=terminal_id,
                timeout=self.timeout,
            )
            data = response.json()
            if not isinstance(data, dict):
                return None
            state = str(data.get("state") or "").upper()
            if state not in self.KNOWN_STATES:
                return None
            data["state"] = state
            return data
        except (requests.RequestException, ValueError, TypeError,
                TerminalCredentialMissing, BackendHttpError) as error:
            logger.warning("[TERMINAL-LIFECYCLE] backend indisponível: %s", error)
            return None

    def notify_started(self, terminal_id):
        return self._post(terminal_id, "started")

    def confirm_pending_reset(self):
        pending = self.reset_service.pending_completion()
        if not pending:
            return True
        if self._post(pending["terminalId"], "completed"):
            self.reset_service.acknowledge_completion()
            return True
        return False

    def _post(self, terminal_id, stage):
        if not self.base_url or not terminal_id:
            return False
        try:
            response = self.client.request(
                "POST",
                f"/terminal/{terminal_id}/factory-reset/{stage}",
                terminal_id=terminal_id,
                timeout=self.timeout,
                expected=(200, 202, 204),
            )
            return True
        except (requests.RequestException, TerminalCredentialMissing,
                BackendHttpError) as error:
            logger.warning(
                "[TERMINAL-LIFECYCLE] confirmação %s pendente: %s", stage, error
            )
            return False


class TerminalLifecycleCheckThread(QThread):
    result_ready = pyqtSignal(object)

    def __init__(self, terminal_id, api=None, parent=None):
        super().__init__(parent)
        self.terminal_id = terminal_id
        self.api = api or TerminalLifecycleApi()

    def run(self):
        self.result_ready.emit(self.api.check(self.terminal_id))


class TerminalResetPolicy:
    UNRESOLVED_STATES = {
        "STARTING_PAYMENT", "WAITING_PAYMENT", "PROCESSING",
        "TIMEOUT_CHECK", "RECONCILIATION_PENDING", "UNKNOWN",
        "CANCELLING", "CANCEL_PENDING",
    }

    @classmethod
    def has_unresolved_payment(cls, purchase_session):
        return bool(
            purchase_session.payment_in_flight
            or purchase_session.order_id
            or purchase_session.cart_id
            or purchase_session.state in cls.UNRESOLVED_STATES
        )
