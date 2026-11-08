"""Asynchronous navigation validation and success-only history updates."""

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from app.filesystem.path_validator import validate_directory


class _Result(QObject):
    finished = Signal(int, object, str)


class _Validation(QRunnable):
    def __init__(self, token: int, value: str, base: Path | None) -> None:
        super().__init__()
        self.token, self.value, self.base = token, value, base
        self.signals = _Result()

    @Slot()
    def run(self) -> None:
        try:
            path = validate_directory(self.value, self.base)
        except (OSError, ValueError, RuntimeError) as error:
            self.signals.finished.emit(self.token, None, str(error))
        else:
            self.signals.finished.emit(self.token, path, "")


class FileBrowserService(QObject):
    """Keep UI state unchanged until a requested destination is validated."""

    location_changed = Signal(str)
    navigation_failed = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.history: list[Path] = []
        self.position = -1
        self._token = 0
        self._target: int | None = None
        self._workers: dict[int, _Validation] = {}

    @property
    def current(self) -> Path | None:
        return self.history[self.position] if self.position >= 0 else None

    @property
    def can_back(self) -> bool:
        return self.position > 0

    @property
    def can_forward(self) -> bool:
        return self.position + 1 < len(self.history)

    def navigate(self, value: str, target: int | None = None) -> None:
        self._token += 1
        self._target = target
        worker = _Validation(self._token, value, self.current)
        self._workers[self._token] = worker
        worker.signals.finished.connect(self._complete)
        self.busy_changed.emit(True)
        QThreadPool.globalInstance().start(worker)

    @Slot(int, object, str)
    def _complete(self, token: int, path: Path | None, error: str) -> None:
        self._workers.pop(token, None)
        if token != self._token:
            return
        self.busy_changed.emit(False)
        if path is None:
            self.navigation_failed.emit(error)
            return
        if self._target is not None:
            self.position = self._target
        elif path != self.current:
            self.history = self.history[: self.position + 1] + [path]
            self.position = len(self.history) - 1
        self.location_changed.emit(str(path))

    def back(self) -> None:
        if self.can_back:
            self.navigate(str(self.history[self.position - 1]), self.position - 1)

    def forward(self) -> None:
        if self.can_forward:
            self.navigate(str(self.history[self.position + 1]), self.position + 1)

    def up(self) -> None:
        if self.current is not None and self.current.parent != self.current:
            self.navigate(str(self.current.parent))

    def refresh(self) -> None:
        if self.current is not None:
            self.navigate(str(self.current), self.position)
