"""Initialize a paranoid project (.paranoid-coder and DB). This is the ONLY way to create them."""

from __future__ import annotations

import sys
from pathlib import Path

from paranoid.config import PARANOID_DIR, get_project_root
from paranoid.storage import SQLiteStorage


def run(args) -> None:
    """Run the init command: create .paranoid-coder and summaries.db with metadata."""
    path = getattr(args, "path", Path(".")).resolve()
    project_root = get_project_root(path)
    project_root = project_root.resolve()

    if not project_root.is_dir() and not path.is_file():
        print("Error: Path is not an existing directory or file.", file=sys.stderr)
        sys.exit(1)

    # Opening storage creates .paranoid-coder and summaries.db with schema + metadata
    storage = SQLiteStorage(project_root)
    storage._connect()
    storage.close()

    print(f"Initialized paranoid project at {project_root.as_posix()}")
    print(f"  {project_root / PARANOID_DIR}/")

