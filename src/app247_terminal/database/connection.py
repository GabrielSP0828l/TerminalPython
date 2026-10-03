"""Cria conexões SQLite com as mesmas garantias em todos os repositories."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def connect_sqlite(path, *, row_factory=False, timeout=5.0):
    database_path = Path(path).expanduser()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(os.fspath(database_path), timeout=timeout)
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA foreign_keys = ON")
    if row_factory:
        connection.row_factory = sqlite3.Row
    return connection
