"""Read-only browsing regression checks using disposable test folders."""

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QAbstractItemView

from app.filesystem.path_validator import validate_directory
from app.services.file_browser_service import FileBrowserService
from app.ui.main_window import MainWindow


APPLICATION = QApplication.instance() or QApplication([])


def wait_until(condition) -> None:
    deadline = time.monotonic() + 10
    while not condition():
        APPLICATION.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("Timed out waiting for directory loading")
        time.sleep(0.01)
    APPLICATION.processEvents()


class BrowsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.child = self.root / "folder"
        self.child.mkdir()
        (self.root / "sample.txt").write_text("unchanged", encoding="utf-8")

    def tearDown(self) -> None:
        QThreadPool.globalInstance().waitForDone()
        APPLICATION.processEvents()
        self.temp.cleanup()

    def navigate(self, browser, value) -> None:
        completed = []
        browser.location_changed.connect(completed.append)
        browser.navigate(str(value))
        wait_until(lambda: bool(completed))
        browser.location_changed.disconnect(completed.append)

    def test_validation(self) -> None:
        self.assertEqual(validate_directory("folder", self.root), self.child)
        for value in ("", str(self.root / "missing"), str(self.root / "sample.txt")):
            with self.assertRaises((OSError, ValueError)):
                validate_directory(value)
        with patch("app.filesystem.path_validator.os.scandir", side_effect=PermissionError("Denied")):
            with self.assertRaises(PermissionError):
                validate_directory(str(self.root))

    def test_history_and_failure(self) -> None:
        browser = FileBrowserService()
        self.navigate(browser, self.root)
        self.navigate(browser, self.child)
        browser.back()
        wait_until(lambda: browser.current == self.root)
        self.assertTrue(browser.can_forward)
        browser.forward()
        wait_until(lambda: browser.current == self.child)
        browser.back()
        wait_until(lambda: browser.current == self.root)
        errors = []
        browser.navigation_failed.connect(errors.append)
        browser.navigate(str(self.root / "missing"))
        wait_until(lambda: bool(errors))
        self.assertEqual(browser.current, self.root)
        self.assertTrue(browser.can_forward)
        other = self.root / "other"
        other.mkdir()
        self.navigate(browser, other)
        self.assertFalse(browser.can_forward)
        self.assertNotIn(self.child, browser.history)

    def test_root_and_stale_results(self) -> None:
        browser = FileBrowserService()
        root = Path(self.root.anchor)
        self.navigate(browser, root)
        browser.up()
        self.assertEqual(browser.current, root)
        browser.navigate(str(self.child))
        browser.navigate(str(self.root))
        wait_until(lambda: not browser._workers)
        self.assertEqual(browser.current, self.root)
        self.assertNotIn(self.child, browser.history)

    def test_window_listing_refresh_and_read_only(self) -> None:
        with patch("app.ui.main_window.standard_locations", return_value=[("Home", str(self.root))]):
            window = MainWindow(database_path=self.root / "state" / "test.sqlite3")
        window.show()
        try:
            wait_until(lambda: window.browser.current == self.root)
            view = window.explorer
            wait_until(lambda: window.quick_sort.initialized and not window.quick_sort.busy)
            wait_until(lambda: view.model.rowCount(view.details.rootIndex()) == 3)
            self.assertTrue(view.model.isReadOnly())
            self.assertEqual(view.details.editTriggers(), QAbstractItemView.EditTrigger.NoEditTriggers)
            self.assertEqual(view.details.dragDropMode(), QAbstractItemView.DragDropMode.DragDrop)
            self.assertTrue(view.details.dragEnabled())
            self.assertTrue(view.details.acceptDrops())
            view.details.setCurrentIndex(view.model.index(str(self.root / "sample.txt")))
            wait_until(lambda: window.preview.text.toPlainText() == "unchanged")
            view.details.doubleClicked.emit(view.model.index(str(self.child)))
            wait_until(lambda: window.browser.current == self.child)
            self.assertEqual(window.navigation.address_field.text(), str(self.child))
            window.navigation.buttons["Back"].click()
            wait_until(lambda: window.browser.current == self.root)
            (self.root / "new.txt").write_text("new", encoding="utf-8")
            previous = view.model
            window.navigation.buttons["Refresh"].click()
            wait_until(lambda: view.model is not previous)
            wait_until(lambda: view.model.rowCount(view.details.rootIndex()) == 4)
            window.navigation.preview_button.click()
            self.assertFalse(window.preview.isVisible())
            window.navigation.preview_button.click()
            self.assertTrue(window.preview.isVisible())
            self.assertEqual((self.root / "sample.txt").read_text(encoding="utf-8"), "unchanged")
        finally:
            window.close()
            window.deleteLater()
            APPLICATION.processEvents()


if __name__ == "__main__":
    unittest.main()
