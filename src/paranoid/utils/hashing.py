"""Content and tree hashing for change detection (SHA-256)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
    config: dict[str, Any] | None = None,
) -> bool:
    """
    Return True if the item needs (re-)summarization: missing, hash changed, or
    (for files with graph context) context changed significantly.

    When config contains smart_invalidation and the summary used graph context
    (context_level=1), also re-summarizes when:
    - imports_hash changed (if re_summarize_on_imports_change)
    - callers_count increased by more than callers_threshold
    - callees_count increased by more than callees_threshold
    """
    path_str = Path(path).as_posix()
    existing = storage.get_summary(path_str)
    if existing is None:
        return True
    if existing.hash != current_hash:
        return True

    # Smart invalidation: check context when summary used graph context
    if config and existing.context_level == 1:
        return _needs_resummary_for_context_change(
            path_str, storage, config.get("smart_invalidation") or {}
        )
    return False


def _needs_resummary_for_context_change(
    path_str: str,
    storage: Storage,
    smart_config: dict[str, Any],
) -> bool:
    """Return True if context changed significantly (imports, callers, callees)."""
    from paranoid.llm.graph_context import (
        SUMMARY_CONTEXT_VERSION,
        compute_file_context_snapshot,
    )

    get_context = getattr(storage, "get_summary_context", None)
    if get_context is None:
        return False

    stored = get_context(path_str)
    if stored is None:
        return False

    current = compute_file_context_snapshot(storage, path_str)
    if current is None:
        return False

    stored_imports_hash, stored_callers, stored_callees, stored_version = stored

    # Context format changed
    if stored_version != SUMMARY_CONTEXT_VERSION:
        return True

    if smart_config.get("re_summarize_on_imports_change", True):
        if current.imports_hash != stored_imports_hash:
            return True

    callers_threshold = smart_config.get("callers_threshold", 3)
    if current.callers_count - stored_callers > callers_threshold:
        return True

    callees_threshold = smart_config.get("callees_threshold", 3)
    if current.callees_count - stored_callees > callees_threshold:
        return True

    return False
