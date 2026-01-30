"""Unit tests for ignore patterns (parse .paranoidignore, match paths, storage sync)."""

from __future__ import annotations

from pathlib import Path

import pytest

from paranoid.storage import SQLiteStorage
from paranoid.utils.ignore import (
    build_spec,
    is_ignored,
    load_patterns,
    parse_ignore_file,
    sync_patterns_to_storage,
)


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Temporary directory as project root."""
    return tmp_path


@pytest.fixture
def storage(project_root: Path) -> SQLiteStorage:
    """SQLiteStorage for a temp project root. Closed after test."""
    s = SQLiteStorage(project_root)
    s._connect()
    yield s
    s.close()


# --- parse_ignore_file ---


def test_parse_ignore_file_missing_returns_empty(tmp_path: Path) -> None:
    """Missing file returns empty list."""
    assert parse_ignore_file(tmp_path / "nonexistent") == []


def test_parse_ignore_file_strips_comments_and_blanks(tmp_path: Path) -> None:
    """Comments and blank lines are stripped."""
    f = tmp_path / ".paranoidignore"
    f.write_text("# comment\n\n*.pyc\n  \n__pycache__/\n# another\n")
    patterns = parse_ignore_file(f)
    assert patterns == ["*.pyc", "__pycache__/"]


def test_parse_ignore_file_preserves_patterns(tmp_path: Path) -> None:
    """Valid patterns are preserved as-is."""
    f = tmp_path / ".gitignore"
    f.write_text("node_modules/\n*.pyc\n.env\n")
    assert parse_ignore_file(f) == ["node_modules/", "*.pyc", ".env"]


# --- build_spec / is_ignored ---


def test_is_ignored_empty_spec_never_matches(project_root: Path) -> None:
    """Empty spec matches nothing."""
    spec = build_spec([])
    assert is_ignored(project_root / "foo.py", project_root, spec) is False
    assert is_ignored(project_root / "src" / "bar.py", project_root, spec) is False


def test_is_ignored_glob_file(project_root: Path) -> None:
    """*.pyc matches .pyc files."""
    spec = build_spec(["*.pyc"])
    assert is_ignored(project_root / "x.pyc", project_root, spec) is True
    assert is_ignored(project_root / "src" / "y.pyc", project_root, spec) is True
    assert is_ignored(project_root / "x.py", project_root, spec) is False


def test_is_ignored_directory_pattern(project_root: Path) -> None:
    """node_modules/ matches directory and contents."""
    spec = build_spec(["node_modules/"])
    assert is_ignored(project_root / "node_modules", project_root, spec) is True
    assert is_ignored(project_root / "node_modules" / "foo", project_root, spec) is True
    assert is_ignored(project_root / "src" / "node_modules", project_root, spec) is True
    assert is_ignored(project_root / "src" / "foo.py", project_root, spec) is False


def test_is_ignored_pycache(project_root: Path) -> None:
    """__pycache__/ matches __pycache__ directories."""
    spec = build_spec(["__pycache__/"])
    assert is_ignored(project_root / "__pycache__", project_root, spec) is True
    assert is_ignored(project_root / "src" / "__pycache__" / "bar.cpython-311.pyc", project_root, spec) is True
    assert is_ignored(project_root / "src" / "bar.py", project_root, spec) is False


def test_is_ignored_combined_patterns(project_root: Path) -> None:
    """Multiple patterns work together."""
    spec = build_spec([".git/", ".paranoid-coder/", "*.pyc", "venv/"])
    assert is_ignored(project_root / ".git" / "config", project_root, spec) is True
    assert is_ignored(project_root / ".paranoid-coder" / "summaries.db", project_root, spec) is True
    assert is_ignored(project_root / "x.pyc", project_root, spec) is True
    assert is_ignored(project_root / "venv" / "bin", project_root, spec) is True
    assert is_ignored(project_root / "src" / "main.py", project_root, spec) is False


def test_is_ignored_accepts_str_paths(project_root: Path) -> None:
    """Path and project_root can be str."""
    spec = build_spec(["*.pyc"])
    assert is_ignored((project_root / "a.pyc").as_posix(), project_root.as_posix(), spec) is True


# --- load_patterns ---


def test_load_patterns_builtin_and_additional(project_root: Path) -> None:
    """Config builtin and additional patterns are loaded."""
    config = {
        "ignore": {
            "use_gitignore": False,
            "builtin_patterns": [".git/", ".paranoid-coder/"],
            "additional_patterns": ["vendor/"],
        },
    }
    result = load_patterns(project_root, config)
    assert (".git/", "builtin") in result
    assert (".paranoid-coder/", "builtin") in result
    assert ("vendor/", "additional") in result


def test_load_patterns_reads_paranoidignore(project_root: Path) -> None:
    """Patterns from .paranoidignore are loaded with source 'file'."""
    (project_root / ".paranoidignore").write_text("*.pyc\n__pycache__/\n")
    config = {"ignore": {"use_gitignore": False, "builtin_patterns": [], "additional_patterns": []}}
    result = load_patterns(project_root, config)
    assert ("*.pyc", "file") in result
    assert ("__pycache__/", "file") in result


def test_load_patterns_reads_gitignore_when_enabled(project_root: Path) -> None:
    """When use_gitignore is True, .gitignore is read with source 'gitignore'."""
    (project_root / ".gitignore").write_text("node_modules/\n.env\n")
    config = {"ignore": {"use_gitignore": True, "builtin_patterns": [], "additional_patterns": []}}
    result = load_patterns(project_root, config)
    assert ("node_modules/", "gitignore") in result
    assert (".env", "gitignore") in result


def test_load_patterns_skips_gitignore_when_disabled(project_root: Path) -> None:
    """When use_gitignore is False, .gitignore is not read."""
    (project_root / ".gitignore").write_text("x\n")
    config = {"ignore": {"use_gitignore": False, "builtin_patterns": [], "additional_patterns": []}}
    result = load_patterns(project_root, config)
    assert not any(s == "gitignore" for _, s in result)


# --- sync_patterns_to_storage ---


def test_sync_patterns_to_storage_replaces_by_source(storage: SQLiteStorage, project_root: Path) -> None:
    """Syncing replaces patterns for each source."""
    patterns_with_source = [
        (".git/", "builtin"),
        (".paranoid-coder/", "builtin"),
        ("*.pyc", "file"),
        ("__pycache__/", "file"),
    ]
    sync_patterns_to_storage(patterns_with_source, storage)
    stored = storage.get_ignore_patterns()
    by_source: dict[str, list[str]] = {}
    for p in stored:
        by_source.setdefault(p.source or "", []).append(p.pattern)
    assert set(by_source.get("builtin", [])) == {".git/", ".paranoid-coder/"}
    assert set(by_source.get("file", [])) == {"*.pyc", "__pycache__/"}


def test_sync_patterns_to_storage_replace_updates(storage: SQLiteStorage, project_root: Path) -> None:
    """Second sync with same source replaces previous patterns."""
    sync_patterns_to_storage([("old.pyc", "file")], storage)
    assert len([p for p in storage.get_ignore_patterns() if p.source == "file"]) == 1
    sync_patterns_to_storage([("new.pyc", "file"), ("other/", "file")], storage)
    file_patterns = [p.pattern for p in storage.get_ignore_patterns() if p.source == "file"]
    assert set(file_patterns) == {"new.pyc", "other/"}


# --- integration: load_patterns + build_spec + is_ignored ---


def test_full_flow_paranoidignore_respected(project_root: Path) -> None:
    """Load from config + file, build spec, is_ignored respects .paranoidignore."""
    (project_root / ".paranoidignore").write_text("# test\ntests/\n*_test.py\n")
    config = {"ignore": {"use_gitignore": False, "builtin_patterns": [".git/"], "additional_patterns": []}}
    loaded = load_patterns(project_root, config)
    patterns = [p for p, _ in loaded]
    spec = build_spec(patterns)
    assert is_ignored(project_root / "tests" / "unit" / "foo.py", project_root, spec) is True
    assert is_ignored(project_root / "foo_test.py", project_root, spec) is True
    assert is_ignored(project_root / "src" / "main.py", project_root, spec) is False
    assert is_ignored(project_root / ".git" / "HEAD", project_root, spec) is True
