import json
import shutil
from datetime import datetime
from pathlib import Path

from config import PROJECT_ROOT


class FactoryResetService:
    RESET_MARKER = Path("db/factory-reset.pending")
    LOCAL_STATE_FILES = (
        Path("db/terminal.json"),
        Path("db/terminal.db"),
        Path("database/last_sync.txt"),
        Path("temp_checkout.png"),
    )

    def __init__(self, base_dir=PROJECT_ROOT):
        self.base_dir = Path(base_dir)

    def request_reset(self):
        marker = self.base_dir / self.RESET_MARKER
        marker.parent.mkdir(parents=True, exist_ok=True)
        temporary_marker = marker.with_suffix(".tmp")
        temporary_marker.write_text(
            json.dumps({
                "requestedAt": datetime.now().isoformat(),
                "version": 1
            }),
            encoding="utf-8"
        )
        temporary_marker.replace(marker)

    def apply_pending(self):
        marker = self.base_dir / self.RESET_MARKER
        if not marker.exists():
            return None

        backup_dir = self._new_backup_dir()
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

            marker.unlink()
            return backup_dir, moved_files
        except Exception:
            # O marcador permanece para que o reset possa ser retomado no próximo início.
            raise

    def _new_backup_dir(self):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_dir = self.base_dir / "db/reset-backups" / timestamp
        backup_dir.mkdir(parents=True, exist_ok=False)
        return backup_dir
