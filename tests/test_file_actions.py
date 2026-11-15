"""Rename, recycle, clipboard and favorites checks with isolated files."""

import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from PySide6.QtCore import QMimeData, QThreadPool, QUrl
from PySide6.QtWidgets import QApplication, QDialog

from app.database.connection import connect
from app.database.repository import Repository
from app.filesystem.safety import SafetyPolicy
from app.services.file_action_service import FileActionService
from app.ui.main_window import MainWindow

APPLICATION = QApplication.instance() or QApplication([])


def wait_until(condition):
    deadline = time.monotonic() + 15
    while not condition():
        APPLICATION.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("Action timed out")
        time.sleep(0.01)
    APPLICATION.processEvents()


class MemoryClipboard:
    def __init__(self):
        self.clear()
    def clear(self):
        self.data = QMimeData()
    def mimeData(self):
        return self.data
    def setMimeData(self, data):
        self.data = data


class FileActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.file = self.root / "source.txt"
        self.file.write_bytes(b"original")
        self.repo = Repository(self.root / "state" / "test.sqlite3")
        self.repo.initialize()
        self.service = FileActionService(self.repo, SafetyPolicy([self.repo.path.parent]))

    def tearDown(self):
        self.temp.cleanup()

    def test_rename_preserves_extension_and_refuses_existing_names(self):
        plan = self.service.plan_rename(str(self.file), "new")
        results = self.service.execute(plan, Event(), lambda message: None)
        self.assertEqual(results[0].status, "renamed")
        target = self.root / "new.txt"
        self.assertEqual(target.read_bytes(), b"original")
        self.assertFalse(self.file.exists())
        self.file.write_bytes(b"different")
        with self.assertRaises(FileExistsError):
            self.service.plan_rename(str(self.file), "new")
        self.assertEqual(target.read_bytes(), b"original")
        self.assertEqual(self.repo.history()[0]["operation_type"], "rename")

    def test_invalid_names_protected_paths_and_changed_files_are_rejected(self):
        for stem in ("../escape", "CON", "bad:name", "", "space "):
            with self.assertRaises(ValueError):
                self.service.plan_rename(str(self.file), stem)
        plan = self.service.plan_rename(str(self.file), "new")
        self.file.write_bytes(b"changed")
        result = self.service.execute(plan, Event(), lambda message: None)[0]
        self.assertEqual(result.status, "failed")
        self.assertTrue(self.file.exists())
        protected = FileActionService(self.repo, SafetyPolicy([self.root]))
        with self.assertRaises(ValueError):
            protected.plan_rename(str(self.file), "new")

    def test_recycle_uses_backend_and_records_result_without_permanent_fallback(self):
        trash = self.root / "fixture-trash.txt"
        with patch("app.services.file_action_service.QFile") as backend:
            backend.supportsMoveToTrash.return_value = True
            backend.return_value.moveToTrash.side_effect = lambda: (self.file.rename(trash), True)[1]
            backend.return_value.fileName.return_value = str(trash)
            plan = self.service.plan_recycle([str(self.file)])
            results = self.service.execute(plan, Event(), lambda message: None)
        self.assertEqual(results[0].status, "recycled")
        self.assertEqual(trash.read_bytes(), b"original")
        self.assertEqual(self.repo.history()[0]["operation_type"], "recycle")

    def test_recycle_failure_and_cancellation_preserve_source(self):
        with patch("app.services.file_action_service.QFile") as backend:
            backend.supportsMoveToTrash.return_value = True
            backend.return_value.moveToTrash.return_value = False
            backend.return_value.errorString.return_value = "Recycle unavailable"
            plan = self.service.plan_recycle([str(self.file)])
            result = self.service.execute(plan, Event(), lambda message: None)[0]
            self.assertEqual(result.status, "failed")
            self.assertTrue(self.file.exists())
            cancel = Event()
            cancel.set()
            backend.return_value.moveToTrash.reset_mock()
            result = self.service.execute(plan, cancel, lambda message: None)[0]
            self.assertEqual(result.status, "cancelled")
            backend.return_value.moveToTrash.assert_not_called()
            backend.supportsMoveToTrash.return_value = False
            with self.assertRaises(OSError):
                self.service.plan_recycle([str(self.file)])

    def test_version_one_migration_preserves_shortcuts_and_history(self):
        self.repo.save_shortcut("A", "Existing", str(self.root))
        operation, ids = self.repo.start_operation(str(self.root), [str(self.file)])
        self.repo.record_item(ids[0], str(self.file), "skipped", "existing record")
        with connect(self.repo.path) as db:
            db.execute("DROP TABLE favorites")
            db.execute("PRAGMA user_version = 1")
        self.repo.initialize()
        self.assertEqual(self.repo.shortcuts()[0]["name"], "Existing")
        self.assertEqual(self.repo.history()[0]["message"], "existing record")
        self.repo.save_favorite("Folder", str(self.root))
        restarted = Repository(self.repo.path)
        self.assertEqual(restarted.favorites()[0]["name"], "Folder")
        restarted.delete_favorite(restarted.favorites()[0]["id"])
        self.assertTrue(self.file.exists())


class ContextWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "source"
        self.destination = self.root / "destination"
        self.source.mkdir()
        self.destination.mkdir()
        self.file = self.source / "source.txt"
        self.file.write_text("source", encoding="utf-8")
        self.database = self.root / "state" / "test.sqlite3"
        self.clipboard = MemoryClipboard()
        self.clipboard_patch = patch("app.ui.file_actions.QApplication.clipboard", return_value=self.clipboard)
        self.clipboard_patch.start()
        with patch("app.ui.main_window.standard_locations", return_value=[("Home", str(self.source))]):
            self.window = MainWindow(self.database, SafetyPolicy([self.database.parent]))
        self.window.show()
        wait_until(lambda: self.window.quick_sort.initialized and not self.window.quick_sort.busy)
        wait_until(lambda: self.window.explorer.model.rowCount(self.window.explorer.details.rootIndex()) == 1)
        self.window.explorer.details.setCurrentIndex(self.window.explorer.model.index(str(self.file)))

    def tearDown(self):
        QThreadPool.globalInstance().waitForDone()
        APPLICATION.processEvents()
        self.window.close()
        self.window.deleteLater()
        APPLICATION.processEvents()
        self.clipboard_patch.stop()
        self.temp.cleanup()

    def test_copy_paste_retains_original_and_cut_only_moves_on_paste(self):
        actions = self.window.file_actions
        actions.invoke("copy")
        self.assertTrue(self.file.exists())
        reports = []
        with patch("app.ui.quick_sort_panel.TransferConfirmationDialog") as confirmation, patch.object(self.window.quick_sort, "_report", side_effect=lambda title, text: reports.append(text)):
            confirmation.return_value.exec.return_value = QDialog.DialogCode.Accepted
            confirmation.return_value.decisions.return_value = ["copy"]
            actions.invoke("paste", str(self.destination))
            wait_until(lambda: bool(reports) and not self.window.quick_sort.busy and not self.window.browser._workers)
        self.assertTrue(self.file.exists())
        self.assertEqual((self.destination / self.file.name).read_text(), "source")
        other = self.root / "other"
        other.mkdir()
        self.window.explorer.details.setCurrentIndex(self.window.explorer.model.index(str(self.file)))
        actions.invoke("cut")
        self.assertTrue(self.file.exists())
        reports.clear()
        with patch("app.ui.quick_sort_panel.TransferConfirmationDialog") as confirmation, patch.object(self.window.quick_sort, "_report", side_effect=lambda title, text: reports.append(text)):
            confirmation.return_value.exec.return_value = QDialog.DialogCode.Accepted
            confirmation.return_value.decisions.return_value = ["move"]
            actions.invoke("paste", str(other))
            wait_until(lambda: bool(reports) and not self.window.quick_sort.busy)
        self.assertFalse(self.file.exists())
        self.assertEqual(actions.clipboard_payload()[0], ())

    def test_external_clipboard_defaults_to_copy(self):
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.file))])
        self.clipboard.setMimeData(mime)
        paths, operation, external = self.window.file_actions.clipboard_payload()
        self.assertEqual(operation, "copy")
        self.assertTrue(external)
        self.assertEqual([Path(path) for path in paths], [self.file])

    def test_cancelled_rename_and_recycle_do_not_modify_files(self):
        with patch("app.ui.file_actions.QInputDialog.getText", return_value=("renamed", True)), patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            self.window.file_actions.invoke("rename")
            wait_until(lambda: not self.window.quick_sort.busy)
            with patch("app.services.file_action_service.QFile") as backend:
                backend.supportsMoveToTrash.return_value = True
                self.window.file_actions.invoke("recycle")
                wait_until(lambda: not self.window.quick_sort.busy)
                backend.return_value.moveToTrash.assert_not_called()
        self.assertTrue(self.file.exists())
        self.assertEqual(self.window.quick_sort.repository.history(), [])

    def test_confirmed_rename_refreshes_listing_and_history(self):
        reports = []
        with patch("app.ui.file_actions.QInputDialog.getText", return_value=("renamed", True)), patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Accepted), patch.object(self.window.quick_sort, "_report", side_effect=lambda title, text: reports.append(text)):
            self.window.file_actions.invoke("rename")
            wait_until(lambda: bool(reports) and not self.window.quick_sort.busy)
        self.assertFalse(self.file.exists())
        self.assertEqual((self.source / "renamed.txt").read_text(), "source")
        self.assertEqual(self.window.quick_sort.repository.history()[0]["status"], "renamed")

    def test_favorites_add_remove_and_navigate(self):
        with patch("app.ui.favorites_panel.QInputDialog.getText", return_value=("Destination", True)):
            self.window.favorites.add_path(str(self.destination))
            wait_until(lambda: not self.window.favorites.busy)
        self.assertEqual(self.window.favorites.folders.count(), 1)
        item = self.window.favorites.folders.item(0)
        self.window.favorites.folders.setCurrentItem(item)
        self.window.favorites.folders.itemClicked.emit(item)
        wait_until(lambda: self.window.browser.current == self.destination)
        self.window.favorites.remove_selected()
        wait_until(lambda: not self.window.favorites.busy)
        self.assertTrue(self.destination.exists())
        self.assertEqual(self.window.quick_sort.repository.favorites(), [])

    def test_context_menu_exposes_file_actions_and_folder_safe_options(self):
        menu = self.window.file_actions.build_menu()
        actions = {action.objectName(): action for action in menu.actions() if action.objectName()}
        self.assertTrue(actions["rename"].isEnabled())
        self.assertTrue(actions["recycle"].isEnabled())
        self.assertFalse(actions["paste"].isEnabled())
        self.window.file_actions.invoke("copy")
        menu = self.window.file_actions.build_menu()
        actions = {action.objectName(): action for action in menu.actions() if action.objectName()}
        self.assertTrue(actions["paste"].isEnabled())
        self.window.explorer.details.clearSelection()
        menu = self.window.file_actions.build_menu()
        actions = {action.objectName(): action for action in menu.actions() if action.objectName()}
        self.assertFalse(actions["rename"].isEnabled())
        self.assertFalse(actions["recycle"].isEnabled())
        self.assertTrue(actions["properties"].isEnabled())

    def test_external_open_is_only_dispatched_by_explicit_action(self):
        with patch("app.ui.file_actions.QDesktopServices.openUrl", return_value=True) as launch:
            self.window.file_actions.invoke("open")
            wait_until(lambda: launch.call_count == 1 and not self.window.quick_sort.busy)
            self.assertEqual(Path(launch.call_args.args[0].toLocalFile()), self.file)


if __name__ == "__main__":
    unittest.main()
