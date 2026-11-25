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
    LEGACY_LAYOUT_MARKER_PATH,
    RESET_BACKUP_DIR,
    RESET_STAGING_DIR,
    SOURCE_ROOT,
    TERMINAL_CONFIG_PATH,
)

logger = logging.getLogger(__name__)


def prepare_runtime_layout() -> list[tuple[Path, Path]]:
    """Copia estado legado uma única vez e só quando o novo destino não existe.

    Destino ausente depois da migração significa factory reset: copiar de novo
    ressuscitaria a identidade e a credencial que o reset removeu.
    """
    migrations = (
        (SOURCE_ROOT / "db" / "terminal.db", DATABASE_PATH),
        (SOURCE_ROOT / "db" / "terminal.json", TERMINAL_CONFIG_PATH),
        (SOURCE_ROOT / "db" / "device-credential", DEVICE_CREDENTIAL_PATH),
        (SOURCE_ROOT / "db" / "display_orientation", DISPLAY_ORIENTATION_PATH),
        (SOURCE_ROOT / "database" / "last_sync.txt", LAST_SYNC_PATH),
    )
    # Instalações anteriores ao marcador: diretório de reset prova que a
    # migração já ocorreu e que os destinos ausentes foram removidos de propósito.
    migrate = not (
        LEGACY_LAYOUT_MARKER_PATH.exists()
        or RESET_BACKUP_DIR.exists()
        or RESET_STAGING_DIR.exists()
    )
    copied = []
    for source, destination in migrations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if migrate and source.is_file() and not destination.exists() and source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
            copied.append((source, destination))
            logger.info("[RUNTIME] estado legado copiado source=%s target=%s", source, destination)
    LEGACY_LAYOUT_MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEGACY_LAYOUT_MARKER_PATH.touch()
    return copied
