"""Read-only directory details backed by Qt's asynchronous filesystem model."""

from PySide6.QtCore import QDir, QItemSelectionModel, QModelIndex, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileSystemModel,
    QHeaderView,
    QLabel,
    QListView,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.drag_drop import FileDragView, FileIconView, selected_file_rows
from app.ui.file_filter_model import FileFilterModel


class FileExplorerWidget(QWidget):
    """List metadata and request folder navigation without modifying files."""

    folder_requested = Signal(str)
    file_selected = Signal(str)
    selection_count_changed = Signal(int)
    files_dropped = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumWidth(280)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        self.location_label = QLabel("Home")
        self.location_label.setObjectName("panelHeading")
        layout.addWidget(self.location_label)
        self.result_label = QLabel()
        layout.addWidget(self.result_label)
        self.details = FileDragView()
        self.details.files_dropped.connect(self.files_dropped.emit)
        self.details.setAccessibleName("File details")
        self.details.setRootIsDecorated(False)
        self.details.setItemsExpandable(False)
        self.details.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.details.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.details.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.details.doubleClicked.connect(self._open_folder)
        self.grid = FileIconView()
        self.grid.setAccessibleName("File grid")
        self.grid.setViewMode(QListView.ViewMode.IconMode)
        self.grid.setResizeMode(QListView.ResizeMode.Adjust)
        self.grid.setMovement(QListView.Movement.Static)
        self.grid.setIconSize(QSize(64, 64))
        self.grid.setGridSize(QSize(140, 110))
        self.grid.setWordWrap(True)
        self.grid.setUniformItemSizes(True)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.grid.doubleClicked.connect(self._open_folder)
        self.grid.files_dropped.connect(self.files_dropped.emit)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.details)
        self.stack.addWidget(self.grid)
        layout.addWidget(self.stack)
        self.model: FileFilterModel | None = None
        self.source_model: QFileSystemModel | None = None
        self._filters = ("", "", "All files")
        self._sort = (0, Qt.SortOrder.AscendingOrder)

    @property
    def active_view(self):
        return self.stack.currentWidget()

    def set_view_mode(self, mode: str) -> None:
        paths = self.selected_paths()
        current = self.active_view.currentIndex()
        current_path = self.model.filePath(current) if self.model and current.isValid() else ""
        if self.model:
            self.active_view.clearSelection()
        self.stack.setCurrentWidget(self.grid if mode == "Grid" else self.details)
        if self.model:
            flags = QItemSelectionModel.SelectionFlag.Select
            if self.active_view is self.details:
                flags |= QItemSelectionModel.SelectionFlag.Rows
            for path in paths:
                self.active_view.selectionModel().select(self.model.index(path), flags)
            if current_path:
                self.active_view.selectionModel().setCurrentIndex(self.model.index(current_path), QItemSelectionModel.SelectionFlag.NoUpdate)
        if self.active_view.currentIndex().isValid():
            self.active_view.scrollTo(self.active_view.currentIndex())

    def set_filters(self, query: str, extensions: str, category: str) -> None:
        self._filters = (query, extensions, category)
        if self.model:
            self.model.set_filters(*self._filters)
            self.selection_count_changed.emit(len(self.selected_paths()))
            self._update_count()

    def sort_files(self, column: int, order) -> None:
        self._sort = (column, order)
        if self.model:
            self.model.sort(column, order)
            self.details.header().setSortIndicator(column, order)

    def set_location(self, location: str) -> None:
        """Replace the model to force a fresh directory listing on Refresh."""
        old_model = self.model
        old_source = self.source_model
        old_selection = self.details.selectionModel()
        sort_order = self._sort
        self.source_model = QFileSystemModel(self)
        self.source_model.setReadOnly(True)
        self.source_model.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot)
        self.source_model.setRootPath(location)
        self.model = FileFilterModel(self.source_model, self.source_model.rootPath(), self)
        self.model.set_filters(*self._filters)
        self.model.rowsInserted.connect(self._update_count)
        self.model.rowsRemoved.connect(self._update_count)
        self.source_model.directoryLoaded.connect(self._update_count)
        self.details.setModel(self.model)
        self.grid.setModel(self.model)
        shared_selection = QItemSelectionModel(self.model, self)
        self.details.setSelectionModel(shared_selection)
        self.grid.setSelectionModel(shared_selection)
        root = self.model.index(location)
        self.details.setRootIndex(root)
        self.grid.setRootIndex(root)
        shared_selection.currentChanged.connect(self._selection_changed)
        shared_selection.selectionChanged.connect(
            lambda selected, deselected: self.selection_count_changed.emit(len(self.selected_paths()))
        )
        self.file_selected.emit("")
        self.selection_count_changed.emit(0)
        header = self.details.header()
        # Native Qt order is Name, Size, Type, Date Modified.
        header.moveSection(header.visualIndex(2), 1)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.details.setSortingEnabled(True)
        self.sort_files(*sort_order)
        self.location_label.setText(location)
        self.location_label.setWordWrap(True)
        self._update_count()
        if old_model is not None:
            old_model.deleteLater()
        if old_source is not None:
            old_source.deleteLater()
        if old_selection is not None:
            old_selection.deleteLater()

    def _update_count(self, *args) -> None:
        if self.model is not None:
            count = self.model.rowCount(self.active_view.rootIndex())
            self.result_label.setText(f"{count} item(s) shown in this folder" if count else "No matching items in this folder")

    def _open_folder(self, index: QModelIndex) -> None:
        if self.model is not None:
            index = index.siblingAtColumn(0)
            if self.model.isDir(index):
                self.folder_requested.emit(self.model.filePath(index))

    def _selection_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        if self.model is not None and current.isValid() and not self.model.isDir(current):
            self.file_selected.emit(self.model.filePath(current.siblingAtColumn(0)))
        else:
            self.file_selected.emit("")

    def selected_paths(self) -> list[str]:
        if self.model is None:
            return []
        return [self.model.filePath(index) for index in selected_file_rows(self.active_view)]
