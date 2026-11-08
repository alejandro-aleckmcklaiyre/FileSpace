"""Preview empty state, awaiting the preview engine milestone."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PreviewPanel(QWidget):
    """Explain the currently unavailable preview functionality."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumWidth(200)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        heading = QLabel("Preview")
        heading.setObjectName("panelHeading")
        layout.addWidget(heading)
        layout.addStretch()
        message = QLabel("No file selected\n\nFile previews will be available in a later milestone.")
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(message)
        layout.addStretch()
