"""Detail panel showing summary text and metadata."""

from __future__ import annotations

from pathlib import Path
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


_CONTEXT_LEVEL_LABELS = {0: "Isolated", 1: "With graph", 2: "With RAG (future)"}


def _context_level_label(level: int) -> str:
    return _CONTEXT_LEVEL_LABELS.get(level, f"Unknown ({level})")


class DetailWidget(QScrollArea):
    """Shows description and metadata for the selected summary."""

    def __init__(self, storage: Storage, project_root: Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self._storage = storage
        self._project_root = Path(project_root) if project_root else None
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

    def _needs_resummary(self, path: str, summary: object) -> bool:
        """Return True if item needs re-summarization (content or context changed)."""
        from paranoid.config import load_config
        from paranoid.storage.models import Summary
        from paranoid.utils.hashing import content_hash, current_tree_hash, needs_summarization

        if not isinstance(summary, Summary):
            return False
        try:
            if summary.type == "file":
                current_hash = content_hash(Path(path))
            else:
                current_hash = current_tree_hash(path, self._storage)
            config = load_config(self._project_root) if self._project_root else None
            return needs_summarization(path, current_hash, self._storage, config)
        except (ValueError, OSError):
            return True

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
        needs_resum = self._needs_resummary(path, summary)
        if needs_resum:
            self._meta_layout.addRow(
                "Status:",
                _label("Needs re-summary (content or context changed)"),
            )
        self._meta_layout.addRow("Path:", _label(path))
        self._meta_layout.addRow("Type:", _label(summary.type))
        self._meta_layout.addRow("Model:", _label(summary.model or "—"))
        if summary.model_version:
            self._meta_layout.addRow("Model version:", _label(summary.model_version))
        self._meta_layout.addRow("Prompt version:", _label(summary.prompt_version or "—"))
        self._meta_layout.addRow(
            "Context level:",
            _label(_context_level_label(summary.context_level)),
        )
        self._meta_layout.addRow("Generated:", _label(summary.generated_at or "—"))
        self._meta_layout.addRow("Updated:", _label(summary.updated_at or "—"))
        if summary.error:
            self._meta_layout.addRow("Error:", _label(summary.error))
