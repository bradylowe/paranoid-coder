"""Shared utilities: hashing, path normalization, ignore patterns."""

from paranoid.utils.hashing import content_hash, needs_summarization, tree_hash
from paranoid.utils.ignore import (
    build_spec,
    is_ignored,
    load_patterns,
    parse_ignore_file,
    sync_patterns_to_storage,
)

__all__ = [
    "build_spec",
    "content_hash",
    "is_ignored",
    "load_patterns",
    "needs_summarization",
    "parse_ignore_file",
    "sync_patterns_to_storage",
    "tree_hash",
]
