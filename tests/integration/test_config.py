"""Integration tests: paranoid config --show (requires initialized project)."""

from __future__ import annotations

import json
import io
from pathlib import Path
from unittest.mock import patch

import pytest

from paranoid.commands.config_cmd import run as config_run
from paranoid.commands.init_cmd import run as init_run


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


def test_config_show_after_init(fixture_project: Path) -> None:
    """Init first, then config --show; output is valid JSON with expected keys."""
    init_args = type("Args", (), {"path": fixture_project})()
    init_run(init_args)
    buf = io.StringIO()
    args = type("Args", (), {
        "path": fixture_project,
        "show": True,
        "set_key": None,
        "add_key": None,
        "remove_key": None,
        "global_": False,
    })()
    with patch("paranoid.commands.config_cmd.sys.stdout", buf):
        config_run(args)
    out = buf.getvalue()
    # Output is "# Config: ..." then JSON; parse from first {
    start = out.find("{")
    assert start >= 0, "Expected JSON in config output"
    data = json.loads(out[start:])
    assert "default_model" in data
    assert "ignore" in data
    assert "builtin_patterns" in data["ignore"]
