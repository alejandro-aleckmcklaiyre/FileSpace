"""Bounded, local error logs for a Windows application without a console."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(data_directory: Path) -> Path:
    folder = data_directory / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "filespace.log"
    handler = RotatingFileHandler(path, maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("app")
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    return path


def install_exception_handler(application, log_path: Path) -> None:
    from PySide6.QtWidgets import QMessageBox

    def report(kind, error, traceback):
        if issubclass(kind, KeyboardInterrupt):
            application.quit()
            return
        logging.getLogger(__name__).critical("Unhandled application error", exc_info=(kind, error, traceback))
        QMessageBox.critical(
            None, "FileSpace encountered a problem",
            f"An unexpected error occurred. Review any active operation before retrying.\n\nDetails: {error}\n\nLog: {log_path}",
        )

    sys.excepthook = report
