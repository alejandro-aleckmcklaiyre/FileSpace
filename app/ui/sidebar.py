"""Scrollable location choices; no paths are accessed here."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QScrollArea, QVBoxLayout, QWidget

from app.services.drive_service import available_drives, standard_locations


class SidebarWidget(QScrollArea):
    """Report selected location labels to the main window."""

    location_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumWidth(160)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        heading = QLabel("LOCATIONS")
        heading.setObjectName("sectionHeading")
        layout.addWidget(heading)
        self.locations = QListWidget()
        self.locations.setAccessibleName("Locations")
        for name, path in standard_locations():
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path or "Location unavailable")
            self.locations.addItem(item)
        self.locations.setFixedHeight(210)
        self.locations.currentItemChanged.connect(
            lambda current, previous: self._request_location(current) if current else None
        )
        self.locations.itemActivated.connect(self._request_location)
        layout.addWidget(self.locations)

        heading = QLabel("DRIVES")
        heading.setObjectName("sectionHeading")
        layout.addWidget(heading)
        self.drives = QListWidget()
        self.drives.setAccessibleName("Available drives")
        self.drives.currentItemChanged.connect(
            lambda current, previous: self._request_location(current) if current else None
        )
        self.drives.itemActivated.connect(self._request_location)
        layout.addWidget(self.drives)
        self.refresh_drives()

        for title, message in (("FAVORITES", "No favorite folders yet."),):
            label = QLabel(title)
            label.setObjectName("sectionHeading")
            layout.addWidget(label)
            description = QLabel(message)
            description.setWordWrap(True)
            layout.addWidget(description)
            layout.addSpacing(16)
        self.content_layout = layout
        layout.addStretch()
        self.setWidget(content)

    def _request_location(self, item: QListWidgetItem) -> None:
        self.location_selected.emit(item.data(Qt.ItemDataRole.UserRole) or "")

    def refresh_drives(self) -> None:
        self.drives.clear()
        for name, path in available_drives():
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self.drives.addItem(item)
        self.drives.setFixedHeight(max(70, min(180, self.drives.count() * 32 + 8)))

    def fit_lists(self) -> None:
        """Let the outer sidebar scroll instead of clipping standard locations."""
        for widget in (self.locations, self.drives):
            widget.ensurePolished()
            height = sum(widget.sizeHintForRow(row) for row in range(widget.count()))
            widget.setFixedHeight(max(40, height + 2 * widget.frameWidth() + 4))
