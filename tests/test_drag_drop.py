"""Qt drop routing and confirmed transfer tests using disposable files."""

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QItemSelectionModel, QMimeData, QPoint, QPointF, QThreadPool, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QDialog, QListWidgetItem

from app.database.repository import Repository
from app.filesystem.safety import SafetyPolicy
from app.ui.dialogs.quick_sort import ExternalTransferDialog
from app.ui.drag_drop import INTERNAL_MIME, DropRequest, ShortcutDropList, event_files
from app.ui.file_explorer import FileExplorerWidget
from app.ui.main_window import MainWindow

APPLICATION = QApplication.instance() or QApplication([])
ACTIONS = Qt.DropAction.CopyAction | Qt.DropAction.MoveAction


def wait_until(condition) -> None:
    deadline = time.monotonic() + 15
    while not condition():
        APPLICATION.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("Drop workflow timed out")
        time.sleep(0.01)
    APPLICATION.processEvents()


def external_mime(paths) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
    return mime


class InternalDropEvent(QDropEvent):
    def __init__(self, point, mime, source, modifiers=Qt.KeyboardModifier.NoModifier):
        super().__init__(QPointF(point), ACTIONS, mime, Qt.MouseButton.LeftButton, modifiers)
        self._source_widget = source

    def source(self):
        return self._source_widget


class DragEventTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "source"
        self.destination = self.root / "destination"
        self.source.mkdir()
        self.destination.mkdir()
        self.file = self.source / "file.txt"
        self.file.write_bytes(b"unchanged")
        self.external = self.root / "external.txt"
        self.external.write_bytes(b"external")
        self.explorer = FileExplorerWidget()
        self.explorer.resize(700, 450)
        self.view = self.explorer.details
        self.view.drop_policy = SafetyPolicy([])
        self.explorer.set_location(str(self.root))
        self.explorer.show()
        wait_until(lambda: self.explorer.model.rowCount(self.view.rootIndex()) == 3)
        self.received = []
        self.view.files_dropped.connect(self.received.append)

    def tearDown(self) -> None:
        self.explorer.close()
        self.explorer.deleteLater()
        APPLICATION.processEvents()
        self.temp.cleanup()

    def destination_point(self):
        index = self.explorer.model.index(str(self.destination))
        return self.view.visualRect(index).center()

    def test_external_viewport_events_acknowledge_copy_and_defer_work(self) -> None:
        mime = external_mime([self.external])
        point = self.destination_point()
        enter = QDragEnterEvent(QPointF(point), ACTIONS, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.view.viewport(), enter)
        self.assertTrue(enter.isAccepted())
        move = QDragMoveEvent(QPointF(point), ACTIONS, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.view.viewport(), move)
        self.assertTrue(move.isAccepted())
        self.assertTrue(self.view._drag_valid)
        drop = QDropEvent(QPointF(point), ACTIONS, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.view.viewport(), drop)
        self.assertTrue(drop.isAccepted())
        self.assertEqual(drop.dropAction(), Qt.DropAction.CopyAction)
        self.assertEqual(self.received, [])
        wait_until(lambda: bool(self.received))
        request = self.received[0]
        self.assertTrue(request.external)
        self.assertEqual(request.operation, "copy")
        self.assertEqual(Path(request.destination), self.destination)
        self.assertEqual(self.external.read_bytes(), b"external")
        self.assertFalse(list(self.destination.iterdir()))

    def test_internal_move_ctrl_copy_and_private_mime(self) -> None:
        mime = QMimeData()
        mime.setData(INTERNAL_MIME, json.dumps([str(self.file)]).encode())
        for modifiers, operation in (
            (Qt.KeyboardModifier.NoModifier, "move"),
            (Qt.KeyboardModifier.ControlModifier, "copy"),
        ):
            event = InternalDropEvent(self.destination_point(), mime, self.view, modifiers)
            self.view.dropEvent(event)
            self.assertTrue(event.isAccepted())
            wait_until(lambda: len(self.received) == (1 if operation == "move" else 2))
            self.assertFalse(self.received[-1].external)
            self.assertEqual(self.received[-1].operation, operation)
        # A forged private marker with no actual FileSpace source is not trusted.
        forged = QDropEvent(QPointF(self.destination_point()), ACTIONS, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.assertEqual(event_files(forged)[0], ())

    def test_blank_area_targets_current_directory(self) -> None:
        mime = external_mime([self.file])
        point = QPoint(20, self.view.viewport().height() - 10)
        event = QDropEvent(QPointF(point), ACTIONS, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.view.dropEvent(event)
        wait_until(lambda: bool(self.received))
        self.assertEqual(Path(self.received[0].destination), self.root)

    def test_file_rows_protected_locations_same_folder_and_disabled_view_rejected(self) -> None:
        mime = external_mime([self.file])
        file_point = self.view.visualRect(self.explorer.model.index(str(self.external))).center()
        event = QDropEvent(QPointF(file_point), ACTIONS, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.view.dropEvent(event)
        self.assertFalse(event.isAccepted())
        self.view.drop_policy = SafetyPolicy([self.destination])
        event = QDropEvent(QPointF(self.destination_point()), ACTIONS, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.view.dropEvent(event)
        self.assertFalse(event.isAccepted())
        self.view.drop_policy = SafetyPolicy([])
        same_mime = external_mime([self.external])
        same = QDropEvent(QPointF(20, self.view.viewport().height() - 10), ACTIONS, same_mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.view.dropEvent(same)
        self.assertFalse(same.isAccepted())
        self.view.setEnabled(False)
        disabled = QDropEvent(QPointF(self.destination_point()), ACTIONS, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.view.dropEvent(disabled)
        self.assertFalse(disabled.isAccepted())
        APPLICATION.processEvents()
        self.assertEqual(self.received, [])
        self.assertTrue(self.file.exists())

    def test_nonlocal_text_and_move_only_external_payloads_rejected(self) -> None:
        for mime in (QMimeData(), external_mime([self.file])):
            if not mime.hasUrls():
                mime.setUrls([QUrl("https://example.com/file.txt")])
            event = QDropEvent(QPointF(self.destination_point()), Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            self.view.dropEvent(event)
            self.assertFalse(event.isAccepted())
        text = QMimeData()
        text.setText(str(self.file))
        event = QDropEvent(QPointF(self.destination_point()), ACTIONS, text, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.view.dropEvent(event)
        self.assertFalse(event.isAccepted())

    def test_internal_start_drag_never_exports_shell_urls_or_removes_sources(self) -> None:
        self.explorer.set_location(str(self.source))
        wait_until(lambda: self.explorer.model.rowCount(self.view.rootIndex()) == 1)
        self.view.setCurrentIndex(self.explorer.model.index(str(self.file)))
        self.assertTrue(self.explorer.model.flags(self.view.currentIndex()) & Qt.ItemFlag.ItemIsDragEnabled)
        with patch("app.ui.drag_drop.QDrag") as drag:
            self.view.startDrag(ACTIONS)
            mime = drag.return_value.setMimeData.call_args.args[0]
            self.assertTrue(mime.hasFormat(INTERNAL_MIME))
            self.assertFalse(mime.hasUrls())
            self.assertEqual([Path(value) for value in json.loads(bytes(mime.data(INTERNAL_MIME)))], [self.file])
        self.assertEqual(self.file.read_bytes(), b"unchanged")

    def test_drag_includes_partial_selection_once_per_file(self) -> None:
        self.explorer.set_location(str(self.source))
        second = self.source / "second.txt"
        second.write_bytes(b"second")
        wait_until(lambda: self.explorer.model.rowCount(self.view.rootIndex()) == 2)
        selection = self.view.selectionModel()
        for path in (self.file, second):
            index = self.explorer.model.index(str(path))
            for column in (0, 2):
                selection.select(index.siblingAtColumn(column), QItemSelectionModel.SelectionFlag.Select)
        self.assertEqual(len(selection.selectedRows(0)), 0)
        with patch("app.ui.drag_drop.QDrag") as drag:
            self.view.startDrag(ACTIONS)
            mime = drag.return_value.setMimeData.call_args.args[0]
            paths = json.loads(bytes(mime.data(INTERNAL_MIME)))
            self.assertEqual({Path(path) for path in paths}, {self.file, second})
            self.assertEqual(len(paths), 2)

    def test_quick_sort_target_accepts_only_actual_shortcut_rows(self) -> None:
        shortcuts = ShortcutDropList()
        shortcuts.drop_policy = SafetyPolicy([])
        shortcuts.resize(350, 180)
        item = QListWidgetItem("Destination")
        item.setData(Qt.ItemDataRole.UserRole, {"destination_path": str(self.destination)})
        shortcuts.addItem(item)
        shortcuts.show()
        APPLICATION.processEvents()
        received = []
        shortcuts.files_dropped.connect(received.append)
        mime = external_mime([self.file])
        event = QDropEvent(QPointF(shortcuts.visualItemRect(item).center()), ACTIONS, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        shortcuts.dropEvent(event)
        self.assertTrue(event.isAccepted())
        wait_until(lambda: bool(received))
        self.assertEqual(Path(received[0].destination), self.destination)
        blank = QDropEvent(QPointF(20, shortcuts.viewport().height() - 10), ACTIONS, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        shortcuts.dropEvent(blank)
        self.assertFalse(blank.isAccepted())
        shortcuts.close()
        shortcuts.deleteLater()


class DropWorkflowTests(unittest.TestCase):
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
        with patch("app.ui.main_window.standard_locations", return_value=[("Home", str(self.destination))]):
            self.window = MainWindow(self.database, SafetyPolicy([self.database.parent]))
        self.window.show()
        wait_until(lambda: self.window.quick_sort.initialized and not self.window.quick_sort.busy and self.window.browser.current == self.destination)

    def tearDown(self) -> None:
        QThreadPool.globalInstance().waitForDone()
        APPLICATION.processEvents()
        self.window.close()
        self.window.deleteLater()
        APPLICATION.processEvents()
        self.temp.cleanup()

    def test_external_mode_defaults_to_copy(self) -> None:
        dialog = ExternalTransferDialog(tuple(map(str, self.files)), str(self.destination))
        self.assertEqual(dialog.operation(), "copy")
        dialog.move.setChecked(True)
        self.assertEqual(dialog.operation(), "move")

    def perform(self, operation: str, external: bool) -> None:
        reports = []
        with patch("app.ui.quick_sort_panel.ExternalTransferDialog") as mode, patch("app.ui.quick_sort_panel.TransferConfirmationDialog") as confirm, patch.object(self.window.quick_sort, "_report", side_effect=lambda title, text: reports.append(text)):
            mode.return_value.exec.return_value = QDialog.DialogCode.Accepted
            mode.return_value.operation.return_value = operation
            confirm.return_value.exec.return_value = QDialog.DialogCode.Accepted
            confirm.return_value.decisions.return_value = [operation] * len(self.files)
            request = DropRequest(tuple(map(str, self.files)), str(self.destination), "copy" if external else operation, external)
            self.window.explorer.files_dropped.emit(request)
            wait_until(lambda: bool(reports) and not self.window.quick_sort.busy)
            self.assertEqual(mode.call_count, 1 if external else 0)
        self.assertTrue(all((self.destination / file.name).exists() for file in self.files))
        self.assertEqual([file.exists() for file in self.files], [operation == "copy"] * len(self.files))
        recent = self.repo.history()[:len(self.files)]
        self.assertEqual({row["operation_type"] for row in recent}, {operation})
        self.assertEqual({row["status"] for row in recent}, {"copied" if operation == "copy" else "moved"})

    def test_external_copy_retains_all_sources_and_records_copy_history(self) -> None:
        self.perform("copy", True)

    def test_external_explicit_move_removes_verified_sources(self) -> None:
        self.perform("move", True)

    def test_internal_ctrl_drag_copy_retains_sources(self) -> None:
        self.perform("copy", False)

    def test_internal_drag_move(self) -> None:
        self.perform("move", False)

    def test_successive_bulk_transfers_reuse_worker_and_refresh(self) -> None:
        for batch, (operation, external) in enumerate((("move", False), ("copy", True), ("move", True), ("copy", False))):
            with self.subTest(batch=batch, operation=operation):
                self.files = [self.source / f"batch-{batch}-{index}.txt" for index in range(3)]
                for file in self.files:
                    file.write_text(file.name, encoding="utf-8")
                self.perform(operation, external)
                wait_until(lambda: not self.window.browser._workers)
                self.assertFalse(self.window.quick_sort.runner.busy)
                self.assertTrue(self.window.explorer.details.isEnabled())

    def test_cancel_external_import_does_nothing(self) -> None:
        with patch("app.ui.quick_sort_panel.ExternalTransferDialog") as mode:
            mode.return_value.exec.return_value = QDialog.DialogCode.Rejected
            self.window.quick_sort.request_drop(DropRequest(tuple(map(str, self.files)), str(self.destination), "copy", True))
        self.assertFalse(self.window.quick_sort.busy)
        self.assertTrue(all(file.exists() for file in self.files))
        self.assertFalse(list(self.destination.iterdir()))
        self.assertEqual(self.repo.history(), [])

    def test_cancel_final_drop_confirmation_does_nothing(self) -> None:
        with patch("app.ui.quick_sort_panel.ExternalTransferDialog") as mode, patch("app.ui.quick_sort_panel.TransferConfirmationDialog") as confirmation:
            mode.return_value.exec.return_value = QDialog.DialogCode.Accepted
            mode.return_value.operation.return_value = "move"
            confirmation.return_value.exec.return_value = QDialog.DialogCode.Rejected
            self.window.quick_sort.request_drop(DropRequest(tuple(map(str, self.files)), str(self.destination), "copy", True))
            wait_until(lambda: not self.window.quick_sort.busy)
        self.assertTrue(all(file.exists() for file in self.files))
        self.assertFalse(list(self.destination.iterdir()))
        self.assertEqual(self.repo.history(), [])

    def test_external_folder_or_missing_file_is_rejected_without_changes(self) -> None:
        warnings = []
        with patch("app.ui.quick_sort_panel.ExternalTransferDialog") as mode, patch("app.ui.quick_sort_panel.QMessageBox.warning", side_effect=lambda *args: warnings.append(args[2])):
            mode.return_value.exec.return_value = QDialog.DialogCode.Accepted
            mode.return_value.operation.return_value = "copy"
            for path in (self.source, self.source / "missing.txt"):
                previous = len(warnings)
                self.window.quick_sort.request_drop(DropRequest((str(path),), str(self.destination), "copy", True))
                wait_until(lambda: len(warnings) > previous and not self.window.quick_sort.busy)
        self.assertTrue(all(file.exists() for file in self.files))
        self.assertFalse(list(self.destination.iterdir()))
        self.assertEqual(self.repo.history(), [])


if __name__ == "__main__":
    unittest.main()
