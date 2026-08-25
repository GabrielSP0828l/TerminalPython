from dataclasses import dataclass
import json
from pathlib import Path
from typing import Optional

from config import TERMINAL_CONFIG_PATH


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

        with open(temporary_path, "w", encoding="utf-8") as f:
            json.dump(
                self.to_dict(),
                f,
                indent=4,
                ensure_ascii=False
            )
        temporary_path.replace(terminal_path)

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

        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
