"""Unit tests for hashing (content hash, tree hash, change detection)."""

from __future__ import annotations

from pathlib import Path

import pytest

from paranoid.storage import SQLiteStorage, Summary
from paranoid.utils.hashing import content_hash, needs_summarization, tree_hash


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


def _summary(path: str, type_: str = "file", hash_: str = "abc123", **kwargs: object) -> Summary:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    h = kwargs.pop("hash", hash_)
    return Summary(
        path=path,
        type=type_,
        hash=h,
        description="Summary",
        model="qwen3:8b",
        prompt_version="v1",
        generated_at=now,
        updated_at=now,
        **kwargs,
    )


# --- content_hash ---


def test_content_hash_deterministic(tmp_path: Path) -> None:
    """Same file content produces the same hash."""
    f = tmp_path / "same.py"
    f.write_text("print('hello')")
    h1 = content_hash(f)
    h2 = content_hash(f)
    assert h1 == h2
    assert len(h1) == 64
    assert all(c in "0123456789abcdef" for c in h1)


def test_content_hash_different_content_different_hash(tmp_path: Path) -> None:
    """Different content produces different hash."""
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("x")
    b.write_text("y")
    assert content_hash(a) != content_hash(b)


def test_content_hash_binary_safe(tmp_path: Path) -> None:
    """Binary and unicode contents are hashed from raw bytes."""
    binary = tmp_path / "bin"
    binary.write_bytes(b"\x00\xff\xfe\x00")
    unicode_file = tmp_path / "utf8.txt"
    unicode_file.write_text("café 日本語", encoding="utf-8")
    h_bin = content_hash(binary)
    h_utf = content_hash(unicode_file)
    assert len(h_bin) == 64
    assert len(h_utf) == 64
    assert h_bin != h_utf


def test_content_hash_not_file_raises(tmp_path: Path) -> None:
    """Passing a directory or missing path raises ValueError."""
    with pytest.raises(ValueError, match="Not a file"):
        content_hash(tmp_path)
    missing = tmp_path / "missing.txt"
    with pytest.raises(ValueError, match="Not a file"):
        content_hash(missing)


# --- tree_hash ---


def test_tree_hash_empty_directory(storage: SQLiteStorage, project_root: Path) -> None:
    """Empty directory (no children in storage) has deterministic hash."""
    base = (project_root / "src").as_posix()
    h = tree_hash(base, storage)
    assert len(h) == 64
    # Same again
    h2 = tree_hash(base, storage)
    assert h == h2


def test_tree_hash_from_children(storage: SQLiteStorage, project_root: Path) -> None:
    """Tree hash is SHA-256 of sorted child hashes."""
    base = (project_root / "src").as_posix()
    storage.set_summary(_summary(f"{base}/a.py", hash="aaa"))
    storage.set_summary(_summary(f"{base}/b.py", hash="bbb"))
    storage.set_summary(_summary(f"{base}/sub", type_="directory", hash="ccc"))
    h = tree_hash(base, storage)
    assert len(h) == 64
    # Order of children should not matter (we sort by hash)
    storage.set_summary(_summary(f"{base}/b.py", hash="bbb"))
    storage.set_summary(_summary(f"{base}/a.py", hash="aaa"))
    h2 = tree_hash(base, storage)
    assert h == h2


def test_tree_hash_propagates_change(storage: SQLiteStorage, project_root: Path) -> None:
    """Changing a child's hash changes the directory's tree hash."""
    base = (project_root / "src").as_posix()
    storage.set_summary(_summary(f"{base}/foo.py", hash="old"))
    h_before = tree_hash(base, storage)
    storage.set_summary(_summary(f"{base}/foo.py", hash="new"))
    h_after = tree_hash(base, storage)
    assert h_before != h_after


# --- needs_summarization ---


def test_needs_summarization_missing_returns_true(storage: SQLiteStorage, project_root: Path) -> None:
    """No stored summary → needs summarization."""
    path = (project_root / "new.py").as_posix()
    assert needs_summarization(path, "anyhash", storage) is True


def test_needs_summarization_same_hash_returns_false(storage: SQLiteStorage, project_root: Path) -> None:
    """Stored hash equals current hash → skip."""
    path = (project_root / "unchanged.py").as_posix()
    storage.set_summary(_summary(path, hash="same"))
    assert needs_summarization(path, "same", storage) is False


def test_needs_summarization_different_hash_returns_true(storage: SQLiteStorage, project_root: Path) -> None:
    """Stored hash differs from current hash → needs summarization."""
    path = (project_root / "changed.py").as_posix()
    storage.set_summary(_summary(path, hash="old"))
    assert needs_summarization(path, "new", storage) is True


def test_needs_summarization_accepts_path_object(storage: SQLiteStorage, project_root: Path) -> None:
    """Path can be Path or str."""
    path = project_root / "p.py"
    path_str = path.as_posix()
    storage.set_summary(_summary(path_str, hash="h"))
    assert needs_summarization(path, "h", storage) is False
    assert needs_summarization(path_str, "h", storage) is False


def test_needs_summarization_smart_invalidation_context_change(
    storage: SQLiteStorage, project_root: Path
) -> None:
    """When context_level=1 and context changed (e.g. more callers), needs resummary."""
    from paranoid.commands.analyze import run as analyze_run
    from paranoid.commands.init_cmd import run as init_run

    # Create a file with entities and calls
    src = project_root / "src"
    src.mkdir()
    py_file = src / "mod.py"
    py_file.write_text("def f(): pass\ndef g(): f()\n")
    init_run(type("Args", (), {"path": project_root})())
    analyze_run(type("Args", (), {"path": project_root, "force": True, "verbose": False, "dry_run": False})())

    path_str = py_file.resolve().as_posix()
    storage.set_summary(_summary(path_str, hash="h123", context_level=1))
    # Store context with 0 callers (simulate old state)
    storage.set_summary_context(path_str, "imp_hash", 0, 1, "1")

    config = {
        "smart_invalidation": {
            "callers_threshold": 1,
            "callees_threshold": 3,
            "re_summarize_on_imports_change": True,
        }
    }
    # Current graph has callers (g calls f) - should trigger resummary
    assert needs_summarization(path_str, "h123", storage, config) is True


def test_needs_summarization_smart_invalidation_no_context_change(
    storage: SQLiteStorage, project_root: Path
) -> None:
    """When context_level=1 and context unchanged, no resummary (same hash)."""
    from paranoid.llm.graph_context import SUMMARY_CONTEXT_VERSION, compute_file_context_snapshot

    path_str = (project_root / "x.py").as_posix()
    storage.set_summary(_summary(path_str, hash="h", context_level=1))
    snapshot = compute_file_context_snapshot(storage, path_str)
    if snapshot is None:
        # No graph data - smart invalidation won't trigger
        storage.set_summary_context(path_str, "hash", 0, 0, SUMMARY_CONTEXT_VERSION)
    else:
        storage.set_summary_context(
            path_str,
            snapshot.imports_hash,
            snapshot.callers_count,
            snapshot.callees_count,
            SUMMARY_CONTEXT_VERSION,
        )

    config = {"smart_invalidation": {"callers_threshold": 3, "callees_threshold": 3}}
    # Same hash, context matches (or no graph) -> no resummary
    assert needs_summarization(path_str, "h", storage, config) is False
