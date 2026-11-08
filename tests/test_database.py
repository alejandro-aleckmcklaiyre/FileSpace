"""Persistence and transfer journal tests using isolated SQLite databases."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from app.database.connection import connect
from app.database.repository import Repository
from app.filesystem.safety import SafetyPolicy
from app.services.quick_sort_service import QuickSortService


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.destination = self.root / "destination"
        self.destination.mkdir()
        self.repo = Repository(self.root / "state" / "filespace.sqlite3")
        self.repo.initialize()
        self.service = QuickSortService(self.repo, SafetyPolicy([self.repo.path.parent]))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_shortcuts_persist_edit_reorder_delete_and_unique_keyword(self) -> None:
        self.service.save("A", "Photos", str(self.destination))
        self.service.save("B", "Work", str(self.destination))
        restarted = Repository(self.repo.path)
        restarted.initialize()
        first, second = restarted.shortcuts()
        self.assertEqual(first["name"], "Photos")
        self.assertTrue(first["created_at"])
        with self.assertRaises(sqlite3.IntegrityError):
            self.service.save("a", "Duplicate", str(self.destination))
        self.service.save("C", "Renamed", str(self.destination), first["id"])
        restarted.reorder(second["id"], -1)
        self.assertEqual([row["keyword"] for row in restarted.shortcuts()], ["B", "C"])
        restarted.delete_shortcut(first["id"])
        self.assertEqual(len(self.repo.shortcuts()), 1)
        self.assertTrue(self.destination.is_dir())
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_invalid_destinations_and_empty_fields_rejected(self) -> None:
        with self.assertRaises((OSError, ValueError)):
            self.service.save("A", "Bad", str(self.root / "missing"))
        with self.assertRaises(ValueError):
            self.service.save("A", "Protected", str(self.repo.path.parent))
        with self.assertRaises(ValueError):
            self.service.save("", "", str(self.destination))
        self.assertEqual(self.repo.shortcuts(), [])

    def test_history_tracks_every_file_after_restart(self) -> None:
        files = [self.root / "first.txt", self.root / "second.txt"]
        for file in files:
            file.write_bytes(b"temporary fixture")
        plan = self.service.plan([str(file) for file in files], str(self.destination))
        results = self.service.move(plan, ["move", "skip"], Event(), lambda message: None)
        self.assertEqual([item.status for item in results], ["moved", "skipped"])
        history = Repository(self.repo.path).history()
        self.assertEqual(len(history), 2)
        self.assertEqual({item["status"] for item in history}, {"moved", "skipped"})
        self.assertTrue(all(item["operation_status"] == "completed" for item in history))
        self.assertTrue(all(item["source_path"] and item["destination_path"] and item["created_at"] for item in history))

    def test_journal_failure_before_transfer_preserves_original(self) -> None:
        source = self.root / "source.txt"
        source.write_bytes(b"safe")
        plan = self.service.plan([str(source)], str(self.destination))
        with patch.object(self.repo, "start_operation", side_effect=sqlite3.OperationalError("Disk full")):
            with self.assertRaises(sqlite3.OperationalError):
                self.service.move(plan, ["move"], Event(), lambda message: None)
        self.assertTrue(source.exists())
        self.assertFalse(list(self.destination.iterdir()))

    def test_journal_failure_after_first_file_stops_next_file(self) -> None:
        first, second = self.root / "one.txt", self.root / "two.txt"
        first.write_bytes(b"one")
        second.write_bytes(b"two")
        plan = self.service.plan([str(first), str(second)], str(self.destination))
        with patch.object(self.repo, "record_item", side_effect=sqlite3.OperationalError("Journal unavailable")):
            with self.assertRaisesRegex(RuntimeError, "Inspect both paths"):
                self.service.move(plan, ["move", "move"], Event(), lambda message: None)
        self.assertTrue((self.destination / first.name).exists())
        self.assertTrue(second.exists())
        self.assertTrue(all(row["operation_status"] == "needs_review" for row in self.repo.history()))

    def test_newer_database_is_not_modified(self) -> None:
        with connect(self.repo.path) as db:
            db.execute("PRAGMA user_version = 2")
        with self.assertRaises(ValueError):
            self.repo.initialize()
        with connect(self.repo.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)

    def test_final_journal_failure_reports_that_files_already_moved(self) -> None:
        source = self.root / "done.txt"
        source.write_bytes(b"done")
        plan = self.service.plan([str(source)], str(self.destination))
        with patch.object(self.repo, "finish_operation", side_effect=sqlite3.OperationalError("Disk full")):
            with self.assertRaisesRegex(RuntimeError, "Transfers have finished"):
                self.service.move(plan, ["move"], Event(), lambda message: None)
        self.assertFalse(source.exists())
        self.assertEqual((self.destination / source.name).read_bytes(), b"done")
        self.assertEqual(self.repo.history()[0]["status"], "moved")


if __name__ == "__main__":
    unittest.main()
