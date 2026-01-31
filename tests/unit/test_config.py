"""Unit tests for config (default_config, find_project_root, get_project_root, resolve_path)."""

from __future__ import annotations

from pathlib import Path

import pytest

from paranoid.config import (
    PARANOID_DIR,
    default_config,
    find_project_root,
    get_project_root,
    project_config_path,
    resolve_path,
)


def test_default_config() -> None:
    cfg = default_config()
    assert "default_model" in cfg
    assert cfg["default_model"] == "qwen2.5-coder:7b"
    assert "ollama_host" in cfg
    assert "ignore" in cfg
    assert "builtin_patterns" in cfg["ignore"]
    assert any(".paranoid-coder" in p for p in cfg["ignore"]["builtin_patterns"])


def test_resolve_path(tmp_path: Path) -> None:
    p = tmp_path / "sub" / ".." / "sub"
    assert resolve_path(p).resolve() == (tmp_path / "sub").resolve()


def test_get_project_root_file(tmp_path: Path) -> None:
    f = tmp_path / "file.txt"
    f.write_text("x")
    assert get_project_root(f) == tmp_path.resolve()


def test_get_project_root_dir(tmp_path: Path) -> None:
    d = tmp_path / "dir"
    d.mkdir()
    assert get_project_root(d) == d.resolve()


def test_find_project_root_not_found(tmp_path: Path) -> None:
    """No .paranoid-coder in hierarchy returns None."""
    (tmp_path / "a" / "b").mkdir(parents=True)
    assert find_project_root(tmp_path / "a" / "b") is None


def test_find_project_root_found(tmp_path: Path) -> None:
    """Finds directory containing .paranoid-coder."""
    (tmp_path / PARANOID_DIR).mkdir(parents=True)
    (tmp_path / "src" / "deep").mkdir(parents=True)
    root = find_project_root(tmp_path / "src" / "deep")
    assert root is not None
    assert root == tmp_path.resolve()
    assert (root / PARANOID_DIR).is_dir()


def test_find_project_root_from_file(tmp_path: Path) -> None:
    (tmp_path / PARANOID_DIR).mkdir(parents=True)
    f = tmp_path / "src" / "foo.py"
    f.parent.mkdir(parents=True)
    f.write_text("x")
    root = find_project_root(f)
    assert root is not None
    assert root == tmp_path.resolve()


def test_project_config_path(tmp_path: Path) -> None:
    expected = tmp_path / PARANOID_DIR / "config.json"
    assert project_config_path(tmp_path) == expected
