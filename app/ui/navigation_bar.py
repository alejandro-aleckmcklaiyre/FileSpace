"""Navigation controls and the preview visibility toggle."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.services.search_service import CATEGORIES


class NavigationBar(QWidget):
    """Expose preview visibility without performing filesystem operations."""

    preview_toggled = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        layout = QHBoxLayout()
        outer.addLayout(layout)
        self.buttons: dict[str, QPushButton] = {}
        for title in ("Back", "Forward", "Up", "Refresh"):
            button = QPushButton(title)
            button.setEnabled(False)
            button.setToolTip(title)
            self.buttons[title] = button
            layout.addWidget(button)

        self.address_field = QLineEdit()
        self.address_field.setPlaceholderText("Select a location")
        self.address_field.setAccessibleName("Address")
        self.address_field.setToolTip("Enter a folder path and press Enter.")
        layout.addWidget(self.address_field, 2)

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search files")
        self.search_field.setAccessibleName("Search files")
        self.search_field.setClearButtonEnabled(True)
        self.search_field.setToolTip("Match filenames in the current folder only; subfolders are not scanned.")
        layout.addWidget(self.search_field, 1)

        self.preview_button = QPushButton("Preview")
        self.preview_button.setCheckable(True)
        self.preview_button.setChecked(True)
        self.preview_button.setToolTip("Show or hide the preview panel.")
        self.preview_button.toggled.connect(self.preview_toggled.emit)
        layout.addWidget(self.preview_button)
        filters = QHBoxLayout()
        self.category = QComboBox()
        self.category.addItems(["All files", *CATEGORIES])
        self.category.setAccessibleName("File category")
        self.extensions = QLineEdit()
        self.extensions.setPlaceholderText("Extensions: .jpg, .png")
        self.extensions.setAccessibleName("Extension filter")
        self.extensions.setClearButtonEnabled(True)
        self.extensions.setToolTip("Comma-separated extensions; combine with the category and search filters.")
        self.sort_column = QComboBox()
        for text, column in (("Name", 0), ("Size", 1), ("Type", 2), ("Date modified", 3)):
            self.sort_column.addItem(text, column)
        self.sort_column.setAccessibleName("Sort by")
        self.descending = QPushButton("Descending")
        self.descending.setCheckable(True)
        self.view_mode = QComboBox()
        self.view_mode.addItems(["Details", "Grid"])
        self.view_mode.setAccessibleName("View mode")
        filters.addWidget(self.category)
        filters.addWidget(self.extensions, 1)
        filters.addWidget(QLabel("Sort"))
        filters.addWidget(self.sort_column)
        filters.addWidget(self.descending)
        filters.addWidget(self.view_mode)
        outer.addLayout(filters)
