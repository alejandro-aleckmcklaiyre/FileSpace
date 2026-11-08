"""File-only drag/drop presentation; every accepted drop still needs confirmation.

Internal drags use private MIME data, not shell file URLs, so dragging out of
FileSpace cannot let another application perform an unconfirmed move.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QMimeData, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QDrag, QPainter, QPen
from PySide6.QtWidgets import QApplication, QAbstractItemView, QListWidget, QToolTip, QTreeView

from app.filesystem.safety import SafetyPolicy

INTERNAL_MIME = "application/x-filespace-files"


def selected_file_rows(view):
    """Snapshot every selected file row, including partially selected rows.

    selectedRows() requires every column to be selected. A column/layout change
    or cell selection can leave a visibly selected name out of that result.
    Normalize selected cells to column zero and deduplicate within the root.
    """
    selection = view.selectionModel()
    if selection is None:
        return []
    rows = {}
    for index in selection.selectedIndexes():
        if index.isValid() and index.parent() == view.rootIndex():
            rows.setdefault(index.row(), index.siblingAtColumn(0))
    return list(rows.values())


@dataclass(frozen=True)
class DropRequest:
    sources: tuple[str, ...]
    destination: str
    operation: str
    external: bool


def event_files(event) -> tuple[tuple[str, ...], bool]:
    """Trust the actual Qt drag source, never a marker supplied by another app."""
    mime = event.mimeData()
    internal = isinstance(event.source(), FileDragView)
    try:
        if internal:
            if not mime.hasFormat(INTERNAL_MIME):
                return (), False
            values = json.loads(bytes(mime.data(INTERNAL_MIME)).decode("utf-8"))
        else:
            if not mime.hasUrls() or not mime.urls() or any(not url.isLocalFile() for url in mime.urls()):
                return (), True
            values = [url.toLocalFile() for url in mime.urls()]
        if not isinstance(values, list) or not values or any(
            not isinstance(value, str) or not value or "\x00" in value or not Path(value).is_absolute()
            for value in values
        ):
            return (), not internal
        # Deduplicate shell URL lists without changing their order.
        paths = tuple(dict.fromkeys(values))
        return paths, not internal
    except (ValueError, UnicodeError, TypeError):
        return (), not internal


def transport_action(event, external: bool):
    """External sources receive COPY acknowledgement; FileSpace owns any move.

    This prevents Explorer from deleting originals while confirmation or copying
    is pending. An explicit external Move choice is performed by our worker.
    """
    action = Qt.DropAction.CopyAction if external or event.modifiers() & Qt.KeyboardModifier.ControlModifier else Qt.DropAction.MoveAction
    return action if event.possibleActions() & action else None


class _DropTarget:
    """Shared viewport event handling; subclasses resolve their own destinations."""

    def _configure_drop(self) -> None:
        self.drop_policy: SafetyPolicy | None = None
        self._drag_rect = QRect()
        self._drag_valid = False
        self._drag_label = ""
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(False)

    def _feedback(self, valid: bool, rectangle: QRect, label: str) -> None:
        self._drag_valid, self._drag_rect, self._drag_label = valid, rectangle, label
        self.viewport().update()

    def _clear_feedback(self) -> None:
        self._feedback(False, QRect(), "")

    def _request(self, event) -> DropRequest | None:
        paths, external = event_files(event)
        action = transport_action(event, external)
        destination, rectangle = self._drop_destination(event.position().toPoint())
        valid = bool(paths and destination and action and self.isEnabled() and self.drop_policy is not None)
        if valid:
            valid = self.drop_policy.allows_candidate(Path(destination)) and all(
                self.drop_policy.allows_candidate(Path(path)) and Path(path).parent != Path(destination)
                for path in paths
            )
        operation = "copy" if external or event.modifiers() & Qt.KeyboardModifier.ControlModifier else "move"
        self._feedback(valid, rectangle, f"{operation.title()} files here — review before transfer" if valid else "Drop not allowed here")
        return DropRequest(paths, destination, operation, external) if valid else None

    def dragEnterEvent(self, event) -> None:
        paths, external = event_files(event)
        action = transport_action(event, external)
        self._request(event)
        # Accept supported data on entry so Qt continues sending movement events,
        # including when the pointer initially enters over an invalid file row.
        if paths and action and self.isEnabled() and self.drop_policy is not None:
            event.setDropAction(action)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        request = self._request(event)
        if request is None:
            event.ignore()
        else:
            event.setDropAction(transport_action(event, request.external))
            event.accept()

    def dragLeaveEvent(self, event) -> None:
        self._clear_feedback()
        event.accept()

    def dropEvent(self, event) -> None:
        request = self._request(event)
        self._clear_feedback()
        if request is None:
            event.ignore()
            return
        event.setDropAction(transport_action(event, request.external))
        event.accept()
        # Return to Qt/the shell first. Do not retain the event or its MIME data.
        QTimer.singleShot(0, lambda: self.files_dropped.emit(request))

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._drag_rect.isNull():
            return
        painter = QPainter(self.viewport())
        color = QColor(30, 110, 210) if self._drag_valid else QColor(190, 55, 45)
        painter.setPen(QPen(color, 2))
        tint = QColor(color)
        tint.setAlpha(30)
        painter.fillRect(self._drag_rect, tint)
        painter.drawRect(self._drag_rect.adjusted(1, 1, -2, -2))
        label = QRect(4, max(0, self.viewport().height() - 38), max(1, self.viewport().width() - 8), 34)
        painter.fillRect(label, self.palette().window())
        painter.drawText(label.adjusted(4, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap, self._drag_label)


class FileDragView(_DropTarget, QTreeView):
    files_dropped = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.quick_sort_key_handler: Callable[[str, bool], bool] | None = None
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDragEnabled(True)
        self._configure_drop()

    def keyPressEvent(self, event) -> None:
        """Give configured A–Z keys precedence over filename type-to-select.

        Scope is this focused view only. Modified commands, text fields, dialogs,
        and unassigned letters retain their existing Qt behavior.
        """
        if (
            self.hasFocus() and QApplication.activeModalWidget() is None
            and event.modifiers() in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ShiftModifier)
            and Qt.Key.Key_A <= event.key() <= Qt.Key.Key_Z
            and self.quick_sort_key_handler is not None
            and self.quick_sort_key_handler(chr(event.key()), event.isAutoRepeat())
        ):
            event.accept()
            return
        super().keyPressEvent(event)

    def startDrag(self, supported_actions) -> None:
        model = self.model()
        indexes = selected_file_rows(self) if model else []
        if not indexes or any(model.isDir(index) for index in indexes):
            QToolTip.showText(QCursor.pos(), "Drag files only; folder transfers are not supported.", self)
            return
        paths = [model.filePath(index) for index in indexes]
        if self.drop_policy is None or any(not self.drop_policy.allows_candidate(Path(path)) for path in paths):
            QToolTip.showText(QCursor.pos(), "Files in protected locations cannot be transferred.", self)
            return
        mime = QMimeData()
        mime.setData(INTERNAL_MIME, json.dumps(paths).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction, Qt.DropAction.MoveAction)
        # Never call the default model drag implementation or remove source rows.

    def _drop_destination(self, point) -> tuple[str, QRect]:
        model = self.model()
        rectangle = self.viewport().rect().adjusted(1, 1, -1, -1)
        if model is None:
            return "", rectangle
        index = self.indexAt(point)
        if index.isValid():
            index = index.siblingAtColumn(0)
            rectangle = self.visualRect(index)
            rectangle.setLeft(0)
            rectangle.setRight(self.viewport().width() - 1)
            return (model.filePath(index) if model.isDir(index) else ""), rectangle
        root = self.rootIndex()
        return (model.filePath(root) if root.isValid() else ""), rectangle


class ShortcutDropList(_DropTarget, QListWidget):
    files_dropped = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self._configure_drop()

    def _drop_destination(self, point) -> tuple[str, QRect]:
        item = self.itemAt(point)
        if item is None:
            return "", self.viewport().rect().adjusted(1, 1, -1, -1)
        data = item.data(Qt.ItemDataRole.UserRole)
        return (data.get("destination_path", "") if isinstance(data, dict) else ""), self.visualItemRect(item)
