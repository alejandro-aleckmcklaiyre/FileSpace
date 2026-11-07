"""Application startup and Qt event loop."""

import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def main() -> int:
    """Create the application and keep it running until its windows close."""
    application = QApplication(sys.argv)
    application.setApplicationName("FileSpace")
    window = MainWindow()
    window.show()
    return application.exec()
