from dataclasses import dataclass
import json
from pathlib import Path


@dataclass
class Terminal:
    terminalId: int
    uuidTerminal: str
    serialNumber: str
    nome: str
    codigo: str
    status: str
    ativo: bool
    activated: bool
    condominioId: int
    condominioNome: str

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            terminalId=data.get("terminalId"),
            uuidTerminal=data.get("uuidTerminal"),
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

    def save(self, path="db/terminal.json"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                self.to_dict(),
                f,
                indent=4,
                ensure_ascii=False
            )

    @classmethod
    def is_activated(cls, path="db/terminal.json"):
        return Path(path).exists()

    @classmethod
    def load(cls, path="db/terminal.json"):
        if not Path(path).exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))