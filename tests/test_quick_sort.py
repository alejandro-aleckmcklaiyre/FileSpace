"""Full Qt Quick Sort flow against disposable files and database."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from PySide6.QtCore import QEvent, QItemSelectionModel, QThreadPool, Qt
from PySide6.QtTest import QTest
from PySide6.QtGui import QImage, QKeyEvent
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app.database.repository import Repository
from app.filesystem.safety import SafetyPolicy
from app.services.file_preview_service import PreviewResult
from app.ui.dialogs.quick_sort import TransferConfirmationDialog
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

    def configure_letter(self, keyword="f") -> None:
        shortcut = self.repo.shortcuts()[0]
        self.repo.save_shortcut(keyword, "Destination", str(self.destination), shortcut["id"])
        self.window.quick_sort._reload_rows(self.repo.shortcuts())

    def focus_file_list(self):
        self.window.activateWindow()
        view = self.window.explorer.details
        view.setFocus()
        wait_until(view.hasFocus)
        return view

    def test_letter_key_confirms_selected_batch_instead_of_filename_search(self) -> None:
        self.configure_letter("f")
        matching_file = self.source / "filename-starting-f.txt"
        matching_file.write_text("leave this file", encoding="utf-8")
        wait_until(lambda: self.window.explorer.model.rowCount(self.window.explorer.details.rootIndex()) == 3)
        for modifiers in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ShiftModifier):
            self.window.explorer.details.clearSelection()
            self.select_files()
            view = self.focus_file_list()
            with patch("app.ui.quick_sort_panel.TransferConfirmationDialog") as dialog:
                dialog.return_value.exec.return_value = QDialog.DialogCode.Rejected
                QTest.keyClick(view, Qt.Key.Key_F, modifiers)
                wait_until(lambda: dialog.call_count == 1 and not self.window.quick_sort.busy)
                self.assertEqual({item.source for item in dialog.call_args.args[0].items}, set(self.files))
            self.assertEqual({Path(path) for path in self.window.explorer.selected_paths()}, set(self.files))
        self.assertTrue(all(file.exists() for file in self.files))
        self.assertTrue(matching_file.exists())
        self.assertEqual(self.repo.history(), [])

    def test_letter_key_moves_only_after_confirmation(self) -> None:
        self.configure_letter()
        self.select_files()
        view = self.focus_file_list()
        reports = []
        with patch("app.ui.quick_sort_panel.TransferConfirmationDialog") as dialog, patch.object(self.window.quick_sort, "_report", side_effect=lambda title, text: reports.append(text)):
            dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog.return_value.decisions.return_value = ["move", "move"]
            QTest.keyClick(view, Qt.Key.Key_F)
            wait_until(lambda: bool(reports) and not self.window.quick_sort.busy)
        self.assertFalse(any(file.exists() for file in self.files))
        self.assertTrue(all((self.destination / file.name).exists() for file in self.files))
        self.assertEqual(len(self.repo.history()), 2)

    def test_letter_key_opens_destination_without_selection(self) -> None:
        self.configure_letter()
        view = self.focus_file_list()
        QTest.keyClick(view, Qt.Key.Key_F)
        wait_until(lambda: self.window.browser.current == self.destination)
        self.assertTrue(all(file.exists() for file in self.files))
        self.assertEqual(self.repo.history(), [])

    def test_text_entry_and_ctrl_a_do_not_activate_destinations(self) -> None:
        # A is assigned by the fixture, but Ctrl+A must still select all files.
        view = self.focus_file_list()
        with patch.object(self.window.quick_sort, "_activate") as activation:
            QTest.keyClick(view, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            self.assertEqual(len(self.window.explorer.selected_paths()), 2)
            field = self.window.navigation.address_field
            field.setFocus()
            field.clear()
            QTest.keyClicks(field, "a")
            self.assertEqual(field.text(), "a")
            activation.assert_not_called()

    def test_unassigned_letters_keep_filename_navigation(self) -> None:
        view = self.focus_file_list()
        with patch.object(self.window.quick_sort, "_activate") as activation:
            QTest.keyClick(view, Qt.Key.Key_T)
            wait_until(lambda: self.window.explorer.model.fileName(view.currentIndex()) == "two.txt")
            activation.assert_not_called()

    def test_held_key_and_busy_state_do_not_trigger_again(self) -> None:
        self.configure_letter()
        self.select_files()
        view = self.focus_file_list()
        with patch.object(self.window.quick_sort, "_activate") as activation:
            repeat = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F, Qt.KeyboardModifier.NoModifier, "f", True)
            QApplication.sendEvent(view, repeat)
            self.assertTrue(repeat.isAccepted())
            self.window.quick_sort._set_busy(True)
            self.assertTrue(self.window.quick_sort.activate_keyword("F"))
            activation.assert_not_called()
            self.window.quick_sort._set_busy(False)
        self.assertTrue(all(file.exists() for file in self.files))

    def test_keyboard_bindings_follow_keyword_edit_and_deletion(self) -> None:
        self.configure_letter("f")
        with patch.object(self.window.quick_sort, "_activate") as activation:
            self.assertTrue(self.window.quick_sort.activate_keyword("F"))
            self.assertEqual(activation.call_count, 1)
            self.configure_letter("g")
            self.assertFalse(self.window.quick_sort.activate_keyword("F"))
            self.assertTrue(self.window.quick_sort.activate_keyword("G"))
            self.assertEqual(activation.call_count, 2)
            shortcut = self.repo.shortcuts()[0]
            self.repo.delete_shortcut(shortcut["id"])
            self.window.quick_sort._reload_rows(self.repo.shortcuts())
            self.assertFalse(self.window.quick_sort.activate_keyword("G"))

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
        with patch("app.ui.quick_sort_panel.TransferConfirmationDialog") as dialog, patch.object(self.window.quick_sort, "_report", side_effect=lambda title, text: reports.append(text)):
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
        with patch("app.ui.quick_sort_panel.TransferConfirmationDialog") as dialog:
            dialog.return_value.exec.return_value = QDialog.DialogCode.Rejected
            self.window.quick_sort.shortcuts.itemClicked.emit(self.window.quick_sort.shortcuts.item(0))
            wait_until(lambda: not self.window.quick_sort.busy)
        self.assertTrue(all(file.exists() for file in self.files))
        self.assertEqual(self.repo.history(), [])

    def test_confirmed_multiple_files_move_and_persist_history(self) -> None:
        self.select_files()
        reports = []
        with patch("app.ui.quick_sort_panel.TransferConfirmationDialog") as dialog, patch.object(self.window.quick_sort, "_report", side_effect=lambda title, text: reports.append(text)):
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
        dialog = TransferConfirmationDialog(plan)
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

    def test_repeated_image_batches_with_ctrl_and_shift_clicks_include_every_selected_file(self) -> None:
        images = [self.source / f"image-{number}.png" for number in range(8)]
        image = QImage(80, 60, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.green)
        for path in images:
            self.assertTrue(image.save(str(path)))
        self.window.browser.refresh()
        wait_until(lambda: not self.window.browser._workers and self.window.explorer.model.rowCount(self.window.explorer.details.rootIndex()) == 10)
        warnings, reports = [], []
        with patch("app.ui.quick_sort_panel.TransferConfirmationDialog") as dialog, patch.object(self.window.quick_sort, "_report", side_effect=lambda title, text: reports.append(text)), patch("app.ui.quick_sort_panel.QMessageBox.warning", side_effect=lambda *args: warnings.append(args[2])):
            dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog.return_value.decisions.return_value = ["move", "move"]
            for batch in range(4):
                paths = images[batch * 2:batch * 2 + 2]
                view = self.window.explorer.details
                for number, path in enumerate(paths):
                    index = self.window.explorer.model.index(str(path))
                    view.scrollTo(index)
                    APPLICATION.processEvents()
                    point = view.visualRect(index).center()
                    modifier = (Qt.KeyboardModifier.ControlModifier if batch < 2 else Qt.KeyboardModifier.ShiftModifier) if number else Qt.KeyboardModifier.NoModifier
                    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, modifier, point)
                self.assertEqual({Path(path) for path in self.window.explorer.selected_paths()}, set(paths))
                shortcuts = self.window.quick_sort.shortcuts
                self.window.sidebar.ensureWidgetVisible(shortcuts)
                APPLICATION.processEvents()
                QTest.mouseClick(shortcuts.viewport(), Qt.MouseButton.LeftButton, pos=shortcuts.visualItemRect(shortcuts.item(0)).center())
                wait_until(lambda: len(reports) > batch or bool(warnings))
                self.assertEqual(warnings, [])
                plan = dialog.call_args.args[0]
                self.assertEqual({item.source for item in plan.items}, set(paths))
                wait_until(lambda: not self.window.quick_sort.busy and not self.window.browser._workers)
                wait_until(lambda: self.window.explorer.model.rowCount(view.rootIndex()) == 8 - batch * 2)
                self.assertTrue(all((self.destination / path.name).exists() for path in paths))
        self.assertEqual(len(self.repo.history()), 8)

    def test_second_batch_includes_files_with_only_some_cells_selected(self) -> None:
        reports, warnings = [], []
        with patch("app.ui.quick_sort_panel.TransferConfirmationDialog") as dialog, patch.object(self.window.quick_sort, "_report", side_effect=lambda title, text: reports.append(text)), patch("app.ui.quick_sort_panel.QMessageBox.warning", side_effect=lambda *args: warnings.append(args[2])):
            dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog.return_value.decisions.return_value = ["move", "move"]
            self.select_files()
            self.window.quick_sort._activate(self.window.quick_sort.shortcuts.item(0))
            wait_until(lambda: len(reports) == 1 and not self.window.quick_sort.busy and not self.window.browser._workers)
            wait_until(lambda: self.window.explorer.model.rowCount(self.window.explorer.details.rootIndex()) == 0)

            second = [self.source / f"second-{number}.txt" for number in range(3)]
            for file in second:
                file.write_text(file.name, encoding="utf-8")
            wait_until(lambda: self.window.explorer.model.rowCount(self.window.explorer.details.rootIndex()) == 3)
            view = self.window.explorer.details
            selection = view.selectionModel()
            for number, file in enumerate(second):
                index = self.window.explorer.model.index(str(file)).siblingAtColumn(number)
                selection.select(index, QItemSelectionModel.SelectionFlag.Select)
            self.assertEqual(len(selection.selectedRows(0)), 0)
            self.assertEqual({Path(path) for path in self.window.explorer.selected_paths()}, set(second))
            self.assertIn("3 item(s) selected", self.window.quick_sort.selection_hint.text())
            dialog.return_value.decisions.return_value = ["move"] * 3
            self.window.quick_sort._activate(self.window.quick_sort.shortcuts.item(0))
            wait_until(lambda: len(reports) == 2 or bool(warnings))
            self.assertEqual(warnings, [])
            plan = dialog.call_args.args[0]
            self.assertEqual({item.source for item in plan.items}, set(second))
            self.assertTrue(all((self.destination / file.name).exists() for file in second))
            self.assertEqual(len(self.repo.history()), 5)


if __name__ == "__main__":
    unittest.main()
