"""The application window foundation; navigation comes in later milestones."""

from PySide6.QtWidgets import QMainWindow, QWidget


class MainWindow(QMainWindow):
    """A basic, resizable FileSpace window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FileSpace")
        self.resize(1200, 800)
        self.setCentralWidget(QWidget(self))
