"""Single-job worker runner with cooperative transfer cancellation."""

from threading import Event
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class _Signals(QObject):
    done = Signal(str, object, str)
    progress = Signal(str)


class _Job(QRunnable):
    def __init__(self, name: str, function: Callable) -> None:
        super().__init__()
        self.name, self.function = name, function
        self.signals = _Signals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.function(self.signals.progress.emit)
        except Exception as error:
            self.signals.done.emit(self.name, None, str(error))
        else:
            self.signals.done.emit(self.name, result, "")


class FileOperationService(QObject):
    finished = Signal(str, object, str)
    progress = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.cancel = Event()
        self._job: _Job | None = None

    @property
    def busy(self) -> bool:
        return self._job is not None

    def start(self, name: str, function: Callable) -> None:
        if self.busy:
            raise RuntimeError("Another Quick Sort task is still running.")
        self.cancel.clear()
        self._job = _Job(name, function)
        self._job.signals.done.connect(self._done)
        self._job.signals.progress.connect(self.progress.emit)
        QThreadPool.globalInstance().start(self._job)

    @Slot(str, object, str)
    def _done(self, name: str, result: object, error: str) -> None:
        self._job = None
        self.finished.emit(name, result, error)
