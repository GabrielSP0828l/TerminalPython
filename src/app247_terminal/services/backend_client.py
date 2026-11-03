"""Cliente HTTP comum para contratos Terminal -> Spring Boot."""

import logging
import threading

import requests

from app247_terminal.config.settings import API_URL
from app247_terminal.services.terminal_auth import terminal_auth_headers


logger = logging.getLogger(__name__)

# Só estes códigos do backend provam problema do equipamento. Outro 401/403 pode
# vir do túnel/proxy ou de regra de negócio (ex.: QR de outro condomínio).
DEVICE_UNAUTHORIZED_CODES = frozenset({
    "AUTH_REQUIRED", "TERMINAL_AUTH_INVALID", "TERMINAL_UNAUTHORIZED",
})
DEVICE_FORBIDDEN_CODES = frozenset({
    "TERMINAL_CONTEXT_MISMATCH", "TERMINAL_IDENTITY_MISMATCH",
    "TERMINAL_NOT_OPERATIONAL",
})


class TerminalAccessState:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = "OPERATIONAL"

    def set(self, state):
        with self._lock:
            self._state = state

    def get(self):
        with self._lock:
            return self._state


terminal_access_state = TerminalAccessState()


class BackendHttpError(RuntimeError):
    def __init__(self, status, code=None, message=None, payload=None):
        self.status = int(status) if status is not None else None
        self.code = str(code or "").strip() or None
        self.payload = payload if isinstance(payload, dict) else {}
        super().__init__(message or self._default_message())

    @property
    def authentication_failed(self):
        return self.status == 401

    @property
    def forbidden(self):
        return self.status == 403

    @property
    def device_unauthorized(self):
        return self.status == 401 and self.code in DEVICE_UNAUTHORIZED_CODES

    @property
    def device_forbidden(self):
        return self.status == 403 and self.code in DEVICE_FORBIDDEN_CODES

    def _default_message(self):
        if self.status == 401:
            return "Credencial do Terminal ausente, invalida ou revogada"
        if self.status == 403:
            return "Terminal autenticado sem permissao para esta operacao"
        if self.status == 404:
            return "Recurso nao encontrado"
        if self.status == 409:
            return "Operacao em conflito com o estado atual"
        if self.status == 429:
            return "Limite de requisicoes excedido"
        return "Backend indisponivel"


class BackendClient:
    """Centraliza URL, identidade, timeouts e semantica HTTP sem logar segredos."""

    def __init__(self, base_url=API_URL, session=None, credential_store=None):
        self.base_url = (base_url or "").rstrip("/")
        self.session = session or requests.Session()
        self.credential_store = credential_store

    def request(
        self,
        method,
        path,
        *,
        terminal_id=None,
        authenticated=True,
        timeout=10,
        expected=(200,),
        **kwargs,
    ):
        if not self.base_url:
            raise BackendHttpError(None, "BACKEND_NOT_CONFIGURED")
        headers = dict(kwargs.pop("headers", {}) or {})
        if authenticated:
            headers.update(
                terminal_auth_headers(terminal_id, store=self.credential_store)
            )
        request_method = (
            getattr(self.session, "request", None)
            if getattr(type(self.session), "request", None) is not None
            else None
        )
        if request_method is not None:
            response = request_method(
                method.upper(),
                f"{self.base_url}{path}",
                headers=headers,
                timeout=timeout,
                **kwargs,
            )
        else:
            response = getattr(self.session, method.lower())(
                f"{self.base_url}{path}",
                headers=headers,
                timeout=timeout,
                **kwargs,
            )
        status = getattr(response, "status_code", None)
        logger.info(
            "[BACKEND] request concluida method=%s endpoint=%s status=%s",
            method.upper(),
            path,
            status,
        )
        if status not in tuple(expected):
            payload = self._safe_json(response)
            error = BackendHttpError(
                status, payload.get("code"), payload.get("message"), payload
            )
            if error.device_unauthorized:
                terminal_access_state.set("AUTH_REQUIRED")
            elif error.device_forbidden:
                terminal_access_state.set("FORBIDDEN")
            raise error
        return response

    @staticmethod
    def _safe_json(response):
        try:
            payload = response.json()
        except (ValueError, TypeError):
            return {}
        return payload if isinstance(payload, dict) else {}
