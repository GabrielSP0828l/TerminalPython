"""Validação de versão sem duplicar a versão atual da aplicação."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering

from app247_terminal.version import APP_VERSION

_VERSION_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z.-]+))?$"
)


@total_ordering
@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    prerelease: str = ""

    @classmethod
    def parse(cls, value: str) -> "Version":
        match = _VERSION_PATTERN.fullmatch(str(value).strip())
        if not match:
            raise ValueError(f"Versão inválida: {value!r}")
        return cls(
            int(match.group(1)), int(match.group(2)), int(match.group(3)),
            match.group(4) or "",
        )

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        return f"{base}-{self.prerelease}" if self.prerelease else base

    def __lt__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        own_core = (self.major, self.minor, self.patch)
        other_core = (other.major, other.minor, other.patch)
        if own_core != other_core:
            return own_core < other_core
        if not self.prerelease:
            return False
        if not other.prerelease:
            return True
        return self.prerelease < other.prerelease


CURRENT_VERSION = Version.parse(APP_VERSION)
