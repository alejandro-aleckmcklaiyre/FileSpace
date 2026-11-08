"""Explicit destination configuration and per-file conflict decisions."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QRadioButton,
)

from app.filesystem.file_operations import TransferPlan


class ShortcutDialog(QDialog):
    def __init__(self, parent=None, shortcut: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit destination" if shortcut else "Add destination")
        self.resize(520, 220)
        data = shortcut or {}
        layout = QFormLayout(self)
        self.keyword = QLineEdit(data.get("keyword", ""))
        self.keyword.setMaxLength(20)
        self.keyword.setToolTip("Use a single A–Z letter to activate this destination from the focused file list.")
        self.name = QLineEdit(data.get("name", ""))
        self.name.setMaxLength(100)
        self.destination = QLineEdit(data.get("destination_path", ""))
        layout.addRow("Keyword", self.keyword)
        layout.addRow("Name", self.name)
        help_text = QLabel("Single A–Z keywords work in the file list. Other keywords are mouse-only labels.")
        help_text.setWordWrap(True)
        layout.addRow(help_text)
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


class TransferConfirmationDialog(QDialog):
    def __init__(self, plan: TransferPlan, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Confirm file {plan.operation}")
        self.resize(760, 480)
        layout = QVBoxLayout(self)
        sources = "\n".join(sorted({str(item.source.parent) for item in plan.items}))
        summary = QPlainTextEdit(
            f"Operation: {plan.operation.upper()}\nFiles: {len(plan.items)}\nTotal size: {plan.total_size:,} bytes\n"
            f"Sources:\n{sources}\nDestination: {plan.destination}\n"
            + ("Originals are retained." if plan.operation == "copy" else "Files are copied and verified before originals are removed.")
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
                choice.addItem(plan.operation.title(), plan.operation)
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
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(f"{plan.operation.title()} files")
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


class ExternalTransferDialog(QDialog):
    """Choose external transfer intent before building a confirmation plan."""

    def __init__(self, sources: tuple[str, ...], destination: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import files")
        self.resize(520, 240)
        layout = QVBoxLayout(self)
        summary = QPlainTextEdit(f"{len(sources)} file(s) dropped from outside FileSpace.\nDestination: {destination}")
        summary.setReadOnly(True)
        summary.setMaximumHeight(90)
        layout.addWidget(summary)
        self.copy = QRadioButton("Copy — keep the original files")
        self.move = QRadioButton("Move — remove originals after successful verification")
        self.copy.setChecked(True)
        layout.addWidget(self.copy)
        layout.addWidget(self.move)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Review files")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def operation(self) -> str:
        return "move" if self.move.isChecked() else "copy"
