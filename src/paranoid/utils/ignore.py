"""Ignore pattern support: .paranoidignore, .gitignore (gitignore syntax), builtin and additional patterns."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pathspec import PathSpec

if TYPE_CHECKING:
    from paranoid.storage.base import Storage

PARANOIDIGNORE = ".paranoidignore"
GITIGNORE = ".gitignore"


def parse_ignore_file(path: Path) -> list[str]:
    """
    Read a gitignore-style file and return non-empty pattern lines (strip comments and blanks).
    """
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    patterns: list[str] = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        patterns.append(s)
    return patterns


def load_patterns(project_root: Path, config: dict) -> list[tuple[str, str]]:
    """
    Build combined pattern list from config and files.

    Returns list of (pattern, source) where source is 'builtin', 'file', 'gitignore', or 'additional'.
    Respects ignore.use_gitignore for reading .gitignore.
    """
    project_root = Path(project_root).resolve()
    ignore_cfg = config.get("ignore", {}) or {}
    use_gitignore = ignore_cfg.get("use_gitignore", True)
    builtin = list(ignore_cfg.get("builtin_patterns", []) or [])
    additional = list(ignore_cfg.get("additional_patterns", []) or [])

    result: list[tuple[str, str]] = []
    for p in builtin:
        result.append((p, "builtin"))
    for p in parse_ignore_file(project_root / PARANOIDIGNORE):
        result.append((p, "file"))
    if use_gitignore:
        for p in parse_ignore_file(project_root / GITIGNORE):
            result.append((p, "gitignore"))
    for p in additional:
        result.append((p, "additional"))
    return result


def build_spec(patterns: list[str]) -> PathSpec:
    """Build a PathSpec from pattern strings (gitignore-style)."""
    return PathSpec.from_lines("gitignore", patterns)


def is_ignored(
    path: Path | str,
    project_root: Path | str,
    spec: PathSpec,
) -> bool:
    """
    Return True if the path is ignored by the given spec.

    path and project_root can be Path or str. path should be absolute or relative to project_root;
    it is made relative to project_root and normalised to posix for matching.
    """
    path = Path(path).resolve()
    root = Path(project_root).resolve()
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    # Normalise to posix string (forward slashes) for pathspec
    rel_str = rel.as_posix()
    if spec.match_file(rel_str):
        return True
    # Try with trailing slash so directory-only patterns (e.g. "node_modules/") match
    # when given the directory path (works even if path doesn't exist on disk)
    if not rel_str.endswith("/") and spec.match_file(rel_str + "/"):
        return True
    return False


def sync_patterns_to_storage(
    patterns_with_source: list[tuple[str, str]],
    storage: Storage,
) -> None:
    """
    Sync combined patterns to storage by source: replace all patterns for each source
    that appears in the list with the current set.
    """
    by_source: dict[str, list[str]] = {}
    for pattern, source in patterns_with_source:
        by_source.setdefault(source, []).append(pattern)
    for source, patterns in by_source.items():
        storage.set_ignore_patterns_for_source(source, patterns)
