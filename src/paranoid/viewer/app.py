"""Main viewer window: tree, detail, search, menu."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QWidget,
)

from paranoid.config import load_config, update_project_config_value
from paranoid.viewer.detail_widget import DetailWidget
from paranoid.viewer.search_widget import SearchWidget
from paranoid.viewer.tree_widget import SummaryTreeWidget

if TYPE_CHECKING:
    from paranoid.storage.base import Storage


class SummarizeWorker(QThread):
    """Runs `paranoid summarize <path> --model <model> --force` in a subprocess."""

    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, path: str, model: str, parent=None) -> None:
        super().__init__(parent)
        self._path = path
        self._model = model

    def run(self) -> None:
        try:
            # Invoke paranoid CLI with --force so we always re-run the LLM (hash check skipped)
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.argv = ['paranoid', 'summarize', sys.argv[1], '--model', sys.argv[2], '--force']; "
                    "from paranoid.cli import main; main()",
                    self._path,
                    self._model,
                ],
                capture_output=True,
                text=True,
                timeout=3600,
            )
            if result.returncode == 0:
                # Show last line of stderr (e.g. "Done: 3 summarized, 0 skipped") so user sees real result
                out = (result.stderr or "").strip()
                last_line = out.splitlines()[-1] if out else "Done."
                self.finished.emit(True, last_line)
            else:
                msg = result.stderr.strip() or result.stdout.strip() or f"Exit code {result.returncode}"
                self.finished.emit(False, msg)
        except subprocess.TimeoutExpired:
            self.finished.emit(False, "Summarization timed out.")
        except Exception as e:
            self.finished.emit(False, str(e))


def run_viewer(project_root: Path, storage: Storage) -> None:
    """Create QApplication and main window; run event loop."""
    app = QApplication(sys.argv)
    app.setApplicationName("Paranoid Viewer")
    win = ViewerMainWindow(project_root=project_root, storage=storage)
    win.show()
    sys.exit(app.exec())


class ViewerMainWindow(QMainWindow):
    """Main window: menu, tree (left), detail (right), optional search."""

    def __init__(
        self,
        project_root: Path,
        storage: Storage,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._project_root = Path(project_root).resolve()
        self._storage = storage
        self._summarize_worker: SummarizeWorker | None = None
        self.setWindowTitle(f"Paranoid — {self._project_root.name or 'Project'}")
        self._setup_menu()
        self._setup_central()
        self._setup_status_bar()

    def _setup_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        exit_act = QAction("E&xit", self)
        exit_act.setShortcut("Ctrl+Q")
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        view_menu = menubar.addMenu("&View")
        config = load_config(self._project_root)
        show_ignored = config.get("viewer", {}).get("show_ignored", False)
        self._show_ignored_act = QAction("Show ignored paths", self)
        self._show_ignored_act.setCheckable(True)
        self._show_ignored_act.setChecked(show_ignored)
        self._show_ignored_act.triggered.connect(self._on_show_ignored_toggled)
        view_menu.addAction(self._show_ignored_act)

        help_menu = menubar.addMenu("&Help")
        about_act = QAction("&About Paranoid", self)
        about_act.triggered.connect(self._about)
        help_menu.addAction(about_act)

    def _on_show_ignored_toggled(self, checked: bool) -> None:
        update_project_config_value(self._project_root, "viewer.show_ignored", checked)
        self._tree.set_show_ignored(checked)

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "About Paranoid",
            "Paranoid — local-only codebase summarization and analysis.\n\n"
            "Summaries are stored in .paranoid-coder/summaries.db.\n"
            "No code or summaries leave your machine.",
        )

    def _setup_status_bar(self) -> None:
        self._status_bar = self.statusBar()
        self._status_bar.showMessage("Ready")

    def _setup_central(self) -> None:
        central = QWidget(self)
        from PyQt6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        search = SearchWidget(self)
        layout.addWidget(search)

        tree = SummaryTreeWidget(self._storage, self._project_root, self)
        search.connect_filter_changed(tree.set_filter_text)
        detail = DetailWidget(self._storage, self._project_root, self)
        tree.itemSelectionChanged.connect(
            lambda: detail.show_path(tree.selected_path())
        )
        tree.reSummarizeRequested.connect(self._on_re_summarize_requested)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(tree)
        splitter.addWidget(detail)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self.setCentralWidget(central)
        self.resize(900, 600)
        self._tree = tree
        self._detail = detail

    def _on_re_summarize_requested(self, path: str) -> None:
        config = load_config(self._project_root)
        model = config.get("default_model")
        if not model:
            QMessageBox.warning(
                self,
                "Re-summarize",
                "No default model set. Add default_model to your config\n"
                "(e.g. ~/.paranoid/config.json or .paranoid-coder/config.json)\n"
                "or run: paranoid summarize <path> --model <model> from the terminal.",
            )
            return
        if self._summarize_worker and self._summarize_worker.isRunning():
            self._status_bar.showMessage("Summarization already in progress…")
            return
        self._status_bar.showMessage(f"Summarizing {path}…")
        self._summarize_worker = SummarizeWorker(path, model, self)
        self._summarize_worker.finished.connect(self._on_summarize_finished)
        self._summarize_worker.start()

    def _on_summarize_finished(self, success: bool, message: str) -> None:
        self._summarize_worker = None
        self._status_bar.showMessage(message if success else f"Error: {message}", 5000)
        if not success:
            QMessageBox.warning(self, "Re-summarize", message)
        else:
            self._tree.refresh_selected_node()
            self._detail.show_path(self._tree.selected_path())
