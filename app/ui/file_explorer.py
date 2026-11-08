"""An empty details view for the interface foundation."""

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)


class FileExplorerWidget(QWidget):
    """Show the chosen location without enumerating its contents."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumWidth(280)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        self.location_label = QLabel("Home")
        self.location_label.setObjectName("panelHeading")
        layout.addWidget(self.location_label)
        message = QLabel("Folder contents will appear here when file browsing is available.")
        message.setWordWrap(True)
        layout.addWidget(message)
        self.details = QTreeWidget()
        self.details.setAccessibleName("File details")
        self.details.setHeaderLabels(["Name", "Type", "Size", "Date Modified"])
        self.details.setRootIsDecorated(False)
        self.details.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.details.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.details)

    def set_location(self, location: str) -> None:
        """Update the display label only; this does not navigate the filesystem."""
        self.location_label.setText(location)
