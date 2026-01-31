"""Integration tests: paranoid prompts --list (requires initialized project)."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest

from paranoid.commands.init_cmd import run as init_run
from paranoid.commands.prompts_cmd import run as prompts_run


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


def test_prompts_list_after_init(fixture_project: Path) -> None:
    """Init first, then prompts --list; output lists prompt keys (e.g. python:file)."""
    init_args = type("Args", (), {"path": fixture_project})()
    init_run(init_args)
    buf = io.StringIO()
    args = type("Args", (), {"path": fixture_project, "edit": None})()
    with patch("paranoid.commands.prompts_cmd.sys.stdout", buf):
        prompts_run(args)
    out = buf.getvalue()
    assert "python:file" in out
    assert "python:directory" in out or "built-in" in out
    assert "Placeholders:" in out
