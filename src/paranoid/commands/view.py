"""Launch the summaries viewer."""

from __future__ import annotations

import sys
from argparse import Namespace

from paranoid.config import require_project_root


def run(args: Namespace) -> None:
    """Run the view command: launch PyQt6 viewer for project summaries."""
    project_root = require_project_root(args.path)
    try:
        from paranoid.storage.sqlite import SQLiteStorage
        from paranoid.viewer.app import run_viewer
    except ImportError as e:
        if "PyQt6" in str(e) or "pyqt6" in str(e).lower():
            print(
                "Viewer requires PyQt6. Install with: pip install paranoid-coder[viewer]",
                file=sys.stderr,
            )
        else:
            print(f"Viewer failed to load: {e}", file=sys.stderr)
        sys.exit(1)
    with SQLiteStorage(project_root) as storage:
        run_viewer(project_root, storage)
