"""Unit tests for storage layer (SQLite CRUD, list_children, ignore_patterns, metadata)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from paranoid.storage import SQLiteStorage, Summary
from paranoid.storage.models import IgnorePattern, ProjectStats


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


def _summary(
    path: str,
    type_: str = "file",
    hash_: str = "abc123",
    description: str = "A summary.",
    **kwargs: object,
) -> Summary:
    now = datetime.now(timezone.utc).isoformat()
    # Pop known args so we don't pass them twice (Summary uses 'hash', we use hash_)
    hash_val = kwargs.pop("hash", hash_)
    model = kwargs.pop("model", "qwen3:8b")
    return Summary(
        path=path,
        type=type_,
        hash=hash_val,
        description=description,
        model=model,
        prompt_version="v1",
        generated_at=now,
        updated_at=now,
        **kwargs,
    )


def test_set_and_get_summary(storage: SQLiteStorage, project_root: Path) -> None:
    path = (project_root / "src" / "foo.py").as_posix()
    s = _summary(path, file_extension=".py")
    storage.set_summary(s)
    got = storage.get_summary(path)
    assert got is not None
    assert got.path == s.path
    assert got.type == s.type
    assert got.hash == s.hash
    assert got.description == s.description
    assert got.file_extension == ".py"


def test_get_summary_missing_returns_none(storage: SQLiteStorage, project_root: Path) -> None:
    missing = (project_root / "nonexistent.py").as_posix()
    assert storage.get_summary(missing) is None


def test_set_summary_upserts(storage: SQLiteStorage, project_root: Path) -> None:
    path = (project_root / "src" / "bar.py").as_posix()
    storage.set_summary(_summary(path, description="First"))
    storage.set_summary(_summary(path, description="Second", hash="def456"))
    got = storage.get_summary(path)
    assert got is not None
    assert got.description == "Second"
    assert got.hash == "def456"


def test_delete_summary(storage: SQLiteStorage, project_root: Path) -> None:
    path = (project_root / "src" / "baz.py").as_posix()
    storage.set_summary(_summary(path))
    assert storage.get_summary(path) is not None
    storage.delete_summary(path)
    assert storage.get_summary(path) is None


def test_delete_summary_no_op_if_missing(storage: SQLiteStorage, project_root: Path) -> None:
    missing = (project_root / "missing.py").as_posix()
    storage.delete_summary(missing)  # should not raise


def test_list_children_direct_only(storage: SQLiteStorage, project_root: Path) -> None:
    base = (project_root / "src").as_posix()
    storage.set_summary(_summary(f"{base}/foo.py", hash="h1"))
    storage.set_summary(_summary(f"{base}/bar.py", hash="h2"))
    storage.set_summary(_summary(f"{base}/subdir", type_="directory", hash="h3"))
    storage.set_summary(_summary(f"{base}/subdir/nested.py", hash="h4"))

    children = storage.list_children(base)
    paths = {c.path for c in children}
    assert paths == {f"{base}/foo.py", f"{base}/bar.py", f"{base}/subdir"}
    assert f"{base}/subdir/nested.py" not in paths


def test_list_children_empty(storage: SQLiteStorage, project_root: Path) -> None:
    empty = (project_root / "empty").as_posix()
    assert storage.list_children(empty) == []


def test_list_children_normalizes_path(storage: SQLiteStorage, project_root: Path) -> None:
    base = (project_root / "src").as_posix()
    storage.set_summary(_summary(f"{base}/a.py", hash="h1"))
    storage.set_summary(_summary(f"{base}/b.py", hash="h2"))
    # Pass path without trailing slash
    children = storage.list_children(base)
    assert len(children) == 2
    # Pass path with trailing slash (implementation normalizes)
    children2 = storage.list_children(base + "/")
    assert len(children2) == 2


def test_metadata_get_set(storage: SQLiteStorage) -> None:
    assert storage.get_metadata("project_root") is not None  # set by init
    assert storage.get_metadata("custom_key") is None
    storage.set_metadata("custom_key", "custom_value")
    assert storage.get_metadata("custom_key") == "custom_value"


def test_metadata_overwrite(storage: SQLiteStorage) -> None:
    storage.set_metadata("k", "v1")
    storage.set_metadata("k", "v2")
    assert storage.get_metadata("k") == "v2"


def test_add_and_get_ignore_patterns(storage: SQLiteStorage) -> None:
    storage.add_ignore_pattern("*.pyc", "file")
    storage.add_ignore_pattern("node_modules/", "file")
    patterns = storage.get_ignore_patterns()
    assert len(patterns) == 2
    pat_strs = [(p.pattern, p.source) for p in patterns]
    assert ("*.pyc", "file") in pat_strs
    assert ("node_modules/", "file") in pat_strs
    assert all(p.added_at for p in patterns)
    assert all(p.id is not None for p in patterns)


def test_storage_creates_paranoid_dir(project_root: Path) -> None:
    assert not (project_root / ".paranoid-coder").exists()
    with SQLiteStorage(project_root) as st:
        st.get_metadata("project_root")
    assert (project_root / ".paranoid-coder").exists()
    assert (project_root / ".paranoid-coder" / "summaries.db").exists()


def test_summary_needs_update_stored(storage: SQLiteStorage, project_root: Path) -> None:
    path = (project_root / "x.py").as_posix()
    s = _summary(path, needs_update=True)
    storage.set_summary(s)
    got = storage.get_summary(path)
    assert got is not None
    assert got.needs_update is True


def test_get_stats_empty(storage: SQLiteStorage) -> None:
    stats = storage.get_stats()
    assert isinstance(stats, ProjectStats)
    assert stats.count_by_type == {}
    assert stats.last_updated_at is None
    assert stats.model_breakdown == []


def test_get_stats_count_by_type_and_model(storage: SQLiteStorage, project_root: Path) -> None:
    base = (project_root / "src").as_posix()
    storage.set_summary(_summary(f"{base}/a.py", hash="h1", model="qwen3:8b"))
    storage.set_summary(_summary(f"{base}/b.py", hash="h2", model="qwen3:8b"))
    storage.set_summary(_summary(base, type_="directory", hash="h3", model="qwen2:7b"))

    stats = storage.get_stats()
    assert stats.count_by_type == {"file": 2, "directory": 1}
    assert stats.last_updated_at is not None
    assert set(stats.model_breakdown) == {("qwen3:8b", 2), ("qwen2:7b", 1)}


def test_get_stats_scoped_by_path(storage: SQLiteStorage, project_root: Path) -> None:
    base = (project_root / "src").as_posix()
    storage.set_summary(_summary(f"{base}/foo.py", hash="h1"))
    storage.set_summary(_summary(f"{base}/sub/x.py", hash="h2"))
    storage.set_summary(_summary(f"{base}/sub", type_="directory", hash="h3"))
    storage.set_summary(_summary(base, type_="directory", hash="h4"))

    sub = f"{base}/sub"
    stats_sub = storage.get_stats(scope_path=sub)
    assert stats_sub.count_by_type == {"file": 1, "directory": 1}

    stats_base = storage.get_stats(scope_path=base)
    assert stats_base.count_by_type == {"file": 2, "directory": 2}


def test_get_all_summaries_empty(storage: SQLiteStorage) -> None:
    assert storage.get_all_summaries() == []
    assert storage.get_all_summaries(scope_path="/some/path") == []


def test_get_all_summaries_scoped(storage: SQLiteStorage, project_root: Path) -> None:
    base = (project_root / "src").as_posix()
    storage.set_summary(_summary(f"{base}/a.py", hash="h1"))
    storage.set_summary(_summary(f"{base}/sub/x.py", hash="h2"))
    storage.set_summary(_summary(f"{base}/sub", type_="directory", hash="h3"))
    storage.set_summary(_summary(base, type_="directory", hash="h4"))

    all_summaries = storage.get_all_summaries(scope_path=base)
    paths = [s.path for s in all_summaries]
    assert len(paths) == 4
    assert base in paths
    assert f"{base}/a.py" in paths
    assert f"{base}/sub" in paths
    assert f"{base}/sub/x.py" in paths

    sub = f"{base}/sub"
    sub_summaries = storage.get_all_summaries(scope_path=sub)
    assert len(sub_summaries) == 2
    assert {s.path for s in sub_summaries} == {sub, f"{sub}/x.py"}
