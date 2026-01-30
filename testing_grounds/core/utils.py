"""
Common utility functions used across the codebase.
"""

import os
from pathlib import Path


def normalize_path(path: str | Path) -> str:
    """
    Normalize a path to a consistent string form (forward slashes, no redundant parts).
    """
    p = Path(path).resolve()
    return str(p).replace(os.sep, "/")


def ensure_dir(path: str | Path) -> Path:
    """Create directory and parents if they do not exist. Returns the path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_filename(name: str) -> str:
    """Replace characters that are unsafe in filenames with underscores."""
    unsafe = '<>:"/\\|?*'
    for c in unsafe:
        name = name.replace(c, "_")
    return name
