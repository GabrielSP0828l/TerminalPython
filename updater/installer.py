"""Primitivas de instalação segura em uma nova release.

Este módulo não para serviços e não troca o link ``current``. A ativação e
o health-check pertencem a um supervisor externo futuro, nunca ao processo que
está sendo substituído.
"""

from __future__ import annotations

import os
import tarfile
from dataclasses import dataclass
from pathlib import Path

from updater.version import Version


@dataclass(frozen=True)
class InstallLayout:
    root: Path = Path("/opt/app247")
    data: Path = Path("/var/lib/app247")
    config: Path = Path("/etc/app247")

    @property
    def releases(self) -> Path:
        return self.root / "releases"

    @property
    def current(self) -> Path:
        return self.root / "current"

    def release(self, version: str) -> Path:
        normalized = str(Version.parse(version))
        return self.releases / normalized


@dataclass(frozen=True)
class InstallPlan:
    version: str
    archive: Path
    release_dir: Path
    current_link: Path
    previous_target: Path | None


def build_install_plan(version: str, archive, layout=None) -> InstallPlan:
    layout = layout or InstallLayout()
    archive = Path(archive).resolve()
    previous = None
    if layout.current.is_symlink():
        previous = (layout.current.parent / os.readlink(layout.current)).resolve()
    return InstallPlan(
        version=str(Version.parse(version)),
        archive=archive,
        release_dir=layout.release(version),
        current_link=layout.current,
        previous_target=previous,
    )


def extract_new_release(plan: InstallPlan) -> Path:
    """Extrai somente em diretório inexistente e rejeita traversal/links."""
    if plan.release_dir.exists():
        raise FileExistsError(f"Release já existe: {plan.release_dir}")
    plan.release_dir.parent.mkdir(parents=True, exist_ok=True)
    plan.release_dir.mkdir(mode=0o755)
    try:
        with tarfile.open(plan.archive, "r:*") as package:
            root = plan.release_dir.resolve()
            for member in package.getmembers():
                target = (root / member.name).resolve()
                if root not in target.parents and target != root:
                    raise ValueError(f"Entrada fora da release: {member.name}")
                if member.issym() or member.islnk():
                    raise ValueError(f"Links não são permitidos no pacote: {member.name}")
            package.extractall(plan.release_dir, filter="data")
    except Exception:
        # Não removemos automaticamente uma extração parcial: ela fica fora
        # de ``current`` para inspeção/limpeza administrativa consciente.
        raise
    return plan.release_dir


def rollback_plan(layout=None) -> tuple[Path, Path | None]:
    """Informa link atual e release anterior registrada; não altera symlinks."""
    layout = layout or InstallLayout()
    marker = layout.data / "previous-release"
    previous = Path(marker.read_text(encoding="utf-8").strip()) if marker.is_file() else None
    return layout.current, previous
