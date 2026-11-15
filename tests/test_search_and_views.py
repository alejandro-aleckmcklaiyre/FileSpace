"""Search/sort/grid integration with real disposable directories."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QItemSelectionModel, QMimeData, QPointF, Qt, QThreadPool, QUrl
from PySide6.QtGui import QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from app.filesystem.safety import SafetyPolicy
from app.ui.main_window import MainWindow

APPLICATION = QApplication.instance() or QApplication([])


def wait_until(condition):
    deadline = time.monotonic() + 15
    while not condition():
        APPLICATION.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("View update timed out")
        time.sleep(0.01)
    APPLICATION.processEvents()


class SearchViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        self.destination = self.root / "destination"
        self.destination.mkdir()
        for name, content in (("alpha.txt", b"a"), ("beta.txt", b"b" * 30), ("photo.JPG", b"image"), ("video.mp4", b"video")):
            (self.source / name).write_bytes(content)
        (self.source / "nested").mkdir()
        (self.source / "nested" / "deep-needle.txt").write_bytes(b"nested")
        self.database = self.root / "state" / "test.sqlite3"
        with patch("app.ui.main_window.standard_locations", return_value=[("Home", str(self.source))]):
            self.window = MainWindow(self.database, SafetyPolicy([self.database.parent]))
        self.window.show()
        wait_until(lambda: self.window.quick_sort.initialized and not self.window.quick_sort.busy and self.window.explorer.model is not None)
        wait_until(lambda: len(self.names()) == 5)

    def tearDown(self):
        QThreadPool.globalInstance().waitForDone()
        APPLICATION.processEvents()
        self.window.close()
        self.window.deleteLater()
        APPLICATION.processEvents()
        self.temp.cleanup()

    def names(self):
        explorer = self.window.explorer
        model, root = explorer.model, explorer.active_view.rootIndex()
        return [model.fileName(model.index(row, 0, root)) for row in range(model.rowCount(root))] if model else []

    def test_search_filters_combine_and_do_not_scan_subfolders(self):
        explorer = self.window.explorer
        explorer.set_filters("PH", "", "All files")
        self.assertEqual(set(self.names()), {"alpha.txt", "photo.JPG"})
        explorer.set_filters("PHOTO", "", "All files")
        self.assertEqual(self.names(), ["photo.JPG"])
        explorer.set_filters("", ".TXT", "All files")
        self.assertEqual(set(self.names()), {"alpha.txt", "beta.txt", "nested"})
        explorer.set_filters("", "*.jpg", "Images")
        self.assertEqual(set(self.names()), {"photo.JPG", "nested"})
        explorer.set_filters("", ".txt", "Images")
        self.assertEqual(self.names(), ["nested"])
        explorer.set_filters("needle", "", "All files")
        self.assertEqual(self.names(), [])
        self.assertTrue(explorer.active_view.rootIndex().isValid())
        self.window.browser.navigate(str(self.source / "nested"))
        wait_until(lambda: self.names() == ["deep-needle.txt"])

    def test_search_field_is_live_and_sort_uses_numeric_metadata(self):
        self.window.navigation.search_field.setText(".txt")
        wait_until(lambda: len(self.names()) == 2)
        self.window.explorer.sort_files(1, Qt.SortOrder.DescendingOrder)
        self.assertEqual(self.names(), ["beta.txt", "alpha.txt"])
        self.window.explorer.sort_files(1, Qt.SortOrder.AscendingOrder)
        self.assertEqual(self.names(), ["alpha.txt", "beta.txt"])
        os.utime(self.source / "alpha.txt", (2000, 2000))
        os.utime(self.source / "beta.txt", (1000, 1000))
        self.window._refresh()
        wait_until(lambda: not self.window.browser._workers and len(self.names()) == 2)
        self.window.explorer.sort_files(3, Qt.SortOrder.AscendingOrder)
        self.assertEqual(self.names(), ["beta.txt", "alpha.txt"])

    def test_switching_views_preserves_files_and_deselection_has_no_ghost_rows(self):
        explorer = self.window.explorer
        paths = [self.source / "alpha.txt", self.source / "beta.txt"]
        selection = explorer.details.selectionModel()
        for path in paths:
            selection.select(explorer.model.index(str(path)), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        self.window.navigation.view_mode.setCurrentText("Grid")
        self.assertIs(explorer.active_view, explorer.grid)
        self.assertEqual({Path(path) for path in explorer.selected_paths()}, set(paths))
        selection.select(explorer.model.index(str(paths[0])), QItemSelectionModel.SelectionFlag.Deselect)
        self.assertEqual([Path(path) for path in explorer.selected_paths()], [paths[1]])
        self.window.navigation.view_mode.setCurrentText("Details")
        self.assertEqual([Path(path) for path in explorer.selected_paths()], [paths[1]])
        self.assertEqual(self.window.view_settings.value("view/mode"), "Details")

    def test_hidden_selected_files_are_not_in_quick_sort_confirmation(self):
        explorer = self.window.explorer
        for path in (self.source / "alpha.txt", self.source / "photo.JPG"):
            explorer.details.selectionModel().select(explorer.model.index(str(path)), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        explorer.set_filters("alpha", "", "All files")
        self.assertEqual(explorer.selected_paths(), [str(self.source / "alpha.txt").replace("\\", "/")])
        self.window.quick_sort.repository.save_shortcut("A", "Dest", str(self.destination))
        self.window.quick_sort._reload_rows(self.window.quick_sort.repository.shortcuts())
        with patch("app.ui.quick_sort_panel.TransferConfirmationDialog") as dialog:
            dialog.return_value.exec.return_value = QDialog.DialogCode.Rejected
            self.window.quick_sort._activate(self.window.quick_sort.shortcuts.item(0))
            wait_until(lambda: not self.window.quick_sort.busy)
            self.assertEqual([item.source for item in dialog.call_args.args[0].items], [self.source / "alpha.txt"])

    def test_grid_preview_selection_maps_to_original_file(self):
        self.window.navigation.view_mode.setCurrentText("Grid")
        self.window.explorer.grid.setCurrentIndex(self.window.explorer.model.index(str(self.source / "alpha.txt")))
        wait_until(lambda: self.window.preview.text.toPlainText() == "a")
        self.assertEqual([Path(path) for path in self.window.explorer.selected_paths()], [self.source / "alpha.txt"])

    def test_grid_mode_and_favorites_restore_after_restart(self):
        self.window.navigation.view_mode.setCurrentText("Grid")
        self.window.quick_sort.repository.save_favorite("Destination", str(self.destination))
        self.window.close()
        self.window.deleteLater()
        APPLICATION.processEvents()
        with patch("app.ui.main_window.standard_locations", return_value=[("Home", str(self.source))]):
            self.window = MainWindow(self.database, SafetyPolicy([self.database.parent]))
        self.window.show()
        wait_until(lambda: self.window.quick_sort.initialized and not self.window.quick_sort.busy)
        self.assertIs(self.window.explorer.active_view, self.window.explorer.grid)
        self.assertEqual(self.window.favorites.folders.count(), 1)
        self.assertEqual(self.window.favorites.folders.item(0).text(), "Destination")

    def test_grid_filtered_keyboard_transfer_uses_visible_files_only(self):
        self.window.navigation.view_mode.setCurrentText("Grid")
        self.window.explorer.set_filters(".txt", "", "All files")
        self.window.quick_sort.repository.save_shortcut("F", "Destination", str(self.destination))
        self.window.quick_sort._reload_rows(self.window.quick_sort.repository.shortcuts())
        self.window.activateWindow()
        grid = self.window.explorer.grid
        grid.setFocus()
        wait_until(grid.hasFocus)
        QTest.keyClick(grid, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual({Path(path).name for path in self.window.explorer.selected_paths()}, {"alpha.txt", "beta.txt"})
        reports = []
        with patch("app.ui.quick_sort_panel.TransferConfirmationDialog") as dialog, patch.object(self.window.quick_sort, "_report", side_effect=lambda title, text: reports.append(text)):
            dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog.return_value.decisions.return_value = ["move", "move"]
            QTest.keyClick(grid, Qt.Key.Key_F)
            wait_until(lambda: bool(reports) and not self.window.quick_sort.busy)
            self.assertEqual({item.source.name for item in dialog.call_args.args[0].items}, {"alpha.txt", "beta.txt"})
        self.assertEqual({file.name for file in self.destination.iterdir()}, {"alpha.txt", "beta.txt"})
        self.assertTrue((self.source / "photo.JPG").exists())

    def test_grid_drop_maps_folder_target_through_proxy(self):
        self.window.navigation.view_mode.setCurrentText("Grid")
        grid = self.window.explorer.grid
        QApplication.processEvents()
        mime = QMimeData()
        outside = self.root / "outside.txt"
        outside.write_bytes(b"external")
        mime.setUrls([QUrl.fromLocalFile(str(outside))])
        index = self.window.explorer.model.index(str(self.source / "nested"))
        point = grid.visualRect(index).center()
        event = QDropEvent(QPointF(point), Qt.DropAction.CopyAction | Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        with patch("app.ui.quick_sort_panel.ExternalTransferDialog") as dialog:
            dialog.return_value.exec.return_value = QDialog.DialogCode.Rejected
            grid.dropEvent(event)
            self.assertTrue(event.isAccepted())
            wait_until(lambda: dialog.call_count == 1)
            self.assertEqual(Path(dialog.call_args.args[1]), self.source / "nested")
        self.assertTrue(outside.exists())


if __name__ == "__main__":
    unittest.main()
