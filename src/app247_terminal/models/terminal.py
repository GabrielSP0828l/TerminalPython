from dataclasses import dataclass
from datetime import datetime
import json
import logging
import os
from pathlib import Path
from typing import Optional

from app247_terminal.config.settings import TERMINAL_CONFIG_PATH


logger = logging.getLogger(__name__)


class TerminalConfigCorrupted(ValueError):
    """``terminal.json`` existe, mas não é uma identidade legível."""


@dataclass
class Terminal:
    terminalId: str
    uuidTerminal: str
    serialNumber: str
    nome: str
    codigo: str
    status: str
    ativo: bool
    activated: bool
    condominioId: Optional[str]
    condominioNome: str

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            raise TypeError("Dados do terminal devem ser um objeto")

        terminal_uuid = data.get("uuidTerminal") or data.get("terminalId")
        if terminal_uuid is None or not str(terminal_uuid).strip():
            raise ValueError("Resposta de ativação sem terminalId")

        terminal_uuid = str(terminal_uuid)
        return cls(
            terminalId=terminal_uuid,
            uuidTerminal=terminal_uuid,
            serialNumber=data.get("serialNumber"),
            nome=data.get("nome"),
            codigo=data.get("codigo"),
            status=data.get("status"),
            ativo=data.get("ativo"),
            activated=data.get("activated"),
            condominioId=data.get("condominioId"),
            condominioNome=data.get("condominioNome")
        )

    def to_dict(self):
        return {
            "terminalId": self.terminalId,
            "uuidTerminal": self.uuidTerminal,
            "serialNumber": self.serialNumber,
            "nome": self.nome,
            "codigo": self.codigo,
            "status": self.status,
            "ativo": self.ativo,
            "activated": self.activated,
            "condominioId": self.condominioId,
            "condominioNome": self.condominioNome
        }

    def save(self, path=TERMINAL_CONFIG_PATH):
        terminal_path = Path(path)
        terminal_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = terminal_path.with_suffix(f"{terminal_path.suffix}.tmp")

        # Desligamentos sem poweroff são reais no Raspberry: o conteúdo precisa
        # estar no disco antes do rename, e o rename antes de retornar.
        with open(temporary_path, "w", encoding="utf-8") as f:
            json.dump(
                self.to_dict(),
                f,
                indent=4,
                ensure_ascii=False
            )
            f.flush()
            os.fsync(f.fileno())
        temporary_path.replace(terminal_path)
        try:
            os.chmod(terminal_path, 0o600)
        except OSError:
            # Plataformas sem semantica POSIX continuam usando escrita atomica.
            pass
        _fsync_directory(terminal_path.parent)

    @classmethod
    def is_activated(cls, path=TERMINAL_CONFIG_PATH):
        try:
            terminal = cls.load(path)
            return bool(terminal and terminal.activated and terminal.ativo)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return False

    @classmethod
    def load(cls, path=TERMINAL_CONFIG_PATH):
        if not Path(path).exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                return cls.from_dict(json.load(f))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise TerminalConfigCorrupted(
                f"Identidade local ilegível em {path}: {error}"
            ) from error

    @classmethod
    def load_or_none(cls, path=TERMINAL_CONFIG_PATH):
        """Leitura para threads e timers: arquivo ilegível nunca derruba o loop."""
        try:
            return cls.load(path)
        except (OSError, TerminalConfigCorrupted) as error:
            logger.error("[TERMINAL] identidade local indisponível: %s", error)
            return None

    @classmethod
    def quarantine_if_corrupted(cls, path=TERMINAL_CONFIG_PATH):
        """Preserva um ``terminal.json`` ilegível e devolve o caminho do backup.

        A identidade é dado do backend: sem o arquivo, o Terminal volta à
        consulta por serial (ou à recuperação de pagamento pendente). O conteúdo
        original nunca é apagado.
        """
        terminal_path = Path(path)
        try:
            cls.load(terminal_path)
            return None
        except TerminalConfigCorrupted:
            pass
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup = terminal_path.with_name(f"{terminal_path.name}.corrupt-{stamp}")
        counter = 1
        while backup.exists():
            backup = terminal_path.with_name(
                f"{terminal_path.name}.corrupt-{stamp}-{counter}"
            )
            counter += 1
        terminal_path.replace(backup)
        _fsync_directory(terminal_path.parent)
        logger.error(
            "[TERMINAL] terminal.json ilegível preservado em %s; "
            "identidade será recuperada pelo backend", backup,
        )
        return backup


def _fsync_directory(directory):
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)
