"""Data-integrity tests: all transfers use disposable test-owned files."""

import os
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from app.filesystem import file_operations as operations
from app.filesystem.safety import SafetyPolicy


class FileOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "source"
        self.destination = self.root / "destination"
        self.source.mkdir()
        self.destination.mkdir()
        self.file = self.source / "photo.txt"
        self.file.write_bytes(b"original data" * 100)
        self.policy = SafetyPolicy([])

    def tearDown(self) -> None:
        self.temp.cleanup()

    def plan(self):
        return operations.build_plan([str(self.file)], str(self.destination), self.policy)

    def test_verified_move_removes_original_only_after_copy(self) -> None:
        content = self.file.read_bytes()
        plan = self.plan()
        actual_digest = operations.digest
        checks = []
        def verifying(path):
            checks.append(path)
            self.assertTrue(self.file.exists())
            return actual_digest(path)
        with patch.object(operations, "digest", side_effect=verifying):
            result = operations.move_file(plan, plan.items[0], "move", self.policy)
        self.assertEqual(result.status, "moved")
        self.assertFalse(self.file.exists())
        self.assertEqual((self.destination / self.file.name).read_bytes(), content)
        self.assertGreaterEqual(len(checks), 4)
        self.assertFalse(list(self.destination.glob(".filespace-*")))

    def test_conflict_skip_rename_replace(self) -> None:
        target = self.destination / self.file.name
        target.write_bytes(b"existing")
        plan = self.plan()
        result = operations.move_file(plan, plan.items[0], "skip", self.policy)
        self.assertEqual(result.status, "skipped")
        self.assertTrue(self.file.exists())
        self.assertEqual(target.read_bytes(), b"existing")
        result = operations.move_file(plan, plan.items[0], "move", self.policy)
        self.assertEqual(result.status, "failed")
        result = operations.move_file(plan, plan.items[0], "rename", self.policy)
        self.assertEqual(result.status, "moved")
        self.assertEqual(Path(result.destination).suffix, ".txt")
        self.assertEqual(target.read_bytes(), b"existing")
        self.file.write_bytes(b"replacement")
        plan = self.plan()
        result = operations.move_file(plan, plan.items[0], "replace", self.policy)
        self.assertEqual(result.status, "moved", result.message)
        self.assertEqual(target.read_bytes(), b"replacement")
        self.assertFalse(list(self.destination.glob(".filespace-*")))

    def test_verification_failure_preserves_source_and_existing_destination(self) -> None:
        target = self.destination / self.file.name
        target.write_bytes(b"old contents")
        plan = self.plan()
        with patch.object(operations, "digest", return_value=b"wrong digest"):
            result = operations.move_file(plan, plan.items[0], "replace", self.policy)
        self.assertEqual(result.status, "failed")
        self.assertTrue(self.file.exists())
        self.assertEqual(target.read_bytes(), b"old contents")
        self.assertFalse(list(self.destination.glob(".filespace-*")))

    def test_changed_source_conflict_and_new_conflict_are_rejected(self) -> None:
        plan = self.plan()
        self.file.write_bytes(b"changed")
        self.assertEqual(operations.move_file(plan, plan.items[0], "move", self.policy).status, "failed")
        plan = self.plan()
        target = self.destination / self.file.name
        target.write_bytes(b"new collision")
        self.assertEqual(operations.move_file(plan, plan.items[0], "move", self.policy).status, "failed")
        plan = self.plan()
        target.write_bytes(b"changed collision")
        self.assertEqual(operations.move_file(plan, plan.items[0], "replace", self.policy).status, "failed")
        self.assertTrue(self.file.exists())
        self.assertEqual(target.read_bytes(), b"changed collision")

    def test_full_disk_or_copy_error_preserves_original(self) -> None:
        plan = self.plan()
        with patch.object(operations.os, "fsync", side_effect=OSError("Disk full")):
            result = operations.move_file(plan, plan.items[0], "move", self.policy)
        self.assertEqual(result.status, "failed")
        self.assertTrue(self.file.exists())
        self.assertFalse(list(self.destination.iterdir()))

    def test_destination_race_never_overwrites_new_file(self) -> None:
        plan = self.plan()
        publish = operations.publish_no_replace
        def race(source, target):
            target.write_bytes(b"arrived later")
            publish(source, target)
        with patch.object(operations, "publish_no_replace", side_effect=race):
            result = operations.move_file(plan, plan.items[0], "move", self.policy)
        self.assertEqual(result.status, "failed")
        self.assertTrue(self.file.exists())
        self.assertEqual((self.destination / self.file.name).read_bytes(), b"arrived later")

    def test_replace_publish_failure_restores_previous_destination(self) -> None:
        target = self.destination / self.file.name
        target.write_bytes(b"old")
        plan = self.plan()
        publish = operations.publish_no_replace
        def failure(source, destination):
            if source.suffix == ".partial":
                raise PermissionError("Cannot publish")
            publish(source, destination)
        with patch.object(operations, "publish_no_replace", side_effect=failure):
            result = operations.move_file(plan, plan.items[0], "replace", self.policy)
        self.assertEqual(result.status, "failed")
        self.assertTrue(self.file.exists())
        self.assertEqual(target.read_bytes(), b"old")

    def test_source_removal_failure_preserves_both_copies_and_backup(self) -> None:
        target = self.destination / self.file.name
        target.write_bytes(b"old")
        plan = self.plan()
        unlink = Path.unlink
        def locked(path, *args, **kwargs):
            if path == self.file:
                raise PermissionError("File locked")
            return unlink(path, *args, **kwargs)
        with patch.object(Path, "unlink", locked):
            result = operations.move_file(plan, plan.items[0], "replace", self.policy)
        self.assertEqual(result.status, "needs_review")
        self.assertTrue(self.file.exists())
        self.assertEqual(target.read_bytes(), self.file.read_bytes())
        backups = list(self.destination.glob("*.backup"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), b"old")
        self.assertIn(str(backups[0]), result.message)

    def test_cancel_between_files_and_partial_failure(self) -> None:
        second = self.source / "second.txt"
        second.write_bytes(b"second")
        plan = operations.build_plan([str(self.file), str(second)], str(self.destination), self.policy)
        cancel = Event()
        recorded = []
        def record(index, result):
            recorded.append(result)
            cancel.set()
        results = operations.execute_plan(plan, ["move", "move"], self.policy, cancel, record, lambda message: None)
        self.assertEqual([result.status for result in results], ["moved", "cancelled"])
        self.assertTrue(second.exists())
        # A missing source fails independently; the next valid source proceeds.
        third = self.source / "third.txt"
        third.write_bytes(b"third")
        plan = operations.build_plan([str(second), str(third)], str(self.destination), self.policy)
        second.unlink()
        results = operations.execute_plan(plan, ["move", "move"], self.policy, Event(), lambda i, r: None, lambda m: None)
        self.assertEqual([result.status for result in results], ["failed", "moved"])

    def test_protected_same_folder_and_directory_sources_rejected(self) -> None:
        with self.assertRaises(ValueError):
            operations.build_plan([str(self.file)], str(self.source), self.policy)
        with self.assertRaises(ValueError):
            operations.build_plan([str(self.source)], str(self.destination), self.policy)
        for roots in ([self.source], [self.destination]):
            with self.assertRaises(ValueError):
                operations.build_plan([str(self.file)], str(self.destination), SafetyPolicy(roots))
        with self.assertRaises(OSError):
            operations.build_plan([str(self.file)], str(self.root / "missing"), self.policy)

    def test_destination_identity_change_rejected(self) -> None:
        plan = self.plan()
        self.destination.rename(self.root / "old_destination")
        self.destination.mkdir()
        result = operations.move_file(plan, plan.items[0], "move", self.policy)
        self.assertEqual(result.status, "failed")
        self.assertTrue(self.file.exists())

    @unittest.skipUnless(os.name == "nt", "NTFS alternate streams are Windows-specific")
    def test_alternate_data_streams_and_download_marker_are_preserved(self) -> None:
        data = {":Zone.Identifier:$DATA": b"[ZoneTransfer]\nZoneId=3", ":custom:$DATA": b"extra user data", ":empty:$DATA": b""}
        for suffix, content in data.items():
            with open(str(self.file) + suffix, "wb") as output:
                output.write(content)
        original = self.file.read_bytes()
        plan = self.plan()
        self.assertEqual(plan.total_size, len(original) + sum(len(content) for content in data.values()))
        result = operations.move_file(plan, plan.items[0], "move", self.policy)
        self.assertEqual(result.status, "moved", result.message)
        self.assertFalse(self.file.exists())
        target = Path(result.destination)
        self.assertEqual(target.read_bytes(), original)
        for suffix, content in data.items():
            with open(str(target) + suffix, "rb") as incoming:
                self.assertEqual(incoming.read(), content)

    @unittest.skipUnless(os.name == "nt", "NTFS alternate streams are Windows-specific")
    def test_stream_copy_failure_preserves_original_and_marker(self) -> None:
        suffix = ":Zone.Identifier:$DATA"
        with open(str(self.file) + suffix, "wb") as output:
            output.write(b"ZoneId=3")
        plan = self.plan()
        original_open = Path.open
        def unsupported(path, *args, **kwargs):
            if ".partial:" in str(path):
                raise OSError("Destination does not support named streams")
            return original_open(path, *args, **kwargs)
        with patch.object(Path, "open", unsupported):
            result = operations.move_file(plan, plan.items[0], "move", self.policy)
        self.assertEqual(result.status, "failed")
        self.assertIn("original kept", result.message)
        self.assertTrue(self.file.exists())
        with open(str(self.file) + suffix, "rb") as incoming:
            self.assertEqual(incoming.read(), b"ZoneId=3")
        self.assertFalse(list(self.destination.iterdir()))

    @unittest.skipUnless(os.name == "nt", "NTFS alternate streams are Windows-specific")
    def test_new_or_corrupted_stream_cannot_cause_source_deletion(self) -> None:
        plan = self.plan()
        suffix = ":Zone.Identifier:$DATA"
        with open(str(self.file) + suffix, "wb") as output:
            output.write(b"ZoneId=3")
        result = operations.move_file(plan, plan.items[0], "move", self.policy)
        self.assertEqual(result.status, "failed")
        plan = self.plan()
        original_digest = operations.digest
        def corrupted(path):
            if ".partial:" in str(path):
                return b"corrupt stream"
            return original_digest(path)
        with patch.object(operations, "digest", side_effect=corrupted):
            result = operations.move_file(plan, plan.items[0], "move", self.policy)
        self.assertEqual(result.status, "failed")
        self.assertTrue(self.file.exists())
        self.assertFalse(list(self.destination.iterdir()))

    @unittest.skipUnless(os.name == "nt", "NTFS alternate streams are Windows-specific")
    def test_rename_and_replace_preserve_incoming_streams(self) -> None:
        target = self.destination / self.file.name
        target.write_bytes(b"old destination")
        suffix = ":Zone.Identifier:$DATA"
        with open(str(self.file) + suffix, "wb") as output:
            output.write(b"incoming marker")
        with open(str(target) + suffix, "wb") as output:
            output.write(b"existing marker")
        plan = self.plan()
        result = operations.move_file(plan, plan.items[0], "rename", self.policy)
        self.assertEqual(result.status, "moved", result.message)
        with open(result.destination + suffix, "rb") as incoming:
            self.assertEqual(incoming.read(), b"incoming marker")
        with open(str(target) + suffix, "rb") as incoming:
            self.assertEqual(incoming.read(), b"existing marker")
        self.file.write_bytes(b"new replacement")
        with open(str(self.file) + suffix, "wb") as output:
            output.write(b"replacement marker")
        plan = self.plan()
        result = operations.move_file(plan, plan.items[0], "replace", self.policy)
        self.assertEqual(result.status, "moved", result.message)
        with open(str(target) + suffix, "rb") as incoming:
            self.assertEqual(incoming.read(), b"replacement marker")

    def test_final_verification_failure_keeps_source_and_replacement_backup(self) -> None:
        target = self.destination / self.file.name
        target.write_bytes(b"old destination")
        plan = self.plan()
        digest = operations.digest
        def final_failure(path):
            return b"wrong final digest" if path == target else digest(path)
        with patch.object(operations, "digest", side_effect=final_failure):
            result = operations.move_file(plan, plan.items[0], "replace", self.policy)
        self.assertEqual(result.status, "needs_review")
        self.assertTrue(self.file.exists())
        self.assertEqual(target.read_bytes(), self.file.read_bytes())
        self.assertEqual(list(self.destination.glob("*.backup"))[0].read_bytes(), b"old destination")

    def test_cancel_before_transfer_touches_no_files(self) -> None:
        plan = self.plan()
        cancel = Event()
        cancel.set()
        results = operations.execute_plan(plan, ["move"], self.policy, cancel, lambda i, r: None, lambda m: None)
        self.assertEqual(results[0].status, "cancelled")
        self.assertTrue(self.file.exists())
        self.assertFalse(list(self.destination.iterdir()))


if __name__ == "__main__":
    unittest.main()
