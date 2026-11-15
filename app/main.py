"""Application startup and Qt event loop."""

import argparse
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.database.connection import default_database_path
from app.diagnostics import configure_logging, install_exception_handler
from app.runtime import resource_path
from app.ui.main_window import MainWindow
from app.version import VERSION


def main() -> int:
    """Create the application and keep it running until its windows close."""
    parser = argparse.ArgumentParser(description="FileSpace desktop file manager")
    parser.add_argument("--smoke-test", type=Path, metavar="NEW_REPORT_JSON", help="Run isolated checks using temporary generated fixtures")
    parser.add_argument("--version", action="version", version=VERSION)
    arguments = parser.parse_args()
    application = QApplication([sys.argv[0]])
    application.setApplicationName("FileSpace")
    application.setApplicationVersion(VERSION)
    application.setWindowIcon(QIcon(str(resource_path("icons/filespace.ico"))))
    if arguments.smoke_test is not None:
        from app.packaging_smoke import run
        return run(application, arguments.smoke_test)
    log_path = configure_logging(default_database_path().parent)
    install_exception_handler(application, log_path)
    window = MainWindow()
    window.show()
    return application.exec()
