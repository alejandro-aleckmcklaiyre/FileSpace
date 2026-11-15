"""Persistent favorite folders; removing a favorite never touches the folder."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.filesystem.path_validator import validate_directory
from app.services.file_operation_service import FileOperationService


class FavoritesPanel(QWidget):
    navigate_requested = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, repository, current_location, parent=None):
        super().__init__(parent)
        self.repository, self.current_location = repository, current_location
        self.busy = False
        self.runner = FileOperationService(self)
        self.runner.finished.connect(self._finished)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = QLabel("FAVORITES")
        heading.setObjectName("sectionHeading")
        layout.addWidget(heading)
        self.folders = QListWidget()
        self.folders.setAccessibleName("Favorite folders")
        self.folders.setFixedHeight(70)
        self.folders.itemClicked.connect(lambda item: self.navigate_requested.emit(item.data(Qt.ItemDataRole.UserRole)["folder_path"]))
        self.folders.itemActivated.connect(lambda item: self.navigate_requested.emit(item.data(Qt.ItemDataRole.UserRole)["folder_path"]))
        layout.addWidget(self.folders)
        controls = QHBoxLayout()
        add = QPushButton("Add current")
        add.clicked.connect(lambda: self.add_path(self.current_location()))
        remove = QPushButton("Remove")
        remove.clicked.connect(self.remove_selected)
        controls.addWidget(add)
        controls.addWidget(remove)
        layout.addLayout(controls)

    def set_rows(self, rows) -> None:
        self.folders.clear()
        for row in rows:
            item = QListWidgetItem(row["name"])
            item.setToolTip(row["folder_path"])
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.folders.addItem(item)
        height = sum(self.folders.sizeHintForRow(row) for row in range(self.folders.count()))
        self.folders.setFixedHeight(max(45, min(160, height + 8)))

    def _start(self, function) -> None:
        if self.busy:
            return
        self.busy = True
        self.busy_changed.emit(True)
        self.runner.start("favorites", function)

    def add_path(self, value) -> None:
        if not value or self.busy:
            return
        path = str(value)
        name, accepted = QInputDialog.getText(self, "Add favorite", "Name", text=Path(path).name or path)
        if not accepted:
            return
        def save(progress):
            folder = validate_directory(path)
            self.repository.save_favorite(name, str(folder))
            return self.repository.favorites()
        self._start(save)

    def remove_selected(self) -> None:
        item = self.folders.currentItem()
        if item is not None:
            favorite_id = item.data(Qt.ItemDataRole.UserRole)["id"]
            def remove(progress):
                self.repository.delete_favorite(favorite_id)
                return self.repository.favorites()
            self._start(remove)

    def _finished(self, name, rows, error) -> None:
        self.busy = False
        self.busy_changed.emit(False)
        if error:
            QMessageBox.warning(self, "Favorite could not be saved", error)
        else:
            self.set_rows(rows)
