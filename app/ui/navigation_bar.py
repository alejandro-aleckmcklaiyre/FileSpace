"""Navigation controls, ready for later browsing integration."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget


class NavigationBar(QWidget):
    """Expose preview visibility without performing filesystem operations."""

    preview_toggled = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        for title in ("Back", "Forward", "Up", "Refresh"):
            button = QPushButton(title)
            button.setEnabled(False)
            button.setToolTip("Available when file browsing is implemented.")
            layout.addWidget(button)

        self.address_field = QLineEdit()
        self.address_field.setPlaceholderText("Select a location")
        self.address_field.setAccessibleName("Address")
        self.address_field.setReadOnly(True)
        self.address_field.setToolTip("Direct path entry will be available with file browsing.")
        layout.addWidget(self.address_field, 2)

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search files")
        self.search_field.setAccessibleName("Search files")
        self.search_field.setEnabled(False)
        self.search_field.setToolTip("Search will be available in a later milestone.")
        layout.addWidget(self.search_field, 1)

        self.preview_button = QPushButton("Preview")
        self.preview_button.setCheckable(True)
        self.preview_button.setChecked(True)
        self.preview_button.setToolTip("Show or hide the preview panel.")
        self.preview_button.toggled.connect(self.preview_toggled.emit)
        layout.addWidget(self.preview_button)
