"""Isola estado persistente para nenhum teste tocar os dados da instalação."""

import os
import tempfile
from pathlib import Path


_runtime = tempfile.TemporaryDirectory(prefix="app247-tests-")
_data_dir = Path(_runtime.name)

os.environ["APP247_ENV"] = "test"
os.environ["APP247_DATA_DIR"] = str(_data_dir)
os.environ["APP247_DB_PATH"] = str(_data_dir / "terminal.db")
os.environ["APP247_TERMINAL_CONFIG_PATH"] = str(_data_dir / "terminal.json")
os.environ["APP247_DEVICE_CREDENTIAL_PATH"] = str(_data_dir / "device-credential")
os.environ["APP247_DISPLAY_ORIENTATION_PATH"] = str(_data_dir / "display_orientation")
os.environ["APP247_LAST_SYNC_PATH"] = str(_data_dir / "last_sync.txt")
# O instalador grava política do NetworkManager; testes nunca tocam /etc.
os.environ["APP247_NM_CONF_DIR"] = str(_data_dir / "NetworkManager/conf.d")
os.environ["APP247_ICON_DESTINATION"] = str(_data_dir / "pixmaps/app247-terminal.png")


import pytest


@pytest.fixture(autouse=True)
def _reset_shutdown_budget():
    """O prazo de encerramento é global ao processo; cada teste começa sem ele."""
    from app247_terminal.services import shutdown_budget

    shutdown_budget.reset_for_tests()
    yield
    shutdown_budget.reset_for_tests()


def pytest_sessionfinish(session, exitstatus):
    _runtime.cleanup()
