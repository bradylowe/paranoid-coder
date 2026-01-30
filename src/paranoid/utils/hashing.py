"""Content and tree hashing for change detection (SHA-256)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from paranoid.storage.base import Storage


def content_hash(path: Path | str) -> str:
    """Compute SHA-256 hash of file contents. Binary-safe (reads raw bytes)."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Not a file: {path}")
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()


def tree_hash(directory_path: Path | str, storage: Storage) -> str:
    """
    Compute hash for a directory from its children's hashes in storage.

    Algorithm (per project plan):
    1. Get direct children of the directory from storage.
    2. Collect each child's hash.
    3. Sort hashes for deterministic ordering.
    4. SHA-256 of the concatenated sorted hashes.

    Any change to any descendant propagates up to all ancestors.
    """
    directory_path = Path(directory_path).as_posix()
    children = storage.list_children(directory_path)
    child_hashes = sorted(c.hash for c in children)
    combined = "".join(child_hashes)
    return hashlib.sha256(combined.encode()).hexdigest()


def current_tree_hash(directory_path: Path | str, storage: Storage) -> str:
    """
    Compute the *current* hash of a directory from actual disk content of its
    descendants (content_hash for files, current_tree_hash for subdirs). Use this
    to detect if a directory is stale when a descendant has changed on disk.
    """
    directory_path = Path(directory_path).as_posix()
    children = storage.list_children(directory_path)
    hashes: list[str] = []
    for c in children:
        try:
            if c.type == "file":
                hashes.append(content_hash(Path(c.path)))
            else:
                hashes.append(current_tree_hash(c.path, storage))
        except (ValueError, OSError):
            hashes.append("__missing__")
    combined = "".join(sorted(hashes))
    return hashlib.sha256(combined.encode()).hexdigest()


def needs_summarization(
    path: Path | str,
    current_hash: str,
    storage: Storage,
) -> bool:
    """
    Return True if the item needs (re-)summarization: missing or hash changed.
    """
    path_str = Path(path).as_posix()
    existing = storage.get_summary(path_str)
    if existing is None:
        return True
    return existing.hash != current_hash
