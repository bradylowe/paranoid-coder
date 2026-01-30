"""Tree view of summarized paths with lazy loading."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QBrush, QColor
from PyQt6.QtWidgets import (
    QApplication,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
)

from paranoid.config import load_config
from paranoid.utils.ignore import build_spec, is_ignored, load_patterns

if TYPE_CHECKING:
    from paranoid.storage.base import Storage


# Light amber background for stale (hash mismatch) items
STALE_BACKGROUND = QBrush(QColor("#fff3cd"))


class SummaryTreeWidget(QTreeWidget):
    """Tree of file/directory summaries; children loaded on expand."""

    PATH_ROLE = Qt.ItemDataRole.UserRole
    TYPE_ROLE = Qt.ItemDataRole.UserRole + 1
    STALE_ROLE = Qt.ItemDataRole.UserRole + 2

    reSummarizeRequested = pyqtSignal(str)  # path

    def __init__(
        self,
        storage: Storage,
        project_root: Path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._storage = storage
        self._project_root = Path(project_root).resolve()
        self._loaded_paths: set[str] = set()
        self._filter_text = ""
        config = load_config(self._project_root)
        self._show_ignored = config.get("viewer", {}).get("show_ignored", False)
        self._ignore_spec = self._build_ignore_spec()
        self.setHeaderLabels(["Name"])
        self.setUniformRowHeights(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemExpanded.connect(self._on_item_expanded)
        self._populate_root()

    def _build_ignore_spec(self):
        config = load_config(self._project_root)
        patterns_with_source = load_patterns(self._project_root, config)
        patterns = [p for p, _ in patterns_with_source]
        return build_spec(patterns)

    def _path_key(self, path: str | Path) -> str:
        p = Path(path).resolve()
        return p.as_posix()

    def _populate_root(self) -> None:
        children = self._storage.list_children(self._project_root)
        for s in children:
            if not self._show_ignored and is_ignored(Path(s.path), self._project_root, self._ignore_spec):
                continue
            item = self._make_item(s)
            self.addTopLevelItem(item)
            if s.type == "directory":
                item.setChildIndicatorPolicy(
                    QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
                )

    def _make_item(self, summary: object) -> QTreeWidgetItem:
        from paranoid.storage.models import Summary
        from paranoid.utils.hashing import content_hash, current_tree_hash

        s = summary
        if not isinstance(s, Summary):
            return QTreeWidgetItem()
        path_str = s.path
        name = Path(path_str).name or path_str
        item = QTreeWidgetItem([name])
        item.setData(0, self.PATH_ROLE, path_str)
        item.setData(0, self.TYPE_ROLE, s.type)
        stale = False
        try:
            if s.type == "file":
                current_hash = content_hash(Path(path_str))
                stale = current_hash != s.hash
            else:
                current_hash = current_tree_hash(path_str, self._storage)
                stale = current_hash != s.hash
        except (ValueError, OSError):
            stale = True
        item.setData(0, self.STALE_ROLE, stale)
        if stale:
            item.setBackground(0, STALE_BACKGROUND)
        if s.type == "directory":
            item.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
            )
        return item

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        path = item.data(0, self.PATH_ROLE)
        if not path or path in self._loaded_paths:
            return
        self._loaded_paths.add(path)
        children = self._storage.list_children(path)
        for s in children:
            if not self._show_ignored and is_ignored(Path(s.path), self._project_root, self._ignore_spec):
                continue
            child_item = self._make_item(s)
            item.addChild(child_item)

    def selected_path(self) -> str | None:
        """Return the path of the current item, or None."""
        items = self.selectedItems()
        if not items:
            return None
        return items[0].data(0, self.PATH_ROLE)

    def _show_context_menu(self, position) -> None:
        item = self.itemAt(position)
        path = item.data(0, self.PATH_ROLE) if item else None
        menu = QMenu(self)
        copy_act = QAction("Copy path", self)
        copy_act.setEnabled(bool(path))
        copy_act.triggered.connect(self._copy_path)
        menu.addAction(copy_act)
        store_act = QAction("Store current hashes", self)
        store_act.setEnabled(bool(path))
        store_act.triggered.connect(self._store_current_hashes_selected)
        menu.addAction(store_act)
        resum_act = QAction("Re-summarize", self)
        resum_act.setEnabled(bool(path))
        resum_act.triggered.connect(self._request_re_summarize)
        menu.addAction(resum_act)
        menu.exec(self.viewport().mapToGlobal(position))

    def _copy_path(self) -> None:
        path = self.selected_path()
        if path:
            QApplication.clipboard().setText(path)

    def _store_current_hashes_selected(self) -> None:
        """Store current content/tree hashes in DB (acknowledge change without re-summarizing)."""
        path = self.selected_path()
        if not path:
            return
        self._store_current_hashes_for_path(path)
        self._clear_stale_appearance_for_selected()
        self.refresh_selected_node()

    def _store_current_hashes_for_path(self, path: str) -> None:
        """Update DB with current hash for path; for dirs, recursively update children first."""
        from paranoid.storage.models import Summary
        from paranoid.utils.hashing import content_hash, tree_hash

        summary = self._storage.get_summary(path)
        if not summary:
            return
        try:
            if summary.type == "file":
                new_hash = content_hash(Path(path))
            else:
                for child in self._storage.list_children(path):
                    self._store_current_hashes_for_path(child.path)
                new_hash = tree_hash(path, self._storage)
        except (ValueError, OSError):
            return
        updated = dataclasses.replace(summary, hash=new_hash)
        self._storage.set_summary(updated)

    def _clear_stale_appearance_for_selected(self) -> None:
        """Clear yellow background and stale role on selected item so it shows as up-to-date."""
        items = self.selectedItems()
        if not items:
            return
        item = items[0]
        item.setData(0, self.STALE_ROLE, False)
        item.setBackground(0, QBrush())

    def refresh_selected_node(self) -> None:
        """Reload selected node from storage (re-expand to refresh children and stale state)."""
        items = self.selectedItems()
        if not items:
            return
        item = items[0]
        path = item.data(0, self.PATH_ROLE)
        if not path:
            return
        self._loaded_paths.discard(path)
        while item.childCount():
            item.takeChild(0)
        self._on_item_expanded(item)

    def _request_re_summarize(self) -> None:
        path = self.selected_path()
        if path:
            self.reSummarizeRequested.emit(path)

    def set_show_ignored(self, show: bool) -> None:
        """Toggle showing ignored paths; rebuild root when changed."""
        if self._show_ignored == show:
            return
        self._show_ignored = show
        self._rebuild_root()

    def _rebuild_root(self) -> None:
        """Clear tree and repopulate from storage (respects show_ignored and filter)."""
        self._loaded_paths.clear()
        self.clear()
        self._populate_root()
        self._apply_filter_to_item(None)

    def set_filter_text(self, text: str) -> None:
        """Show only items whose path contains text (case-insensitive); empty = show all."""
        self._filter_text = (text or "").strip().lower()
        self._apply_filter_to_item(None)

    def _apply_filter_to_item(self, item: QTreeWidgetItem | None) -> bool:
        """Apply filter to item and its children; return True if item or any child is visible."""
        if item is None:
            visible_any = False
            for i in range(self.topLevelItemCount()):
                if self._apply_filter_to_item(self.topLevelItem(i)):
                    visible_any = True
            return visible_any
        path = item.data(0, self.PATH_ROLE) or ""
        matches = not self._filter_text or self._filter_text in path.lower()
        visible_child = False
        for i in range(item.childCount()):
            if self._apply_filter_to_item(item.child(i)):
                visible_child = True
        show = matches or visible_child
        item.setHidden(not show)
        return show
