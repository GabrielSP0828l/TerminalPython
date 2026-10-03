"""Resolução de recursos para desenvolvimento, systemd e PyInstaller."""

from pathlib import Path

from app247_terminal.config.settings import BUNDLE_ROOT


def resource_path(*parts: str) -> Path:
    path = BUNDLE_ROOT.joinpath(*parts).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Recurso da aplicação não encontrado: {path}")
    return path


def image_path(filename: str) -> Path:
    return resource_path("assets", "images", filename)


def icon_path(filename: str) -> Path:
    return resource_path("assets", "icons", filename)
