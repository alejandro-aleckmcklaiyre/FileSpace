"""Explicit destination configuration and per-file conflict decisions."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from app.filesystem.file_operations import MovePlan


class ShortcutDialog(QDialog):
    def __init__(self, parent=None, shortcut: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit destination" if shortcut else "Add destination")
        self.resize(520, 220)
        data = shortcut or {}
        layout = QFormLayout(self)
        self.keyword = QLineEdit(data.get("keyword", ""))
        self.keyword.setMaxLength(20)
        self.name = QLineEdit(data.get("name", ""))
        self.name.setMaxLength(100)
        self.destination = QLineEdit(data.get("destination_path", ""))
        layout.addRow("Keyword", self.keyword)
        layout.addRow("Name", self.name)
        row = QHBoxLayout()
        row.addWidget(self.destination, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        layout.addRow("Destination", row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose destination", self.destination.text())
        if path:
            self.destination.setText(path)


class MoveConfirmationDialog(QDialog):
    def __init__(self, plan: MovePlan, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm Quick Sort move")
        self.resize(760, 480)
        layout = QVBoxLayout(self)
        sources = "\n".join(sorted({str(item.source.parent) for item in plan.items}))
        summary = QPlainTextEdit(
            f"Files: {len(plan.items)}\nTotal size: {plan.total_size:,} bytes\n"
            f"Sources:\n{sources}\nDestination: {plan.destination}\n"
            "Files are copied and verified before originals are removed."
        )
        summary.setReadOnly(True)
        summary.setMaximumHeight(150)
        layout.addWidget(summary)
        table = QTableWidget(len(plan.items), 3)
        table.setHorizontalHeaderLabels(["File", "Conflict", "Decision"])
        self.choices = []
        for row, item in enumerate(plan.items):
            for column, value in enumerate((item.source.name, "Existing file" if item.target_state else "None")):
                cell = QTableWidgetItem(value)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row, column, cell)
            choice = QComboBox()
            if item.target_state is not None:
                for label, value in (("Skip", "skip"), ("Rename incoming", "rename"), ("Replace existing", "replace")):
                    choice.addItem(label, value)
            else:
                choice.addItem("Move", "move")
                choice.addItem("Skip", "skip")
            table.setCellWidget(row, 2, choice)
            self.choices.append(choice)
        table.horizontalHeader().setStretchLastSection(True)
        table.resizeColumnsToContents()
        layout.addWidget(table)
        note = QLabel("Cancel stops between files. Changed files or new conflicts will fail safely; confirm again to retry.")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Move files")
        buttons.accepted.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def decisions(self) -> list[str]:
        return [choice.currentData() for choice in self.choices]

    def _confirm(self) -> None:
        count = self.decisions().count("replace")
        if count and QMessageBox.warning(
            self, "Confirm replacement",
            f"Replace {count} existing file(s)? Their previous contents will be removed after successful transfer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self.accept()
