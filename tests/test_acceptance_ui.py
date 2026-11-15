"""Acceptance regressions at Qt gesture, viewport and worker boundaries."""

import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, Qt, QThreadPool, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QListWidgetItem, QMessageBox

from app.filesystem.safety import SafetyPolicy
from app.services.file_operation_service import _Job
from app.ui.drag_drop import DropRequest
from app.ui.main_window import MainWindow

APPLICATION = QApplication.instance() or QApplication([])


def wait(condition):
    deadline = time.monotonic() + 10
    while not condition():
        APPLICATION.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("Acceptance UI timed out")
        time.sleep(0.01)
    APPLICATION.processEvents()


class AcceptanceUiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.folder = self.root / "folder"
        self.folder.mkdir()
        self.source = self.root / "test.txt"
        self.source.write_text("fixture", encoding="utf-8")
        self.window = MainWindow(self.root / "state/db.sqlite3", SafetyPolicy([]), initial_location=self.root)
        self.window.show()
        wait(lambda: self.window.quick_sort.initialized and not self.window.quick_sort.busy and self.window.explorer.model is not None)
        wait(lambda: self.window.explorer.model.rowCount(self.window.explorer.details.rootIndex()) == 3)

    def tearDown(self):
        QThreadPool.globalInstance().waitForDone()
        APPLICATION.processEvents()
        self.window.close()
        self.window.deleteLater()
        APPLICATION.processEvents()
        self.temporary.cleanup()

    def test_actual_viewport_gesture_starts_drag_in_both_views(self):
        explorer = self.window.explorer
        explorer.files_dropped.disconnect(self.window.quick_sort.request_drop)
        for mode in ("Details", "Grid"):
            explorer.set_view_mode(mode)
            view = explorer.active_view
            APPLICATION.processEvents()
            self.assertTrue(view.dragEnabled())
            self.assertTrue(view.viewport().acceptDrops())
            index = explorer.model.index(str(self.source))
            start = view.visualRect(index).center()
            end = start + QPoint(APPLICATION.startDragDistance() + 20, 0)
            QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
            with patch.object(view, "startDrag") as drag:
                move = QMouseEvent(QEvent.Type.MouseMove, QPointF(end), QPointF(view.viewport().mapToGlobal(end)), Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
                QApplication.sendEvent(view.viewport(), move)
                self.assertTrue(drag.called, mode)
            QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)

    def test_external_native_event_dispatch_in_both_views(self):
        explorer = self.window.explorer
        explorer.files_dropped.disconnect(self.window.quick_sort.request_drop)
        for mode in ("Details", "Grid"):
            explorer.set_view_mode(mode)
            view = explorer.active_view
            APPLICATION.processEvents()
            point = view.visualRect(explorer.model.index(str(self.folder))).center()
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(self.source))])
            received = []
            view.files_dropped.connect(received.append)
            # Disconnect the UI workflow: inspect intent, never confirm/mutate.
            for event in (
                    QDragEnterEvent(QPointF(point), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier),
                    QDragMoveEvent(QPointF(point), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier),
                    QDropEvent(QPointF(point), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier),
            ):
                QApplication.sendEvent(view.viewport(), event)
                self.assertTrue(event.isAccepted(), mode)
            wait(lambda received=received: bool(received))
            self.assertEqual(received[0].operation, "copy")

    def test_favorite_and_drive_targets_accept_folder_paths(self):
        for target, data in (
            (self.window.favorites.folders, {"folder_path": str(self.folder)}),
            (self.window.sidebar.drives, str(self.folder)),
        ):
            target.clear()
            item = QListWidgetItem("Fixture destination")
            item.setData(Qt.ItemDataRole.UserRole, data)
            target.addItem(item)
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(self.source))])
            event = QDropEvent(QPointF(target.visualItemRect(item).center()), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            self.assertIsNotNone(target._request(event))

    def test_missing_favorite_can_be_removed_without_navigation_error(self):
        panel = self.window.favorites
        repository = self.window.quick_sort.repository
        repository.save_favorite("Missing", str(self.folder))
        panel.set_rows(repository.favorites())
        self.folder.rmdir()
        with patch("app.ui.favorites_panel.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes) as question:
            panel._activate(panel.folders.item(0))
            wait(lambda: not panel.busy and panel.folders.count() == 0)
        self.assertEqual(question.call_count, 1)
        self.assertEqual(self.window.browser.current, self.root)

    def test_refresh_deleted_current_folder_recovers_without_second_dialog(self):
        self.window.browser.navigate(str(self.folder))
        wait(lambda: self.window.browser.current == self.folder)
        self.folder.rmdir()
        with patch("app.ui.main_window.QMessageBox.warning") as warning:
            self.window._refresh()
            wait(lambda: self.window.browser.current == self.root)
        warning.assert_not_called()

    def test_destination_removed_during_confirmation_reports_once_and_retains_original(self):
        panel = self.window.quick_sort
        reports = []
        def confirm():
            self.folder.rmdir()
            return QDialog.DialogCode.Accepted
        with patch("app.ui.quick_sort_panel.TransferConfirmationDialog") as dialog, patch.object(panel, "_report", side_effect=lambda title, text: reports.append(text)), patch("app.ui.main_window.QMessageBox.warning") as warning:
            dialog.return_value.exec.side_effect = confirm
            dialog.return_value.decisions.return_value = ["copy"]
            panel.request_drop(DropRequest((str(self.source),), str(self.folder), "copy", False))
            wait(lambda: bool(reports) and not panel.busy)
            wait(lambda: not self.window.browser._workers)
        self.assertEqual(len(reports), 1)
        self.assertIn("Destination folder no longer exists", reports[0])
        self.assertTrue(self.source.exists())
        warning.assert_not_called()

    def test_cancel_and_exit_wait_for_worker_and_show_current_progress(self):
        panel = self.window.quick_sort
        release = Event()
        started = Event()
        def work(progress):
            started.set()
            progress("Copying fixture: 10/100 bytes")
            release.wait(5)
        panel.run_action(work, "Copying fixture", lambda result: None, cancellable=True, title="Copy")
        try:
            wait(started.is_set)
            with patch("app.ui.main_window.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
                self.window.close()
            self.assertTrue(panel.runner.cancel.is_set())
            self.assertTrue(self.window.isVisible())
            self.assertIn("Cancelling after the current file", panel.progress_dialog.labelText())
            self.assertEqual(panel.progress_dialog.windowTitle(), "Copy")
        finally:
            release.set()
        wait(lambda: not self.window.isVisible())

    def test_validation_rejections_log_without_unexpected_traceback(self):
        def rejected(progress):
            raise ValueError("Protected location")
        with self.assertLogs("app.services.file_operation_service", level="WARNING") as logs:
            _Job("plan", rejected).run()
        self.assertIn("Protected location", logs.output[0])
        self.assertIsNone(logs.records[0].exc_info)
