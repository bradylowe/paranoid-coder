"""Integration tests: paranoid export (JSON/CSV) after init and summarize."""

from __future__ import annotations

import csv
import json
import io
from pathlib import Path
from unittest.mock import patch

import pytest

from paranoid.commands.export import run as export_run
from paranoid.commands.init_cmd import run as init_run
from paranoid.commands.summarize import run as summarize_run

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TESTING_GROUNDS = REPO_ROOT / "testing_grounds"


@pytest.fixture
def fixture_project(tmp_path: Path) -> Path:
    """Copy testing_grounds into tmp_path."""
    if not TESTING_GROUNDS.is_dir():
        pytest.skip("testing_grounds not found")
    import shutil
    dest = tmp_path / "project"
    shutil.copytree(TESTING_GROUNDS, dest)
    return dest


@patch("paranoid.commands.summarize.llm_summarize_file", side_effect=lambda path, content, model, **kw: ("Mock file summary.", model))
@patch("paranoid.commands.summarize.llm_summarize_directory", side_effect=lambda path, children, model, **kw: ("Mock dir summary.", model))
def test_export_json_after_summarize(mock_dir, mock_file, fixture_project: Path) -> None:
    """Init, summarize (mocked), then export --format json; stdout is valid JSON array."""
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
    args_exp = type("Args", (), {"path": fixture_project, "format": "json"})()
    with patch("paranoid.commands.export.sys.stdout", buf):
        export_run(args_exp)
    out = buf.getvalue()
    data = json.loads(out)
    assert isinstance(data, list)
    assert len(data) >= 1
    for item in data:
        assert "path" in item
        assert "type" in item
        assert item["type"] in ("file", "directory")
        assert "description" in item
        assert "model" in item


@patch("paranoid.commands.summarize.llm_summarize_file", side_effect=lambda path, content, model, **kw: ("Mock file summary.", model))
@patch("paranoid.commands.summarize.llm_summarize_directory", side_effect=lambda path, children, model, **kw: ("Mock dir summary.", model))
def test_export_csv_after_summarize(mock_dir, mock_file, fixture_project: Path) -> None:
    """Init, summarize (mocked), then export --format csv; stdout is valid CSV with header."""
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
    args_exp = type("Args", (), {"path": fixture_project, "format": "csv"})()
    with patch("paranoid.commands.export.sys.stdout", buf):
        export_run(args_exp)
    out = buf.getvalue()
    reader = csv.DictReader(io.StringIO(out))
    rows = list(reader)
    assert len(rows) >= 1
    assert "path" in rows[0]
    assert "type" in rows[0]
    assert "description" in rows[0]
