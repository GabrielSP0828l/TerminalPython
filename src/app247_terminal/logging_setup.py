"""Configuração de logging: stderr (journal) e arquivo rotativo persistente.

O journald do Raspberry de campo é volátil (BUG-050), então o histórico só
sobrevive a um reboot se também for gravado em ``LOG_DIR``. O arquivo recebe as
mesmas linhas do journal; quem gera o log continua responsável por nunca
registrar token, credencial ou senha (AGENTS.md).
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
LOG_FILE_NAME = "terminal.log"


def configure_logging(
    log_dir: Path | None = None,
    max_bytes: int | None = None,
    backup_count: int | None = None,
) -> Path | None:
    """Liga stderr e, se possível, o arquivo rotativo; devolve o caminho do arquivo.

    Falha ao abrir o arquivo nunca impede a GUI de subir: o Terminal segue só
    com o journal e registra o motivo.
    """
    from app247_terminal.config import settings

    log_dir = Path(log_dir) if log_dir is not None else settings.LOG_DIR
    max_bytes = settings.LOG_MAX_BYTES if max_bytes is None else max_bytes
    backup_count = settings.LOG_BACKUP_COUNT if backup_count is None else backup_count

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)
    if not any(getattr(handler, "_app247_stream", False) for handler in root.handlers):
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(formatter)
        stream._app247_stream = True
        root.addHandler(stream)

    log_path = log_dir / LOG_FILE_NAME
    for handler in root.handlers:
        if getattr(handler, "_app247_file", None) == log_path:
            return log_path
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        if log_path.is_symlink():
            raise OSError(f"link simbólico não é permitido: {log_path}")
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
    except OSError as error:
        logging.getLogger(__name__).warning(
            "[LOG] arquivo persistente indisponível; somente journal dir=%s error=%s",
            log_dir, error,
        )
        return None
    file_handler.setFormatter(formatter)
    file_handler._app247_file = log_path
    root.addHandler(file_handler)
    return log_path
