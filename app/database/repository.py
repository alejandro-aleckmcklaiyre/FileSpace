"""Shortcut configuration and per-file transfer journal."""

from pathlib import Path

from app.database.connection import connect
from app.database.migrations import migrate


class Repository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        migrate(self.path)

    def shortcuts(self) -> list[dict]:
        with connect(self.path) as db:
            return [dict(row) for row in db.execute("SELECT * FROM quick_sort_shortcuts ORDER BY position, id")]

    def save_shortcut(self, keyword: str, name: str, destination: str, shortcut_id: int | None = None) -> None:
        keyword, name = keyword.strip(), name.strip()
        if not keyword or not name or len(keyword) > 20 or len(name) > 100:
            raise ValueError("Enter a keyword (1–20 characters) and name (1–100 characters).")
        with connect(self.path) as db:
            if shortcut_id is None:
                db.execute(
                    "INSERT INTO quick_sort_shortcuts(keyword,name,destination_path,position) VALUES(?,?,?,(SELECT COALESCE(MAX(position),-1)+1 FROM quick_sort_shortcuts))",
                    (keyword, name, destination),
                )
            else:
                db.execute("UPDATE quick_sort_shortcuts SET keyword=?,name=?,destination_path=? WHERE id=?", (keyword, name, destination, shortcut_id))

    def delete_shortcut(self, shortcut_id: int) -> None:
        with connect(self.path) as db:
            db.execute("DELETE FROM quick_sort_shortcuts WHERE id=?", (shortcut_id,))

    def reorder(self, shortcut_id: int, offset: int) -> None:
        with connect(self.path) as db:
            rows = list(db.execute("SELECT id FROM quick_sort_shortcuts ORDER BY position,id"))
            ids = [row[0] for row in rows]
            index = ids.index(shortcut_id)
            target = index + offset
            if 0 <= target < len(ids):
                ids[index], ids[target] = ids[target], ids[index]
                db.executemany("UPDATE quick_sort_shortcuts SET position=? WHERE id=?", enumerate(ids))

    def start_operation(self, destination: str, sources: list[str]) -> tuple[int, list[int]]:
        with connect(self.path) as db:
            operation = db.execute("INSERT INTO operation_history(destination_path,status) VALUES(?,'running')", (destination,)).lastrowid
            items = []
            for source in sources:
                items.append(db.execute(
                    "INSERT INTO operation_items(operation_id,source_path,destination_path,status) VALUES(?,?,?,'pending')",
                    (operation, source, str(Path(destination) / Path(source).name)),
                ).lastrowid)
            return operation, items

    def record_item(self, item: int, destination: str, status: str, message: str) -> None:
        with connect(self.path) as db:
            db.execute("UPDATE operation_items SET destination_path=?,status=?,message=? WHERE id=?", (destination, status, message, item))

    def finish_operation(self, operation: int, status: str) -> None:
        with connect(self.path) as db:
            db.execute("UPDATE operation_history SET status=? WHERE id=?", (status, operation))

    def history(self) -> list[dict]:
        with connect(self.path) as db:
            return [dict(row) for row in db.execute(
                "SELECT i.*,h.created_at AS operation_date,h.status AS operation_status FROM operation_items i JOIN operation_history h ON h.id=i.operation_id ORDER BY i.id DESC LIMIT 1000"
            )]
