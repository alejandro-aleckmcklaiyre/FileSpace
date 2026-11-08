"""Short-lived SQLite connections; never share connections between threads."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from PySide6.QtCore import QStandardPaths


def default_database_path() -> Path:
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / "filespace.sqlite3"


@contextmanager
def connect(path: Path):
    connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()
