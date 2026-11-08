"""Compose the main interface without accessing user files."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QSplitter, QVBoxLayout, QWidget

from app.ui.file_explorer import FileExplorerWidget
from app.ui.navigation_bar import NavigationBar
from app.ui.preview_panel import PreviewPanel
from app.ui.sidebar import SidebarWidget


class MainWindow(QMainWindow):
    """Coordinate presentation widgets and their interface-only actions."""

    def __init__(self) -> None:
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
        for panel in (self.sidebar, self.explorer, self.preview):
            self.splitter.addWidget(panel)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([220, 660, 320])
        layout.addWidget(self.splitter, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Interface foundation | File browsing is not available yet")
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
        self.sidebar.location_selected.connect(self._select_location)
        self.sidebar.locations.setCurrentRow(0)

    def _select_location(self, location: str) -> None:
        self.explorer.set_location(location)
        self.navigation.address_field.setText(location)

    def _set_preview_visible(self, visible: bool) -> None:
        if not visible:
            self._preview_sizes = self.splitter.sizes()
        self.preview.setVisible(visible)
        if visible and self._preview_sizes:
            self.splitter.setSizes(self._preview_sizes)
