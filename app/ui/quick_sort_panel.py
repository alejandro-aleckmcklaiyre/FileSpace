"""Shortcut management and explicit, confirmed move workflow."""

from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QProgressDialog, QPushButton, QVBoxLayout, QWidget,
)

from app.database.repository import Repository
from app.filesystem.safety import SafetyPolicy
from app.services.file_operation_service import FileOperationService
from app.services.quick_sort_service import QuickSortService
from app.ui.dialogs.quick_sort import ExternalTransferDialog, TransferConfirmationDialog, ShortcutDialog
from app.ui.drag_drop import DropRequest, ShortcutDropList


class QuickSortPanel(QWidget):
    navigate_requested = Signal(str)
    busy_changed = Signal(bool)
    transfer_requested = Signal(object, object)
    files_changed = Signal()

    def __init__(self, repository: Repository, policy: SafetyPolicy, selected_paths: Callable, parent=None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.service = QuickSortService(repository, policy)
        self.runner = FileOperationService(self)
        self.runner.finished.connect(self._finished)
        self.runner.progress.connect(self._progress)
        self.selected_paths = selected_paths
        self.busy = False
        self.initialized = False
        self.progress_dialog: QProgressDialog | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = QLabel("QUICK SORT")
        heading.setObjectName("sectionHeading")
        layout.addWidget(heading)
        self.selection_hint = QLabel()
        self.selection_hint.setWordWrap(True)
        self.update_selection_count(0)
        layout.addWidget(self.selection_hint)
        self.shortcuts = ShortcutDropList()
        self.shortcuts.drop_policy = policy
        self.shortcuts.files_dropped.connect(self.request_drop)
        self.shortcuts.setAccessibleName("Quick Sort destinations")
        self.shortcuts.setFixedHeight(48)
        self.shortcuts.itemClicked.connect(self._activate)
        self.shortcuts.itemActivated.connect(self._activate)
        layout.addWidget(self.shortcuts)
        self.empty_label = QLabel("No destinations configured. Choose Add to create one.")
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)
        self.controls = QWidget()
        controls = QVBoxLayout(self.controls)
        controls.setContentsMargins(0, 0, 0, 0)
        for actions in (
            (("Add", lambda: self._edit()), ("Edit", self._edit_selected), ("Delete", self._delete)),
            (("↑", lambda: self._reorder(-1)), ("↓", lambda: self._reorder(1)), ("Open", self._open)),
            (("History", self._history),),
        ):
            row = QHBoxLayout()
            for label, callback in actions:
                button = QPushButton(label)
                if label == "Open":
                    button.setToolTip("Open the highlighted destination without moving selected files.")
                button.clicked.connect(callback)
                row.addWidget(button)
            controls.addLayout(row)
        layout.addWidget(self.controls)
        self.controls.setEnabled(False)
        QTimer.singleShot(0, self._initialize)

    def update_selection_count(self, count: int) -> None:
        self.selection_hint.setText(
            f"{count} item(s) selected. Click a destination to review a move."
            if count else "No files selected. Click a destination to open it."
        )

    def _initialize(self) -> None:
        def initialize(progress):
            self.repository.initialize()
            return self.repository.shortcuts()
        self._start("initialize", initialize, "Loading destinations…")

    def _selected(self) -> dict | None:
        item = self.shortcuts.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def activate_keyword(self, keyword: str, auto_repeat: bool = False) -> bool:
        """Return whether a configured single-letter key was handled.

        All activations reuse the click workflow, including selection snapshots,
        validation, confirmation, and empty-selection destination navigation.
        """
        keyword = keyword.casefold()
        if len(keyword) != 1 or not "a" <= keyword <= "z":
            return False
        for row in range(self.shortcuts.count()):
            item = self.shortcuts.item(row)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data["keyword"].strip().casefold() == keyword:
                if self.initialized and not self.busy and not auto_repeat:
                    self.shortcuts.setCurrentItem(item)
                    self._activate(item)
                return True
        return False

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.controls.setEnabled(not busy and self.initialized)
        self.shortcuts.setEnabled(not busy)
        self.busy_changed.emit(busy)

    def _start(self, name, function, label: str, cancellable: bool = False) -> None:
        self._set_busy(True)
        self.progress_dialog = QProgressDialog(label, "Cancel after current file" if cancellable else "", 0, 0, self.window())
        if not cancellable:
            self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setWindowTitle("Quick Sort")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(300)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.canceled.connect(self.runner.cancel.set)
        self.runner.start(name, function)

    def _progress(self, message: str) -> None:
        if self.progress_dialog is not None:
            self.progress_dialog.setLabelText(message)

    def _close_progress(self) -> None:
        if self.progress_dialog is not None:
            self.progress_dialog.reset()
            self.progress_dialog.close()
            self.progress_dialog.deleteLater()
            self.progress_dialog = None

    def _reload_rows(self, rows) -> None:
        selected = self._selected()
        self.shortcuts.clear()
        for shortcut in rows:
            item = QListWidgetItem(f"[{shortcut['keyword']}] {shortcut['name']}")
            item.setData(Qt.ItemDataRole.UserRole, shortcut)
            item.setToolTip(shortcut["destination_path"])
            key = shortcut["keyword"].strip().upper()
            if len(key) == 1 and "A" <= key <= "Z":
                item.setToolTip(f"{shortcut['destination_path']}\nPress {key} while the file list has focus to activate.")
            self.shortcuts.addItem(item)
            if selected and shortcut["id"] == selected["id"]:
                self.shortcuts.setCurrentItem(item)
        self.empty_label.setVisible(not bool(rows))
        self.shortcuts.setVisible(bool(rows))
        height = sum(self.shortcuts.sizeHintForRow(row) for row in range(self.shortcuts.count()))
        self.shortcuts.setFixedHeight(max(48, min(160, height + 8)))

    def _edit(self, shortcut: dict | None = None) -> None:
        if self.busy:
            return
        dialog = ShortcutDialog(self, shortcut)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        keyword, name, destination = dialog.keyword.text(), dialog.name.text(), dialog.destination.text()
        shortcut_id = shortcut["id"] if shortcut else None
        def save(progress):
            self.service.save(keyword, name, destination, shortcut_id)
            return self.repository.shortcuts()
        self._start("save", save, "Validating and saving destination…")

    def _edit_selected(self) -> None:
        shortcut = self._selected()
        if shortcut:
            self._edit(shortcut)

    def _delete(self) -> None:
        shortcut = self._selected()
        if not shortcut or self.busy:
            return
        if QMessageBox.question(self, "Delete shortcut", "Remove this shortcut? Destination files will stay where they are.") != QMessageBox.StandardButton.Yes:
            return
        def remove(progress):
            self.repository.delete_shortcut(shortcut["id"])
            return self.repository.shortcuts()
        self._start("delete", remove, "Removing shortcut…")

    def _reorder(self, offset: int) -> None:
        shortcut = self._selected()
        if shortcut and not self.busy:
            def reorder(progress):
                self.repository.reorder(shortcut["id"], offset)
                return self.repository.shortcuts()
            self._start("reorder", reorder, "Saving destination order…")

    def _open(self) -> None:
        shortcut = self._selected()
        if shortcut and not self.busy:
            self.navigate_requested.emit(shortcut["destination_path"])

    def _activate(self, item: QListWidgetItem) -> None:
        if self.busy:
            return
        shortcut = item.data(Qt.ItemDataRole.UserRole)
        sources = self.selected_paths()
        if not sources:
            self.navigate_requested.emit(shortcut["destination_path"])
            return
        self._start("plan", lambda progress: self.service.plan(sources, shortcut["destination_path"]), "Checking files and conflicts…")

    def request_drop(self, request: DropRequest) -> None:
        """Snapshot the drop intent, choose external mode, then validate in a worker."""
        if self.busy or not self.initialized:
            return
        operation = request.operation
        if request.external:
            self._set_busy(True)
            dialog = ExternalTransferDialog(request.sources, request.destination, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                self._set_busy(False)
                return
            operation = dialog.operation()
        self._start(
            "plan", lambda progress: self.service.plan(list(request.sources), request.destination, operation),
            "Checking dropped files and conflicts…",
        )

    def _history(self) -> None:
        if not self.busy:
            self._start("history", lambda progress: self.repository.history(), "Loading history…")

    def execute(self, plan, decisions) -> None:
        self._start("transfer", lambda progress: self.service.transfer(plan, decisions, self.runner.cancel, progress), f"Preparing {plan.operation}…", True)

    def _finished(self, name: str, result, error: str) -> None:
        self._close_progress()
        if error:
            self._set_busy(False)
            QMessageBox.warning(self, "Quick Sort could not complete", error)
            if name == "transfer":
                self.files_changed.emit()
            return
        if name == "plan":
            confirmation = TransferConfirmationDialog(result, self)
            if confirmation.exec() == QDialog.DialogCode.Accepted:
                self.transfer_requested.emit(result, confirmation.decisions())
                return
        elif name == "transfer":
            self.files_changed.emit()
            self._report("Transfer results", "\n\n".join(
                f"{item.status}: {item.source}\n→ {item.destination}\n{item.message}" for item in result
            ))
        elif name == "history":
            self._report("Operation history (latest 1,000 files)", f"History timestamps are UTC.\nDatabase: {self.repository.path}\n\n" + ("\n\n".join(
                f"{row['operation_date']} | {row['operation_type']} | batch {row['operation_status']} | file {row['status']}\n"
                f"{row['source_path']}\n→ {row['destination_path']}\n{row['message']}" for row in result
            ) or "No operations recorded."))
        else:
            self.initialized = True
            self._reload_rows(result)
        self._set_busy(False)

    def _report(self, title: str, content: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(760, 500)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit(content)
        text.setReadOnly(True)
        layout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()
