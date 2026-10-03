"""Prepara diretórios persistentes e migra o layout legado sem apagá-lo."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app247_terminal.config.settings import (
    DATABASE_PATH,
    DEVICE_CREDENTIAL_PATH,
    DISPLAY_ORIENTATION_PATH,
    LAST_SYNC_PATH,
    SOURCE_ROOT,
    TERMINAL_CONFIG_PATH,
)

logger = logging.getLogger(__name__)


def prepare_runtime_layout() -> list[tuple[Path, Path]]:
    """Copia estado legado somente quando o novo destino ainda não existe."""
    migrations = (
        (SOURCE_ROOT / "db" / "terminal.db", DATABASE_PATH),
        (SOURCE_ROOT / "db" / "terminal.json", TERMINAL_CONFIG_PATH),
        (SOURCE_ROOT / "db" / "device-credential", DEVICE_CREDENTIAL_PATH),
        (SOURCE_ROOT / "db" / "display_orientation", DISPLAY_ORIENTATION_PATH),
        (SOURCE_ROOT / "database" / "last_sync.txt", LAST_SYNC_PATH),
    )
    copied = []
    for source, destination in migrations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_file() and not destination.exists() and source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
            copied.append((source, destination))
            logger.info("[RUNTIME] estado legado copiado source=%s target=%s", source, destination)
    return copied
