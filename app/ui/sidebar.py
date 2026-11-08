"""Scrollable location choices; no paths are accessed here."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QListWidget, QScrollArea, QVBoxLayout, QWidget


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
        self.locations.addItems(
            ["Home", "Desktop", "Documents", "Downloads", "Pictures", "Videos"]
        )
        self.locations.setFixedHeight(210)
        self.locations.currentTextChanged.connect(self.location_selected.emit)
        layout.addWidget(self.locations)

        for title, message in (
            ("DRIVES", "Drive detection is coming soon."),
            ("FAVORITES", "No favorite folders yet."),
            ("QUICK SORT", "No destinations configured."),
        ):
            label = QLabel(title)
            label.setObjectName("sectionHeading")
            layout.addWidget(label)
            description = QLabel(message)
            description.setWordWrap(True)
            layout.addWidget(description)
            layout.addSpacing(16)
        layout.addStretch()
        self.setWidget(content)
