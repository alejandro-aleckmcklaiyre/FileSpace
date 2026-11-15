"""Context menus and clipboard intent; filesystem mutations stay in workers."""

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QItemSelectionModel, QMimeData, QObject, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QInputDialog, QMenu, QMessageBox, QPlainTextEdit, QVBoxLayout

from app.services.file_action_service import FileActionService
from app.ui.drag_drop import DropRequest

CLIPBOARD_MIME = "application/x-filespace-clipboard"


class FileActions(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.panel = window.quick_sort
        self.service = FileActionService(self.panel.repository, self.panel.service.policy)
        self._clipboard_token = ""
        self._clipboard_paths = ()
        self._clipboard_operation = "copy"
        self.panel.transfer_completed.connect(self._transferred)
        for view in (window.explorer.details, window.explorer.grid):
            view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            view.customContextMenuRequested.connect(lambda point, view=view: self.show_menu(view, point))
            view.file_action_handler = self.invoke

    def show_menu(self, view, point):
        if self.panel.busy:
            return
        index = view.indexAt(point)
        if index.isValid() and not view.selectionModel().isSelected(index):
            flags = QItemSelectionModel.SelectionFlag.ClearAndSelect
            if view is self.window.explorer.details:
                flags |= QItemSelectionModel.SelectionFlag.Rows
            view.selectionModel().setCurrentIndex(index, flags)
        elif not index.isValid():
            view.clearSelection()
        menu = self.build_menu(view)
        menu.exec(view.viewport().mapToGlobal(point))

    def build_menu(self, view=None):
        explorer = self.window.explorer
        paths = explorer.selected_paths()
        files = bool(paths) and all(not explorer.model.isDir(explorer.model.index(path)) for path in paths)
        one = len(paths) == 1
        target = paths[0] if one and not files else str(self.window.browser.current or "")
        menu = QMenu(self.window)
        for name, title, enabled in (
            ("preview", "Preview", one and files), ("open", "Open", one),
            ("containing", "Open containing folder", one),
            ("copy", "Copy", files), ("cut", "Cut", files),
            ("paste", "Paste", bool(target and self.clipboard_payload()[0])),
            ("rename", "Rename", one and files), ("recycle", "Delete to Recycle Bin", files),
            ("properties", "Properties", bool(paths or target)),
            ("favorite", "Add folder to Favorites", bool(target)),
        ):
            action = menu.addAction(title)
            action.setObjectName(name)
            action.setEnabled(enabled)
            action.triggered.connect(lambda checked=False, name=name, target=target: self.invoke(name, target))
        quick = menu.addMenu("Move to Quick Sort destination")
        quick.setEnabled(files and self.panel.shortcuts.count() > 0)
        for row in range(self.panel.shortcuts.count()):
            item = self.panel.shortcuts.item(row)
            action = quick.addAction(item.text().replace("&", "&&"))
            action.triggered.connect(lambda checked=False, item=item: self.panel._activate(item))
        return menu

    def invoke(self, action: str, target: str = "") -> None:
        if self.panel.busy or self.window._quick_sort_busy:
            return
        paths = self.window.explorer.selected_paths()
        if action == "paste":
            sources, operation, external = self.clipboard_payload()
            destination = target or str(self.window.browser.current or "")
            if sources and destination:
                self.panel.request_drop(DropRequest(sources, destination, operation, external))
            return
        if action == "favorite":
            self.window.favorites.add_path(target or self.window.browser.current)
            return
        if action == "properties":
            values = paths or ([target] if target else [str(self.window.browser.current)])
            self.panel.run_action(lambda progress: self.service.properties(values), "Reading properties…", lambda text: self.panel._report("Properties", text))
            return
        if not paths:
            return
        if action == "preview":
            self.window.navigation.preview_button.setChecked(True)
            self.window.preview.select_file(paths[0])
        elif action in {"open", "containing"}:
            path = paths[0]
            if action == "open" and self.window.explorer.model.isDir(self.window.explorer.model.index(path)):
                self.window.browser.navigate(path)
            else:
                destination = str(Path(path).parent) if action == "containing" else path
                def launch(text):
                    if not QDesktopServices.openUrl(QUrl.fromLocalFile(destination)):
                        QMessageBox.warning(self.window, "Cannot open location", "Windows could not open this file or folder.")
                self.panel.run_action(lambda progress: self.service.properties([destination]), "Checking location…", launch)
        elif action in {"copy", "cut"}:
            if any(self.window.explorer.model.isDir(self.window.explorer.model.index(path)) for path in paths):
                QMessageBox.information(self.window, "Files only", "Folder transfers are not supported. Select files only.")
                return
            self._clipboard_token = uuid4().hex
            self._clipboard_paths = tuple(paths)
            self._clipboard_operation = "move" if action == "cut" else "copy"
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(path) for path in paths])
            mime.setData(CLIPBOARD_MIME, self._clipboard_token.encode())
            # No shell Move drop effect: an external paste must not delete files.
            QApplication.clipboard().setMimeData(mime)
            self.window.statusBar().showMessage(f"{len(paths)} file(s) ready to {'move' if action == 'cut' else 'copy'} when pasted.")
        elif action == "rename" and len(paths) == 1:
            path = Path(paths[0])
            stem, accepted = QInputDialog.getText(self.window, "Rename file", f"New name (extension {path.suffix or '(none)'} is kept)", text=path.stem)
            if accepted:
                self.panel.run_action(lambda progress: self.service.plan_rename(str(path), stem), "Checking new name…", self._confirm)
        elif action == "recycle":
            self.panel.run_action(lambda progress: self.service.plan_recycle(paths), "Checking files for recycling…", self._confirm)

    def clipboard_payload(self):
        mime = QApplication.clipboard().mimeData()
        if mime is None:
            return (), "copy", True
        if self._clipboard_token and bytes(mime.data(CLIPBOARD_MIME)).decode(errors="replace") == self._clipboard_token:
            return self._clipboard_paths, self._clipboard_operation, False
        urls = mime.urls()
        if not urls or any(not url.isLocalFile() for url in urls):
            return (), "copy", True
        paths = tuple(dict.fromkeys(url.toLocalFile() for url in urls))
        if any(not path or "\x00" in path or not Path(path).is_absolute() for path in paths):
            return (), "copy", True
        return paths, "copy", True

    def _transferred(self, results):
        moved = {Path(item.source) for item in results if item.status == "moved"}
        if self._clipboard_operation == "move" and self._clipboard_paths and all(Path(path) in moved for path in self._clipboard_paths):
            if not self.clipboard_payload()[2]:
                QApplication.clipboard().clear()
            self._clipboard_paths = ()
            self._clipboard_token = ""

    def _confirm(self, plan):
        dialog = QDialog(self.window)
        dialog.setWindowTitle("Confirm rename" if plan.operation == "rename" else "Confirm Recycle Bin deletion")
        dialog.resize(650, 400)
        layout = QVBoxLayout(dialog)
        summary = QPlainTextEdit(
            f"Files: {len(plan.items)}\nTotal size: {plan.total_size:,} bytes\n\n" + "\n\n".join(
                f"{item.source}\n→ {item.destination}" for item in plan.items
            )
        )
        summary.setReadOnly(True)
        layout.addWidget(summary)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Rename file" if plan.operation == "rename" else "Send to Recycle Bin")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setDefault(True)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.panel._set_busy(True)
        def released():
            self.panel._set_busy(False)
            self.panel.run_action(
                lambda progress: self.service.execute(plan, self.panel.runner.cancel, progress),
                "Applying confirmed file action…", self._results, cancellable=True, mutating=True,
            )
        self.window.preview.release_for_transfer(released)

    def _results(self, results):
        self.window._refresh()
        self.panel._report("File action results", "\n\n".join(f"{item.status}: {item.source}\n→ {item.destination}\n{item.message}" for item in results))
