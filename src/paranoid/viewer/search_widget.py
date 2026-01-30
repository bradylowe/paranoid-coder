"""Search/filter widget for the tree."""

from __future__ import annotations

from PyQt6.QtWidgets import QLineEdit, QSizePolicy, QWidget


class SearchWidget(QWidget):
    """Line edit to filter tree by path or content; emits filter text for tree to use."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText("Filter by path or summary text…")
        self._edit.setClearButtonEnabled(True)
        from PyQt6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._edit)
        # Keep the bar compact: single-line height, don't expand vertically
        self.setMaximumHeight(self._edit.sizeHint().height() + 4)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

    def filter_text(self) -> str:
        """Current filter string."""
        return self._edit.text().strip()

    def connect_filter_changed(self, slot) -> None:
        """Connect to slot(filter_text: str) when user changes the filter."""
        self._edit.textChanged.connect(lambda: slot(self.filter_text()))
