"""Identidade operacional individual do equipamento e migracao legado explicita."""

import os
from pathlib import Path

from config import (
    DEVICE_CREDENTIAL_PATH,
    LEGACY_TERMINAL_AUTH_ENABLED,
    TERMINAL_INTERNAL_TOKEN,
)


class TerminalCredentialMissing(RuntimeError):
    pass


class LegacyTerminalAuthDisabled(RuntimeError):
    pass


class TerminalCredentialStore:
    """Armazena a credencial bruta somente no dispositivo, com troca atomica."""

    def __init__(self, path=DEVICE_CREDENTIAL_PATH):
        self.path = Path(path)

    def load(self):
        try:
            credential = self.path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise TerminalCredentialMissing(
                "Credencial do dispositivo nao pode ser lida"
            ) from error
        return credential or None

    def install(self, credential):
        value = str(credential or "").strip()
        if not value:
            raise ValueError("Credencial individual vazia")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                0o600,
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600)
        except Exception:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise

    def remove(self):
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def terminal_auth_headers(terminal_id=None, require_credential=True, store=None):
    credential = (store or TerminalCredentialStore()).load()
    if require_credential and not credential:
        raise TerminalCredentialMissing(
            "Credencial do dispositivo nao configurada no runtime local"
        )
    if not credential:
        return {}
    headers = {"X-Terminal-Token": credential}
    if terminal_id:
        headers["X-Terminal-Id"] = str(terminal_id)
    return headers


def legacy_migration_headers(terminal_id=None):
    """Nunca e fallback operacional; serve apenas ao endpoint de migracao."""
    if not LEGACY_TERMINAL_AUTH_ENABLED:
        raise LegacyTerminalAuthDisabled(
            "Migracao com segredo compartilhado nao esta habilitada"
        )
    if not TERMINAL_INTERNAL_TOKEN:
        raise TerminalCredentialMissing("Segredo legado de migracao ausente")
    headers = {"X-Terminal-Token": TERMINAL_INTERNAL_TOKEN}
    if terminal_id:
        headers["X-Terminal-Id"] = str(terminal_id)
    return headers


def migrate_legacy_credential(
    terminal_id, base_url, session, store=None, timeout=5
):
    """Troca explicitamente o segredo legado por uma credencial individual."""
    credential_store = store or TerminalCredentialStore()
    response = session.post(
        f"{str(base_url).rstrip('/')}/terminal/{terminal_id}/credential/migrate",
        headers=legacy_migration_headers(terminal_id),
        timeout=timeout,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(f"Migracao de credencial recusada (HTTP {response.status_code})")
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Resposta de migracao invalida")
    if str(payload.get("terminalId")) != str(terminal_id):
        raise ValueError("Credencial recebida para outro Terminal")
    credential = payload.get("credential")
    if not credential:
        raise ValueError("Resposta de migracao sem credencial")
    credential_store.install(credential)
    return {
        "terminalId": str(terminal_id),
        "version": payload.get("version"),
        "createdAt": payload.get("createdAt"),
    }
