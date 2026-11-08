"""Worker-based preview dispatch with bounded concurrency and stale-result rejection."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from app.previews.image import read_image
from app.previews.office import read_office
from app.previews.pdf import read_pdf
from app.previews.text import read_text


@dataclass
class PreviewResult:
    path: str
    kind: str = "message"
    content: object = ""
    metadata: str = ""
    page: int = 0
    pages: int = 0


def load_preview(value: str, page: int = 0) -> PreviewResult:
    path = Path(value)
    result = PreviewResult(value, page=page)
    try:
        info = path.stat()
        if not path.is_file():
            result.content = "Select a file to preview."
            return result
        result.metadata = (
            f"Name: {path.name}\nExtension: {path.suffix or '(none)'}\n"
            f"Size: {info.st_size:,} bytes\nModified: {datetime.fromtimestamp(info.st_mtime):%Y-%m-%d %H:%M:%S}\n"
            f"Location: {path.parent}"
        )
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}:
            result.kind = "image"
            result.content, dimensions = read_image(path)
            result.metadata += "\n" + dimensions
        elif suffix == ".pdf":
            result.kind = "pdf"
            result.content, result.pages = read_pdf(path, page)
        elif suffix in {".txt", ".log", ".csv"}:
            result.kind, result.content = "text", read_text(path)
        elif suffix in {".docx", ".xlsx", ".pptx"}:
            result.kind, result.content = read_office(path)
        elif suffix in {".mp4", ".mkv", ".mov", ".avi"}:
            result.kind, result.content = "video", value
        else:
            result.content = "Preview is not available for this file type."
    except Exception as error:
        # Third-party parsers expose several exception types. Contain failures
        # at the worker boundary so malformed documents cannot crash the UI.
        result.kind = "message"
        result.content = f"Cannot preview this file: {error}"
    return result


class _Signals(QObject):
    finished = Signal(int, object)


class _PreviewWorker(QRunnable):
    def __init__(self, token: int, path: str, page: int) -> None:
        super().__init__()
        self.token, self.path, self.page = token, path, page
        self.signals = _Signals()

    @Slot()
    def run(self) -> None:
        self.signals.finished.emit(self.token, load_preview(self.path, self.page))


class FilePreviewService(QObject):
    ready = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._token = 0
        self._active: _PreviewWorker | None = None
        self._pending: tuple[int, str, int] | None = None

    def cancel(self) -> None:
        """Invalidate current work; running parser calls finish in the background."""
        self._token += 1
        self._pending = None

    @property
    def idle(self) -> bool:
        return self._active is None and self._pending is None

    def request(self, path: str, page: int = 0) -> None:
        self._token += 1
        self._pending = (self._token, path, page)
        self._start_pending()

    def _start_pending(self) -> None:
        if self._active is not None or self._pending is None:
            return
        self._active = _PreviewWorker(*self._pending)
        self._pending = None
        self._active.signals.finished.connect(self._finished)
        QThreadPool.globalInstance().start(self._active)

    @Slot(int, object)
    def _finished(self, token: int, result: PreviewResult) -> None:
        self._active = None
        if token == self._token:
            self.ready.emit(result)
        self._start_pending()
