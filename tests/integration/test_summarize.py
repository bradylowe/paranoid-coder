"""Integration tests: paranoid summarize on fixture project (mock Ollama), verify DB.

Requires an initialized project (paranoid init) before summarize; one test verifies
summarize exits with error when no .paranoid-coder exists.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from paranoid.commands.init_cmd import run as init_run
from paranoid.commands.summarize import run as summarize_run
from paranoid.storage import SQLiteStorage


# Fixture project: use testing_grounds from repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TESTING_GROUNDS = REPO_ROOT / "testing_grounds"


@pytest.fixture
def fixture_project(tmp_path: Path) -> Path:
    """Copy testing_grounds into tmp_path so we don't mutate the repo."""
    if not TESTING_GROUNDS.is_dir():
        pytest.skip("testing_grounds not found")
    import shutil
    dest = tmp_path / "project"
    shutil.copytree(TESTING_GROUNDS, dest)
    return dest


@patch("paranoid.commands.summarize.llm_summarize_file", side_effect=lambda path, content, model, **kw: ("Mock file summary.", model))
@patch("paranoid.commands.summarize.llm_summarize_directory", side_effect=lambda path, children, model, **kw: ("Mock dir summary.", model))
def test_summarize_creates_db_and_stores_summaries(mock_dir, mock_file, fixture_project: Path) -> None:
    """Init first, then run summarize (Ollama mocked); verify summaries.db has rows."""
    init_args = type("Args", (), {"path": fixture_project})()
    init_run(init_args)
    args = type("Args", (), {
        "paths": [fixture_project],
        "model": "qwen2.5-coder:7b",
        "dry_run": False,
        "verbose": False,
        "quiet": True,
    })()
    summarize_run(args)
    db_dir = fixture_project / ".paranoid-coder"
    db_path = db_dir / "summaries.db"
    assert db_dir.is_dir(), ".paranoid-coder should exist"
    assert db_path.is_file(), "summaries.db should exist"
    storage = SQLiteStorage(fixture_project)
    storage._connect()
    try:
        # Should have at least one summary (files + dirs)
        conn = storage._connect()
        row = conn.execute("SELECT COUNT(*) FROM summaries").fetchone()
        count = row[0]
        assert count >= 1, "summaries table should have at least one row"
        # Spot-check: get any summary
        row = conn.execute(
            "SELECT path, type, description FROM summaries LIMIT 1"
        ).fetchone()
        assert row is not None
        path, type_, desc = row[0], row[1], row[2]
        assert path
        assert type_ in ("file", "directory")
        assert desc and ("Mock" in desc)
    finally:
        storage.close()


def test_summarize_dry_run_does_not_write_summaries(fixture_project: Path) -> None:
    """Init first; dry-run should not write any summaries (no LLM calls, no summary rows)."""
    init_args = type("Args", (), {"path": fixture_project})()
    init_run(init_args)
    args = type("Args", (), {
        "paths": [fixture_project],
        "model": "qwen2.5-coder:7b",
        "dry_run": True,
        "verbose": False,
        "quiet": True,
    })()
    summarize_run(args)
    storage = SQLiteStorage(fixture_project)
    storage._connect()
    try:
        row = storage._connect().execute("SELECT COUNT(*) FROM summaries").fetchone()
        count = row[0]
        assert count == 0, "dry-run should not write any summary rows"
    finally:
        storage.close()


def test_summarize_without_init_exits_with_error(fixture_project: Path) -> None:
    """Summarize without prior init should exit with error (no .paranoid-coder)."""
    import sys
    from io import StringIO
    args = type("Args", (), {
        "paths": [fixture_project],
        "model": "qwen2.5-coder:7b",
        "dry_run": False,
        "verbose": False,
        "quiet": True,
    })()
    stderr = StringIO()
    old_stderr = sys.stderr
    sys.stderr = stderr
    try:
        with pytest.raises(SystemExit) as exc_info:
            summarize_run(args)
        assert exc_info.value.code == 1
        assert "paranoid init" in stderr.getvalue()
    finally:
        sys.stderr = old_stderr
