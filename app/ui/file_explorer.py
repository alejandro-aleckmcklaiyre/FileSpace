"""Read-only directory details backed by Qt's asynchronous filesystem model."""

from PySide6.QtCore import QDir, QModelIndex, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QFileSystemModel,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


class FileExplorerWidget(QWidget):
    """List metadata and request folder navigation without modifying files."""

    folder_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumWidth(280)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        self.location_label = QLabel("Home")
        self.location_label.setObjectName("panelHeading")
        layout.addWidget(self.location_label)
        self.details = QTreeView()
        self.details.setAccessibleName("File details")
        self.details.setRootIsDecorated(False)
        self.details.setItemsExpandable(False)
        self.details.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.details.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.details.setDragEnabled(False)
        self.details.setAcceptDrops(False)
        self.details.doubleClicked.connect(self._open_folder)
        self.model: QFileSystemModel | None = None
        layout.addWidget(self.details)

    def set_location(self, location: str) -> None:
        """Replace the model to force a fresh directory listing on Refresh."""
        old_model = self.model
        self.model = QFileSystemModel(self)
        self.model.setReadOnly(True)
        self.model.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot)
        self.details.setModel(self.model)
        self.details.setRootIndex(self.model.setRootPath(location))
        header = self.details.header()
        # Native Qt order is Name, Size, Type, Date Modified.
        header.moveSection(header.visualIndex(2), 1)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.location_label.setText(location)
        self.location_label.setWordWrap(True)
        if old_model is not None:
            old_model.deleteLater()

    def _open_folder(self, index: QModelIndex) -> None:
        if self.model is not None:
            index = index.siblingAtColumn(0)
            if self.model.isDir(index):
                self.folder_requested.emit(self.model.filePath(index))
