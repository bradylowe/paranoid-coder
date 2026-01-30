"""Tree view of summarized paths with lazy loading."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
)

if TYPE_CHECKING:
    from paranoid.storage.base import Storage


class SummaryTreeWidget(QTreeWidget):
    """Tree of file/directory summaries; children loaded on expand."""

    PATH_ROLE = Qt.ItemDataRole.UserRole
    TYPE_ROLE = Qt.ItemDataRole.UserRole + 1

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
        self.setHeaderLabels(["Name"])
        self.setUniformRowHeights(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemExpanded.connect(self._on_item_expanded)
        self._populate_root()

    def _path_key(self, path: str | Path) -> str:
        p = Path(path).resolve()
        return p.as_posix()

    def _populate_root(self) -> None:
        children = self._storage.list_children(self._project_root)
        for s in children:
            item = self._make_item(s)
            self.addTopLevelItem(item)
            if s.type == "directory":
                item.setChildIndicatorPolicy(
                    QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
                )

    def _make_item(self, summary: object) -> QTreeWidgetItem:
        from paranoid.storage.models import Summary

        s = summary
        if not isinstance(s, Summary):
            return QTreeWidgetItem()
        path_str = s.path
        name = Path(path_str).name or path_str
        item = QTreeWidgetItem([name])
        item.setData(0, self.PATH_ROLE, path_str)
        item.setData(0, self.TYPE_ROLE, s.type)
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
        refresh_act = QAction("Refresh", self)
        refresh_act.setEnabled(bool(path))
        refresh_act.triggered.connect(self.refresh_selected_node)
        menu.addAction(refresh_act)
        resum_act = QAction("Re-summarize", self)
        resum_act.setEnabled(bool(path))
        resum_act.triggered.connect(self._request_re_summarize)
        menu.addAction(resum_act)
        menu.exec(self.viewport().mapToGlobal(position))

    def _copy_path(self) -> None:
        path = self.selected_path()
        if path:
            QApplication.clipboard().setText(path)

    def refresh_selected_node(self) -> None:
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
