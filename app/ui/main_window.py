"""Compose the read-only browsing interface."""

from PySide6.QtCore import Qt, QTimer
from pathlib import Path
from PySide6.QtWidgets import QMainWindow, QMessageBox, QSplitter, QVBoxLayout, QWidget

from app.services.file_browser_service import FileBrowserService
from app.services.drive_service import standard_locations
from app.database.connection import default_database_path
from app.database.repository import Repository
from app.filesystem.safety import default_policy, SafetyPolicy
from app.ui.quick_sort_panel import QuickSortPanel

from app.ui.file_explorer import FileExplorerWidget
from app.ui.navigation_bar import NavigationBar
from app.ui.preview_panel import PreviewPanel
from app.ui.sidebar import SidebarWidget


class MainWindow(QMainWindow):
    """Connect presentation widgets to read-only navigation services."""

    def __init__(self, database_path: Path | None = None, safety_policy: SafetyPolicy | None = None) -> None:
        super().__init__()
        self.setWindowTitle("FileSpace")
        self.resize(1200, 800)
        self.setMinimumSize(900, 480)
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.navigation = NavigationBar()
        layout.addWidget(self.navigation)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.sidebar = SidebarWidget()
        self.explorer = FileExplorerWidget()
        self.preview = PreviewPanel()
        database_path = database_path or default_database_path()
        self.quick_sort = QuickSortPanel(
            Repository(database_path), safety_policy or default_policy(database_path),
            self.explorer.selected_paths, self.sidebar,
        )
        self.sidebar.content_layout.insertWidget(self.sidebar.content_layout.count() - 1, self.quick_sort)
        self._quick_sort_busy = False
        for panel in (self.sidebar, self.explorer, self.preview):
            self.splitter.addWidget(panel)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([220, 660, 320])
        layout.addWidget(self.splitter, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Read-only file browsing")
        self.setStyleSheet(
            "QLabel#sectionHeading { font-weight: 600; margin-top: 8px; }"
            "QLabel#panelHeading { font-size: 18px; font-weight: 600; }"
            "QPushButton { padding: 6px 8px; }"
            "QLineEdit { padding: 6px; }"
            "QListWidget { border: none; }"
            "QListWidget::item { padding: 6px; }"
        )

        self._preview_sizes: list[int] = []
        self.navigation.preview_toggled.connect(self._set_preview_visible)
        self.browser = FileBrowserService(self)
        self.sidebar.location_selected.connect(self.browser.navigate)
        self.explorer.folder_requested.connect(self.browser.navigate)
        self.explorer.file_selected.connect(self._preview_selection)
        self.explorer.selection_count_changed.connect(self.quick_sort.update_selection_count)
        self.quick_sort.navigate_requested.connect(self.browser.navigate)
        self.quick_sort.busy_changed.connect(self._set_quick_sort_busy)
        self.quick_sort.files_changed.connect(self._refresh)
        self.quick_sort.transfer_requested.connect(self._prepare_transfer)
        self.browser.location_changed.connect(self._select_location)
        self.browser.navigation_failed.connect(self._navigation_failed)
        self.browser.busy_changed.connect(self._set_busy)
        for name, action in (
            ("Back", self.browser.back), ("Forward", self.browser.forward),
            ("Up", self.browser.up), ("Refresh", self._refresh),
        ):
            self.navigation.buttons[name].clicked.connect(action)
        self.navigation.address_field.returnPressed.connect(
            lambda: self.browser.navigate(self.navigation.address_field.text())
        )
        self.browser.navigate(standard_locations()[0][1])
        QTimer.singleShot(0, self.sidebar.fit_lists)

    def _select_location(self, location: str) -> None:
        self.explorer.set_location(location)
        self.navigation.address_field.setText(location)
        self._update_buttons()
        self.statusBar().showMessage("Read-only file browsing")

    def _update_buttons(self) -> None:
        current = self.browser.current
        self.navigation.buttons["Back"].setEnabled(self.browser.can_back)
        self.navigation.buttons["Forward"].setEnabled(self.browser.can_forward)
        self.navigation.buttons["Up"].setEnabled(current is not None and current.parent != current)
        self.navigation.buttons["Refresh"].setEnabled(current is not None)

    def _set_busy(self, busy: bool) -> None:
        self.statusBar().showMessage("Checking folder…" if busy else "Read-only file browsing")
        if busy:
            for button in self.navigation.buttons.values():
                button.setEnabled(False)
        else:
            self._update_buttons()

    def _navigation_failed(self, message: str) -> None:
        current = self.browser.current
        self.navigation.address_field.setText(str(current) if current else "")
        QMessageBox.warning(self, "Cannot open folder", message)

    def _refresh(self) -> None:
        self.sidebar.refresh_drives()
        self.sidebar.fit_lists()
        self.browser.refresh()

    def _set_preview_visible(self, visible: bool) -> None:
        if not visible:
            self._preview_sizes = self.splitter.sizes()
        self.preview.setVisible(visible)
        if visible and self._preview_sizes:
            self.splitter.setSizes(self._preview_sizes)

    def closeEvent(self, event) -> None:
        if self.quick_sort.busy:
            QMessageBox.information(self, "Quick Sort is active", "Wait for Quick Sort to finish. During a transfer, Cancel stops after the current file.")
            event.ignore()
            return
        self.preview.shutdown()
        super().closeEvent(event)

    def _preview_selection(self, path: str) -> None:
        if not self._quick_sort_busy:
            self.preview.select_file(path)

    def _set_quick_sort_busy(self, busy: bool) -> None:
        self._quick_sort_busy = busy
        for widget in (self.explorer, self.navigation, self.sidebar.locations, self.sidebar.drives):
            widget.setEnabled(not busy)
        if busy:
            self.preview.select_file("")

    def _prepare_transfer(self, plan, decisions) -> None:
        self.statusBar().showMessage("Closing active preview before transfer…")
        self.preview.release_for_transfer(lambda: self.quick_sort.execute(plan, decisions))
