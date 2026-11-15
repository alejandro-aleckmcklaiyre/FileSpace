"""Compose the read-only browsing interface."""

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtWidgets import QMainWindow, QMessageBox, QSplitter, QVBoxLayout, QWidget

from app.database.connection import default_database_path
from app.database.repository import Repository
from app.filesystem.safety import SafetyPolicy, default_policy
from app.services.drive_service import standard_locations
from app.services.file_browser_service import FileBrowserService
from app.ui.favorites_panel import FavoritesPanel
from app.ui.file_actions import FileActions
from app.ui.file_explorer import FileExplorerWidget
from app.ui.navigation_bar import NavigationBar
from app.ui.preview_panel import PreviewPanel
from app.ui.quick_sort_panel import QuickSortPanel
from app.ui.sidebar import SidebarWidget


class MainWindow(QMainWindow):
    """Connect presentation widgets to read-only navigation services."""

    def __init__(self, database_path: Path | None = None, safety_policy: SafetyPolicy | None = None, initial_location: Path | None = None) -> None:
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
        for view in (self.explorer.details, self.explorer.grid):
            view.drop_policy = self.quick_sort.service.policy
            view.quick_sort_key_handler = self.quick_sort.activate_keyword
        self.favorites = FavoritesPanel(self.quick_sort.repository, lambda: self.browser.current, self.sidebar)
        for target in (self.favorites.folders, self.sidebar.locations, self.sidebar.drives):
            target.drop_policy = self.quick_sort.service.policy
            target.files_dropped.connect(self.quick_sort.request_drop)
        self.sidebar.content_layout.insertWidget(self.sidebar.content_layout.count() - 1, self.favorites)
        self.sidebar.content_layout.insertWidget(self.sidebar.content_layout.count() - 1, self.quick_sort)
        self._quick_sort_busy = False
        self._close_when_idle = False
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
        self.file_actions = FileActions(self)
        self.view_settings = QSettings(str(database_path.with_suffix(".ini")), QSettings.Format.IniFormat)
        saved_view = str(self.view_settings.value("view/mode", "Details"))
        self.navigation.view_mode.setCurrentText(saved_view if saved_view in {"Details", "Grid"} else "Details")
        self.explorer.set_view_mode(self.navigation.view_mode.currentText())
        self.filter_timer = QTimer(self)
        self.filter_timer.setSingleShot(True)
        self.filter_timer.setInterval(150)
        self.filter_timer.timeout.connect(self._apply_filters)
        self.navigation.search_field.textChanged.connect(lambda text: self.filter_timer.start())
        self.navigation.extensions.textChanged.connect(lambda text: self.filter_timer.start())
        self.navigation.category.currentTextChanged.connect(lambda text: self._apply_filters())
        self.navigation.sort_column.currentIndexChanged.connect(self._sort_files)
        self.navigation.descending.toggled.connect(self._sort_files)
        self.navigation.view_mode.currentTextChanged.connect(self._switch_view)
        self.explorer.details.header().sortIndicatorChanged.connect(self._header_sort_changed)
        self.quick_sort.favorites_loaded.connect(self.favorites.set_rows)
        self.favorites.navigate_requested.connect(self.browser.navigate)
        self.favorites.busy_changed.connect(lambda busy: self._set_quick_sort_busy(self.quick_sort.busy))
        self.sidebar.location_selected.connect(self.browser.navigate)
        self.explorer.folder_requested.connect(self.browser.navigate)
        self.explorer.file_selected.connect(self._preview_selection)
        self.explorer.selection_count_changed.connect(self.quick_sort.update_selection_count)
        self.explorer.files_dropped.connect(self.quick_sort.request_drop)
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
        self.browser.navigate(str(initial_location) if initial_location is not None else standard_locations()[0][1])
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
        if self.quick_sort.busy or self.favorites.busy:
            if self.quick_sort.busy and self.quick_sort.cancellable:
                if not self._close_when_idle and QMessageBox.question(
                    self, f"{self.quick_sort.action_title} is active",
                    "Cancel remaining files and exit after the current file finishes safely? "
                    "FileSpace will stay open until verification and staging cleanup complete.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                ) == QMessageBox.StandardButton.Yes:
                    self._close_when_idle = True
                    self.quick_sort.request_cancel()
            else:
                QMessageBox.information(self, "File operation is active", "Wait for the current file operation to finish before exiting.")
            event.ignore()
            return
        self.preview.shutdown()
        self.view_settings.sync()
        super().closeEvent(event)

    def _preview_selection(self, path: str) -> None:
        if not self._quick_sort_busy:
            self.preview.select_file(path)

    def _set_quick_sort_busy(self, busy: bool) -> None:
        self._quick_sort_busy = busy or self.favorites.busy
        for widget in (self.explorer, self.navigation, self.sidebar.locations, self.sidebar.drives):
            widget.setEnabled(not self._quick_sort_busy)
        self.favorites.setEnabled(not busy and not self.favorites.busy)
        self.quick_sort.setEnabled(not self.favorites.busy)
        if self._quick_sort_busy:
            self.preview.select_file("")
        elif self._close_when_idle:
            QTimer.singleShot(0, self.close)

    def _prepare_transfer(self, plan, decisions) -> None:
        self.statusBar().showMessage("Closing active preview before transfer…")
        self.preview.release_for_transfer(lambda: self.quick_sort.execute(plan, decisions))

    def _apply_filters(self) -> None:
        self.explorer.set_filters(self.navigation.search_field.text(), self.navigation.extensions.text(), self.navigation.category.currentText())

    def _sort_files(self, *args) -> None:
        order = Qt.SortOrder.DescendingOrder if self.navigation.descending.isChecked() else Qt.SortOrder.AscendingOrder
        self.explorer.sort_files(self.navigation.sort_column.currentData(), order)

    def _header_sort_changed(self, column, order) -> None:
        for widget in (self.navigation.sort_column, self.navigation.descending):
            widget.blockSignals(True)
        self.navigation.sort_column.setCurrentIndex(self.navigation.sort_column.findData(column))
        self.navigation.descending.setChecked(order == Qt.SortOrder.DescendingOrder)
        for widget in (self.navigation.sort_column, self.navigation.descending):
            widget.blockSignals(False)
        self.explorer._sort = (column, order)

    def _switch_view(self, mode: str) -> None:
        self.explorer.set_view_mode(mode)
        self.view_settings.setValue("view/mode", mode)
        self.view_settings.sync()
