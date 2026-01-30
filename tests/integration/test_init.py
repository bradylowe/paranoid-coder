"""Integration test: paranoid init creates .paranoid-coder and DB."""

from __future__ import annotations

from pathlib import Path

import pytest

from paranoid.commands.init_cmd import run as init_run
from paranoid.config import PARANOID_DIR, find_project_root


def test_init_creates_paranoid_dir_and_db(tmp_path: Path) -> None:
    """Run init on a directory; verify .paranoid-coder and summaries.db exist."""
    init_args = type("Args", (), {"path": tmp_path})()
    init_run(init_args)
    db_dir = tmp_path / PARANOID_DIR
    db_path = db_dir / "summaries.db"
    assert db_dir.is_dir()
    assert db_path.is_file()
    assert find_project_root(tmp_path) == tmp_path


def test_init_on_subpath_creates_in_that_directory(tmp_path: Path) -> None:
    """Init with path=dir/sub creates .paranoid-coder in sub (get_project_root returns the path given)."""
    sub = tmp_path / "sub"
    sub.mkdir()
    init_args = type("Args", (), {"path": sub})()
    init_run(init_args)
    db_dir = sub / PARANOID_DIR
    assert db_dir.is_dir()
    assert find_project_root(sub) == sub
