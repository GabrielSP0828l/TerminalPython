import json
import os
import sqlite3
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config import PROJECT_ROOT
from service.TerminalAuth import TerminalCredentialStore


class ResetBlockedActivePayment(RuntimeError):
    code = "RESET_BLOCKED_ACTIVE_PAYMENT"


class ResetBlockedCriticalState(RuntimeError):
    code = "RESET_BLOCKED_CRITICAL_STATE"


class FactoryResetService:
    RESET_MARKER = Path("db/factory-reset.pending")
    COMPLETION_MARKER = Path("db/factory-reset-completion.pending")
    LOCAL_STATE_FILES = (
        Path("db/terminal.json"),
        Path("db/terminal.db"),
        Path("database/last_sync.txt"),
        Path("temp_checkout.png"),
    )

    def __init__(self, base_dir=PROJECT_ROOT, credential_store=None):
        self.base_dir = Path(base_dir)
        if credential_store is None:
            credential_path = (
                None if self.base_dir.resolve() == Path(PROJECT_ROOT).resolve()
                else self.base_dir / "db/device-credential"
            )
            credential_store = (
                TerminalCredentialStore()
                if credential_path is None
                else TerminalCredentialStore(credential_path)
            )
        self.credential_store = credential_store

    def request_reset(self, terminal_id=None, reason="LOCAL_ADMIN", remote=False):
        marker = self.base_dir / self.RESET_MARKER
        marker.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_json_write(marker, {
            "resetId": uuid.uuid4().hex,
            "terminalId": str(terminal_id) if terminal_id else None,
            "reason": str(reason or "UNKNOWN"),
            "remote": bool(remote),
            "requestedAt": datetime.now(timezone.utc).isoformat(),
            "version": 2,
        })

    def apply_pending(self):
        marker = self.base_dir / self.RESET_MARKER
        if not marker.exists():
            return None

        request = self._read_request(marker)
        self._assert_financial_state_can_be_reset()
        remote = bool(request.get("remote"))
        reset_id = str(request.get("resetId") or uuid.uuid4().hex)
        backup_dir = self._reset_directory(reset_id, remote)
        moved_files = []

        try:
            for relative_path in self.LOCAL_STATE_FILES:
                source = self.base_dir / relative_path
                if not source.exists():
                    continue

                destination = backup_dir / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))
                moved_files.append(relative_path)

            if remote and request.get("terminalId"):
                self._atomic_json_write(
                    self.base_dir / self.COMPLETION_MARKER,
                    {
                        "resetId": reset_id,
                        "terminalId": str(request["terminalId"]),
                        "completedAt": datetime.now(timezone.utc).isoformat(),
                        "version": 1,
                    },
                )

            # Reset remoto precisa da identidade uma ultima vez para confirmar
            # /completed. O ACK remove a credencial; reset local remove agora.
            if not remote:
                self.credential_store.remove()

            # Backups do reset administrativo local são recuperáveis. Um reset remoto por
            # encerramento da Empresa elimina o staging para nenhum dado do tenant antigo
            # reaparecer em uma futura ativação.
            if remote and backup_dir.exists():
                shutil.rmtree(backup_dir)
            marker.unlink()
            return (None if remote else backup_dir), moved_files
        except Exception:
            # O marcador permanece para que o reset possa ser retomado no próximo início.
            raise

    def _assert_financial_state_can_be_reset(self):
        database = self.base_dir / "db/terminal.db"
        if not database.exists() or database.stat().st_size == 0:
            return
        try:
            with sqlite3.connect(str(database), timeout=5) as connection:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()
                if integrity is None or str(integrity[0]).lower() != "ok":
                    raise ResetBlockedCriticalState(
                        "SQLite reprovado; reset bloqueado para preservar recovery"
                    )
                table = connection.execute(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type='table' AND name='active_payment'"
                ).fetchone()
                if table and connection.execute(
                    "SELECT 1 FROM active_payment LIMIT 1"
                ).fetchone():
                    raise ResetBlockedActivePayment(
                        "Existe pagamento ativo ou incerto no armazenamento local"
                    )
        except (ResetBlockedActivePayment, ResetBlockedCriticalState):
            raise
        except (OSError, sqlite3.DatabaseError) as error:
            raise ResetBlockedCriticalState(
                "Estado financeiro local nao pode ser verificado"
            ) from error

    def pending_completion(self):
        marker = self.base_dir / self.COMPLETION_MARKER
        if not marker.exists():
            return None
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        return data if isinstance(data, dict) and data.get("terminalId") else None

    def acknowledge_completion(self):
        marker = self.base_dir / self.COMPLETION_MARKER
        if marker.exists():
            marker.unlink()
        self.credential_store.remove()

    def _read_request(self, marker):
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError, TypeError):
            # Compatibilidade com o marcador v1: o reset continua local e recuperável.
            return {}

    def _reset_directory(self, reset_id, remote):
        if remote:
            directory = self.base_dir / "db/reset-staging" / reset_id
            directory.mkdir(parents=True, exist_ok=True)
            return directory
        return self._new_backup_dir()

    def _atomic_json_write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(data), encoding="utf-8")
        temporary.replace(path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    def _new_backup_dir(self):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_dir = self.base_dir / "db/reset-backups" / timestamp
        backup_dir.mkdir(parents=True, exist_ok=False)
        return backup_dir
