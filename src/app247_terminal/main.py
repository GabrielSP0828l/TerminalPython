import logging
import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from app247_terminal.application import MainWindow, present_main_window
from app247_terminal.config.settings import API_URL, DATABASE_PATH
from app247_terminal.models.terminal import Terminal
from app247_terminal.runtime import prepare_runtime_layout
from app247_terminal.services.display_service import DisplayService
from app247_terminal.services.terminal_auth import install_credential_from_stdin
from app247_terminal.version import APP_VERSION
from app247_terminal.utils.resources import icon_path, image_path


def run() -> int:
    if "--install-device-credential" in sys.argv[1:]:
        install_credential_from_stdin()
        print("Credencial individual instalada com segurança.")
        return 0
    if "--version" in sys.argv[1:]:
        print(APP_VERSION)
        return 0
    if "--check" in sys.argv[1:]:
        image_path("logo.png")
        icon_path("checked.svg")
        print(f"app247-terminal {APP_VERSION}: configuração e assets OK")
        return 0
    if "--apply-display" in sys.argv[1:]:
        orientation = os.getenv("DISPLAY_ORIENTATION", "").strip()
        service = DisplayService()
        if orientation:
            service.apply_orientation(orientation, persist=False)
        else:
            service.apply_saved()
        return 0
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    prepare_runtime_layout()
    logger = logging.getLogger(__name__)
    logger.info("[API] Backend: %s", API_URL or "não configurado")
    logger.info("[SYNC] SQLite path: %s", DATABASE_PATH.resolve())
    terminal = Terminal.load()
    if terminal is not None:
        logger.info("[TERMINAL] UUID carregado: %s", terminal.terminalId)

    app = QApplication(sys.argv)
    window = MainWindow()
    app.setOverrideCursor(Qt.BlankCursor)
    present_main_window(window)
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(run())
