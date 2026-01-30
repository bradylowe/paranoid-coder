"""Detail panel showing summary text and metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QTextEdit,
    QWidget,
)

if TYPE_CHECKING:
    from paranoid.storage.base import Storage


def _label(text: str) -> QLabel:
    w = QLabel(text)
    w.setWordWrap(True)
    return w


class DetailWidget(QScrollArea):
    """Shows description and metadata for the selected summary."""

    def __init__(self, storage: Storage, parent=None) -> None:
        super().__init__(parent)
        self._storage = storage
        self.setWidgetResizable(True)
        self._content = QWidget()
        self._layout = QFormLayout(self._content)
        self._description = QTextEdit()
        self._description.setReadOnly(True)
        self._description.setPlaceholderText("Select an item to view its summary.")
        self._metadata = QGroupBox("Metadata")
        self._meta_layout = QFormLayout(self._metadata)
        self._layout.addRow(self._description)
        self._layout.addRow(self._metadata)
        self.setWidget(self._content)

    def _clear_meta_rows(self) -> None:
        while self._meta_layout.rowCount():
            self._meta_layout.removeRow(0)

    def show_path(self, path: str | None) -> None:
        """Load and display the summary for path; clear if path is None."""
        if not path:
            self._description.clear()
            self._description.setPlaceholderText("Select an item to view its summary.")
            self._clear_meta_rows()
            return
        summary = self._storage.get_summary(path)
        if summary is None:
            self._description.setPlainText("(No summary in database for this path.)")
            self._clear_meta_rows()
            return
        self._description.setPlainText(summary.description or "(No description)")
        self._clear_meta_rows()
        self._meta_layout.addRow("Path:", _label(path))
        self._meta_layout.addRow("Type:", _label(summary.type))
        self._meta_layout.addRow("Model:", _label(summary.model or "—"))
        if summary.model_version:
            self._meta_layout.addRow("Model version:", _label(summary.model_version))
        self._meta_layout.addRow("Generated:", _label(summary.generated_at or "—"))
        self._meta_layout.addRow("Updated:", _label(summary.updated_at or "—"))
        if summary.error:
            self._meta_layout.addRow("Error:", _label(summary.error))
