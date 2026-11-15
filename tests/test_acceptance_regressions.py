"""Regressions from owner acceptance, using only disposable fixture paths."""

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.filesystem import file_operations as operations
from app.filesystem import streams
from app.filesystem.cleanup import remove_file, retry_locked, set_readonly
from app.filesystem.safety import SafetyPolicy
from app.platform_shell import select_in_explorer


class AcceptanceTransferTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "source.txt"
        self.source.write_bytes(b"verified data")
        self.folder = self.root / "target"
        self.folder.mkdir()
        self.target = self.folder / self.source.name
        self.policy = SafetyPolicy([])

    def tearDown(self):
        for path in self.root.rglob("*"):
            if path.is_file():
                set_readonly(path, False)
        self.temporary.cleanup()

    def transfer(self, operation="move", action=None):
        plan = operations.build_plan([str(self.source)], str(self.folder), self.policy, operation)
        return operations.transfer_file(plan, plan.items[0], action or operation, self.policy)

    def test_readonly_move_removes_original_and_preserves_destination_attribute(self):
        set_readonly(self.source, True)
        result = self.transfer()
        self.assertEqual(result.status, "moved", result.message)
        self.assertFalse(self.source.exists())
        self.assertEqual(self.target.read_bytes(), b"verified data")
        self.assertFalse(self.target.stat().st_mode & stat.S_IWRITE)
        self.assertEqual(list(self.folder.glob(".filespace-*")), [])

    def test_readonly_replace_removes_backup_and_retains_source_readonly(self):
        self.target.write_bytes(b"previous")
        set_readonly(self.target, True)
        set_readonly(self.source, True)
        result = self.transfer("copy", "replace")
        self.assertEqual(result.status, "copied", result.message)
        self.assertFalse(self.target.stat().st_mode & stat.S_IWRITE)
        self.assertFalse(self.source.stat().st_mode & stat.S_IWRITE)
        self.assertEqual(self.target.read_bytes(), self.source.read_bytes())
        self.assertEqual(list(self.folder.glob(".filespace-*")), [])

    def test_failed_readonly_move_restores_source_attribute_and_clear_status(self):
        set_readonly(self.source, True)
        unlink = Path.unlink
        def denied(path, *args, **kwargs):
            if path == self.source:
                raise PermissionError("ACL refuses deletion")
            return unlink(path, *args, **kwargs)
        with patch.object(Path, "unlink", denied):
            result = self.transfer()
        self.assertEqual(result.status, "copied_original_retained")
        self.assertFalse(self.source.stat().st_mode & stat.S_IWRITE)
        self.assertIn(str(self.source), result.message)
        self.assertEqual(self.target.read_bytes(), self.source.read_bytes())

    def test_readonly_rollback_preserves_previous_destination_and_attributes(self):
        self.target.write_bytes(b"previous")
        set_readonly(self.target, True)
        publish = operations.publish_no_replace
        def denied(source, target):
            if source.suffix == ".partial":
                raise PermissionError("Publication refused")
            publish(source, target)
        with patch.object(operations, "publish_no_replace", side_effect=denied):
            result = self.transfer("copy", "replace")
        self.assertEqual(result.status, "failed")
        self.assertEqual(self.target.read_bytes(), b"previous")
        self.assertFalse(self.target.stat().st_mode & stat.S_IWRITE)
        self.assertEqual(list(self.folder.glob(".filespace-*")), [])

    def test_readonly_owned_staging_cleanup(self):
        stage = self.folder / ".filespace-fixture.partial"
        stage.write_bytes(b"staged")
        set_readonly(stage, True)
        remove_file(stage)
        self.assertFalse(stage.exists())

    def test_changed_file_cannot_be_removed(self):
        expected = operations.fingerprint(self.source)
        self.source.write_bytes(b"changed data after validation")
        with self.assertRaises(ValueError):
            remove_file(self.source, expected)
        self.assertTrue(self.source.exists())

    def test_backup_cleanup_failure_has_verified_copy_status_and_recovery_path(self):
        self.target.write_bytes(b"previous")
        remove = operations.remove_file
        def denied(path, *args):
            if path.suffix == ".backup":
                raise PermissionError("Locked backup")
            remove(path, *args)
        with patch.object(operations, "remove_file", side_effect=denied):
            result = self.transfer("copy", "replace")
        self.assertEqual(result.status, "cleanup_warning")
        backup, = self.folder.glob(".filespace-*.backup")
        self.assertEqual(backup.read_bytes(), b"previous")
        self.assertIn(str(backup), result.message)

    def test_zero_byte_copy_and_replace(self):
        self.source.write_bytes(b"")
        self.assertEqual(self.transfer("copy").status, "copied")
        self.assertEqual(self.transfer("copy", "replace").status, "copied")
        self.assertEqual(self.target.stat().st_size, 0)
        self.assertEqual(list(self.folder.glob(".filespace-*")), [])

    def test_move_backup_warning_does_not_claim_original_was_retained(self):
        self.target.write_bytes(b"previous")
        remove = operations.remove_file
        def denied(path, *args):
            if path.suffix == ".backup":
                raise PermissionError("Locked backup")
            remove(path, *args)
        with patch.object(operations, "remove_file", side_effect=denied):
            result = self.transfer("move", "replace")
        self.assertEqual(result.status, "moved_cleanup_warning")
        self.assertFalse(self.source.exists())
        self.assertEqual(self.target.read_bytes(), b"verified data")

    @unittest.skipUnless(os.name == "nt", "Windows volume capability")
    def test_plain_copy_to_simulated_volume_without_named_streams(self):
        supports = streams.supports_named_streams
        with patch.object(streams, "supports_named_streams", side_effect=lambda path: False if self.folder in path.parents or path == self.folder else supports(path)):
            result = self.transfer("copy")
        self.assertEqual(result.status, "copied", result.message)
        self.assertEqual(self.target.read_bytes(), self.source.read_bytes())

    @unittest.skipUnless(os.name == "nt", "Windows named streams")
    def test_metadata_loss_is_refused_before_staging(self):
        Path(str(self.source) + ":Zone.Identifier").write_bytes(b"ZoneId=3")
        with patch.object(operations, "supports_named_streams", return_value=False):
            result = self.transfer()
        self.assertEqual(result.status, "failed")
        self.assertIn("does not support", result.message)
        self.assertTrue(self.source.exists())
        self.assertEqual(list(self.folder.iterdir()), [])

    @unittest.skipUnless(os.name == "nt", "Windows volume capability")
    def test_volume_query_failure_is_not_treated_as_no_streams(self):
        with patch.object(streams, "supports_named_streams", side_effect=PermissionError("Volume unavailable")):
            with self.assertRaises(PermissionError):
                streams.named_streams(self.source)

    def test_transient_sharing_lock_retries_rename_without_overwrite(self):
        error = PermissionError("Sharing violation")
        error.winerror = 32
        rename = os.rename
        attempts = []
        def transient(source, target):
            attempts.append(source)
            if len(attempts) < 3:
                raise error
            rename(source, target)
        with patch.object(operations.os, "rename", side_effect=transient), patch("app.filesystem.cleanup.time.sleep"):
            operations.publish_no_replace(self.source, self.target)
        self.assertEqual(len(attempts), 3)
        self.assertTrue(self.target.exists())

    def test_permanent_denial_not_retried(self):
        error = PermissionError("ACL denies access")
        error.winerror = 5
        with patch("app.filesystem.cleanup.time.sleep") as sleep:
            with self.assertRaises(PermissionError):
                retry_locked(lambda: (_ for _ in ()).throw(error))
        sleep.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Explorer command")
    def test_explorer_selection_uses_argument_list_with_spaces_and_special_characters(self):
        path = self.root / "a folder" / "test & photo.jpg"
        with patch("app.platform_shell.subprocess.Popen") as launch:
            select_in_explorer(path)
        args = launch.call_args.args[0]
        self.assertEqual(args[1:], ["/select,", str(path)])
        self.assertNotIn("shell", launch.call_args.kwargs)
