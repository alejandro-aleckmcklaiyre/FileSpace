"""Full Qt Quick Sort flow against disposable files and database."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from PySide6.QtCore import QItemSelectionModel, QThreadPool, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app.database.repository import Repository
from app.filesystem.safety import SafetyPolicy
from app.services.file_preview_service import PreviewResult
from app.ui.dialogs.quick_sort import MoveConfirmationDialog
from app.ui.main_window import MainWindow

APPLICATION = QApplication.instance() or QApplication([])


def wait_until(condition) -> None:
    deadline = time.monotonic() + 15
    while not condition():
        APPLICATION.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("Quick Sort timed out")
        time.sleep(0.01)
    APPLICATION.processEvents()


class QuickSortTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "source"
        self.destination = self.root / "destination"
        self.source.mkdir()
        self.destination.mkdir()
        self.files = [self.source / "one.txt", self.source / "two.txt"]
        for file in self.files:
            file.write_text(file.stem, encoding="utf-8")
        self.database = self.root / "state" / "test.sqlite3"
        self.repo = Repository(self.database)
        self.repo.initialize()
        self.repo.save_shortcut("A", "Destination", str(self.destination))
        with patch("app.ui.main_window.standard_locations", return_value=[("Home", str(self.source))]):
            self.window = MainWindow(self.database, SafetyPolicy([self.database.parent]))
        self.window.show()
        wait_until(lambda: self.window.quick_sort.initialized and not self.window.quick_sort.busy and self.window.browser.current == self.source)
        wait_until(lambda: self.window.explorer.model.rowCount(self.window.explorer.details.rootIndex()) == 2)

    def tearDown(self) -> None:
        QThreadPool.globalInstance().waitForDone()
        APPLICATION.processEvents()
        self.window.close()
        self.window.deleteLater()
        APPLICATION.processEvents()
        self.temp.cleanup()

    def select_files(self) -> None:
        model = self.window.explorer.model
        selection = self.window.explorer.details.selectionModel()
        for file in self.files:
            selection.select(model.index(str(file)), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        self.assertEqual(len(self.window.explorer.selected_paths()), 2)

    def test_no_selection_opens_destination(self) -> None:
        shortcuts = self.window.quick_sort.shortcuts
        self.window.sidebar.ensureWidgetVisible(shortcuts)
        APPLICATION.processEvents()
        QTest.mouseClick(shortcuts.viewport(), Qt.MouseButton.LeftButton, pos=shortcuts.visualItemRect(shortcuts.item(0)).center())
        wait_until(lambda: self.window.browser.current == self.destination)
        self.window.browser.back()
        wait_until(lambda: self.window.browser.current == self.source)
        QTest.mouseClick(shortcuts.viewport(), Qt.MouseButton.LeftButton, pos=shortcuts.visualItemRect(shortcuts.item(0)).center())
        wait_until(lambda: self.window.browser.current == self.destination)
        self.assertTrue(all(file.exists() for file in self.files))
        self.assertEqual(self.repo.history(), [])

    @unittest.skipUnless(os.name == "nt", "NTFS streams require Windows")
    def test_downloaded_file_shortcut_click_moves_and_preserves_marker(self) -> None:
        marker = b"[ZoneTransfer]\nZoneId=3\n"
        suffix = ":Zone.Identifier:$DATA"
        with open(str(self.files[0]) + suffix, "wb") as output:
            output.write(marker)
        self.window.explorer.details.setCurrentIndex(self.window.explorer.model.index(str(self.files[0])))
        self.assertIn("1 item(s) selected", self.window.quick_sort.selection_hint.text())
        reports = []
        with patch("app.ui.quick_sort_panel.MoveConfirmationDialog") as dialog, patch.object(self.window.quick_sort, "_report", side_effect=lambda title, text: reports.append(text)):
            dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog.return_value.decisions.return_value = ["move"]
            shortcuts = self.window.quick_sort.shortcuts
            self.window.sidebar.ensureWidgetVisible(shortcuts)
            APPLICATION.processEvents()
            QTest.mouseClick(shortcuts.viewport(), Qt.MouseButton.LeftButton, pos=shortcuts.visualItemRect(shortcuts.item(0)).center())
            wait_until(lambda: bool(reports) and not self.window.quick_sort.busy)
        self.assertFalse(self.files[0].exists())
        with open(str(self.destination / self.files[0].name) + suffix, "rb") as incoming:
            self.assertEqual(incoming.read(), marker)
        self.assertEqual(self.repo.history()[0]["status"], "moved")

    def test_cancel_confirmation_performs_no_transfer(self) -> None:
        self.select_files()
        with patch("app.ui.quick_sort_panel.MoveConfirmationDialog") as dialog:
            dialog.return_value.exec.return_value = QDialog.DialogCode.Rejected
            self.window.quick_sort.shortcuts.itemClicked.emit(self.window.quick_sort.shortcuts.item(0))
            wait_until(lambda: not self.window.quick_sort.busy)
        self.assertTrue(all(file.exists() for file in self.files))
        self.assertEqual(self.repo.history(), [])

    def test_confirmed_multiple_files_move_and_persist_history(self) -> None:
        self.select_files()
        reports = []
        with patch("app.ui.quick_sort_panel.MoveConfirmationDialog") as dialog, patch.object(self.window.quick_sort, "_report", side_effect=lambda title, text: reports.append(text)):
            dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog.return_value.decisions.return_value = ["move", "move"]
            self.window.quick_sort.shortcuts.itemClicked.emit(self.window.quick_sort.shortcuts.item(0))
            wait_until(lambda: bool(reports) and not self.window.quick_sort.busy)
        self.assertFalse(any(file.exists() for file in self.files))
        self.assertEqual({file.name for file in self.destination.iterdir()}, {"one.txt", "two.txt"})
        self.assertEqual({row["status"] for row in self.repo.history()}, {"moved"})
        self.assertTrue(self.window.explorer.isEnabled())

    def test_replacement_needs_second_confirmation(self) -> None:
        (self.destination / self.files[0].name).write_bytes(b"existing")
        plan = self.window.quick_sort.service.plan([str(self.files[0])], str(self.destination))
        dialog = MoveConfirmationDialog(plan)
        self.assertEqual(dialog.decisions(), ["skip"])
        dialog.choices[0].setCurrentIndex(2)
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.No):
            dialog._confirm()
            self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes):
            dialog._confirm()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)

    def test_preview_release_waits_for_running_parser(self) -> None:
        started, release = Event(), Event()
        callbacks = []
        def delayed(path, page):
            started.set()
            release.wait(5)
            return PreviewResult(path, "text", "preview")
        with patch("app.services.file_preview_service.load_preview", side_effect=delayed):
            self.window.preview.select_file(str(self.files[0]))
            wait_until(started.is_set)
            self.window.preview.release_for_transfer(lambda: callbacks.append(True))
            APPLICATION.processEvents()
            self.assertEqual(callbacks, [])
            release.set()
            wait_until(lambda: bool(callbacks))
        self.assertTrue(self.window.preview.service.idle)
        self.assertTrue(all(file.exists() for file in self.files))

    def test_ui_add_edit_reorder_delete(self) -> None:
        panel = self.window.quick_sort
        with patch("app.ui.quick_sort_panel.ShortcutDialog") as dialog:
            form = dialog.return_value
            form.exec.return_value = QDialog.DialogCode.Accepted
            form.keyword.text.return_value = "B"
            form.name.text.return_value = "Second"
            form.destination.text.return_value = str(self.destination)
            panel._edit()
            wait_until(lambda: not panel.busy)
            self.assertEqual(panel.shortcuts.count(), 2)
            panel.shortcuts.setCurrentRow(1)
            form.name.text.return_value = "Edited"
            panel._edit_selected()
            wait_until(lambda: not panel.busy)
        panel._reorder(-1)
        wait_until(lambda: not panel.busy)
        self.assertEqual(self.repo.shortcuts()[0]["name"], "Edited")
        self.assertEqual(panel._selected()["keyword"], "B")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            panel._delete()
            wait_until(lambda: not panel.busy)
        self.assertEqual(panel.shortcuts.count(), 1)
        self.assertTrue(self.destination.is_dir())


if __name__ == "__main__":
    unittest.main()
