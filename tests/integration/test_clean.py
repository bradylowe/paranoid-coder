"""Integration tests: paranoid clean (dry-run and actual)."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest

from paranoid.commands.clean import run as clean_run
from paranoid.commands.init_cmd import run as init_run
from paranoid.commands.summarize import run as summarize_run
from paranoid.storage import SQLiteStorage


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TESTING_GROUNDS = REPO_ROOT / "testing_grounds"


@pytest.fixture
def fixture_project(tmp_path: Path) -> Path:
    if not TESTING_GROUNDS.is_dir():
        pytest.skip("testing_grounds not found")
    import shutil
    dest = tmp_path / "project"
    shutil.copytree(TESTING_GROUNDS, dest, ignore=shutil.ignore_patterns(".paranoid-coder"))
    return dest


@patch("paranoid.commands.summarize.llm_summarize_file", side_effect=lambda path, content, model, **kw: ("Mock file summary.", model))
@patch("paranoid.commands.summarize.llm_summarize_directory", side_effect=lambda path, children, model, **kw: ("Mock dir summary.", model))
def test_clean_dry_run_does_not_delete(mock_dir, mock_file, fixture_project: Path) -> None:
    """Init, summarize (mocked), then clean --pruned --dry-run; DB unchanged."""
    init_args = type("Args", (), {"path": fixture_project})()
    init_run(init_args)
    args_sum = type("Args", (), {
        "paths": [fixture_project],
        "model": "qwen2.5-coder:7b",
        "dry_run": False,
        "verbose": False,
        "quiet": True,
    })()
    summarize_run(args_sum)
    with SQLiteStorage(fixture_project) as storage:
        count_before = len(storage.get_all_summaries())

    args_clean = type("Args", (), {
        "path": fixture_project,
        "pruned": True,
        "stale": False,
        "days": 30,
        "model": None,
        "dry_run": True,
    })()
    clean_run(args_clean)

    with SQLiteStorage(fixture_project) as storage:
        count_after = len(storage.get_all_summaries())
    assert count_after == count_before
