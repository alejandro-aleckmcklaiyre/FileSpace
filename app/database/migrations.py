"""Versioned, transactional schema initialization."""

from pathlib import Path

from app.database.connection import connect


def migrate(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version > 1:
            raise ValueError("This database was created by a newer FileSpace version.")
        if version == 0:
            statements = (
                """CREATE TABLE quick_sort_shortcuts (
                    id INTEGER PRIMARY KEY, keyword TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    name TEXT NOT NULL, destination_path TEXT NOT NULL,
                    icon TEXT, color TEXT, position INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))""",
                """CREATE TABLE operation_history (
                    id INTEGER PRIMARY KEY, operation_type TEXT NOT NULL DEFAULT 'move',
                    destination_path TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))""",
                """CREATE TABLE operation_items (
                    id INTEGER PRIMARY KEY, operation_id INTEGER NOT NULL REFERENCES operation_history(id),
                    source_path TEXT NOT NULL, destination_path TEXT NOT NULL,
                    status TEXT NOT NULL, message TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))""",
            )
            for statement in statements:
                db.execute(statement)
            db.execute("PRAGMA user_version = 1")
