"""Integration tests: paranoid stats after init and summarize."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from paranoid.commands.init_cmd import run as init_run
from paranoid.commands.stats import run as stats_run
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
def test_stats_after_summarize_shows_by_type_and_language(mock_dir, mock_file, fixture_project: Path) -> None:
    """Init, summarize (mocked), then stats; output includes By type and By language."""
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

    buf = io.StringIO()
    args_stats = type("Args", (), {"path": fixture_project})()
    with patch("paranoid.commands.stats.sys.stdout", buf):
        stats_run(args_stats)
    out = buf.getvalue()
    assert "By type:" in out
    assert "files:" in out or "total:" in out
    assert "By language:" in out
    assert "Coverage:" in out
