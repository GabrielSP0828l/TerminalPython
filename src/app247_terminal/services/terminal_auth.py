"""Identidade operacional individual do equipamento e migração legado explícita."""

import argparse
import getpass
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

from app247_terminal.config.settings import (
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
            metadata = self.path.lstat()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise TerminalCredentialMissing(
                "Credencial do dispositivo não pode ser inspecionada"
            ) from error
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise TerminalCredentialMissing(
                "Credencial do dispositivo deve ser um arquivo regular"
            )
        if metadata.st_mode & 0o077:
            raise TerminalCredentialMissing(
                "Credencial do dispositivo possui permissões inseguras"
            )
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(self.path, flags)
            with os.fdopen(descriptor, "rb") as stream:
                opened = os.fstat(stream.fileno())
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or opened.st_mode & 0o077
                    or opened.st_size > 4096
                ):
                    raise TerminalCredentialMissing(
                        "Arquivo de credencial do dispositivo inválido"
                    )
                raw = stream.read(4097)
        except (OSError, UnicodeError) as error:
            raise TerminalCredentialMissing(
                "Credencial do dispositivo não pode ser lida"
            ) from error
        try:
            credential = raw.decode("ascii")
            return _validate_credential(credential)
        except ValueError as error:
            raise TerminalCredentialMissing(
                "Credencial do dispositivo possui formato inválido"
            ) from error

    def install(self, credential):
        value = _validate_credential(str(credential or ""))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            existing = self.path.lstat()
            if stat.S_ISLNK(existing.st_mode) or not stat.S_ISREG(existing.st_mode):
                raise ValueError("Destino da credencial não é um arquivo regular")
        except FileNotFoundError:
            pass
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", dir=self.path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600)
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
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


_CREDENTIAL_PATTERN = re.compile(r"tdc_[A-Za-z0-9_-]{4,508}\Z")


def _validate_credential(credential: str) -> str:
    if not _CREDENTIAL_PATTERN.fullmatch(credential):
        raise ValueError("Credencial individual deve usar o formato tdc_ esperado")
    return credential


def install_credential_from_stdin(store=None) -> None:
    """Provisiona sem expor o segredo em argumentos ou variáveis de ambiente."""
    if sys.stdin.isatty():
        credential = getpass.getpass("Credencial individual do Terminal: ")
    else:
        credential = sys.stdin.read().rstrip("\r\n")
    (store or TerminalCredentialStore()).install(credential)


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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Gerencia a credencial local do Terminal")
    parser.add_argument(
        "--install-from-stdin", action="store_true",
        help="instala a credencial sem colocá-la na linha de comando",
    )
    arguments = parser.parse_args(argv)
    if not arguments.install_from_stdin:
        parser.error("informe --install-from-stdin")
    install_credential_from_stdin()
    print(f"Credencial instalada com segurança em {DEVICE_CREDENTIAL_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
