"""Integration tests for paranoid doctor command (Phase 5B)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from paranoid.commands.analyze import run as analyze_run
from paranoid.commands.doctor import run as doctor_run
from paranoid.commands.init_cmd import run as init_run
from paranoid.config import find_project_root


def test_doctor_requires_analyze(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Doctor exits with error when no entities exist (analyze not run)."""
    init_args = type("Args", (), {"path": tmp_path})()
    init_run(init_args)

    doctor_args = type(
        "Args",
        (),
        {"path": tmp_path, "top": None, "format": "text"},
    )()
    with pytest.raises(SystemExit) as exc_info:
        doctor_run(doctor_args)
    assert exc_info.value.code == 1

    out, err = capsys.readouterr()
    assert "No code entities found" in err
    assert "paranoid analyze" in err


def test_doctor_reports_after_analyze(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Doctor scans entities and reports documentation quality."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "module.py").write_text(
        '''
"""Module with mixed docs."""
def documented(x: int) -> str:
    """Has docstring and type hints."""
    return str(x)

def undocumented(y):
    return y

class Foo:
    """Class with docstring."""
    def bar(self) -> None:
        """Method with docstring."""
        pass
'''
    )

    init_args = type("Args", (), {"path": tmp_path})()
    init_run(init_args)

    analyze_args = type(
        "Args",
        (),
        {"path": tmp_path, "force": True, "verbose": False, "dry_run": False},
    )()
    analyze_run(analyze_args)

    doctor_args = type(
        "Args",
        (),
        {"path": tmp_path, "top": 10, "format": "text"},
    )()
    doctor_run(doctor_args)

    out, err = capsys.readouterr()
    assert "Documentation quality report" in out
    assert "Total entities scanned" in out
    assert "Missing docstrings" in out or "Top items by priority" in out
    assert "undocumented" in out or "documented" in out


def test_doctor_json_export(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Doctor --format json outputs valid JSON."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "foo.py").write_text("def bar(): pass\n")

    init_args = type("Args", (), {"path": tmp_path})()
    init_run(init_args)

    analyze_args = type(
        "Args",
        (),
        {"path": tmp_path, "force": True, "verbose": False, "dry_run": False},
    )()
    analyze_run(analyze_args)

    _ = capsys.readouterr()  # Clear output from init/analyze

    doctor_args = type(
        "Args",
        (),
        {"path": tmp_path, "top": 5, "format": "json"},
    )()
    doctor_run(doctor_args)

    out, err = capsys.readouterr()
    data = json.loads(out)
    assert isinstance(data, list)
    assert len(data) >= 1
    item = data[0]
    assert "qualified_name" in item
    assert "has_docstring" in item
    assert "has_examples" in item
    assert "has_type_hints" in item
    assert "priority_score" in item
    assert "file_path" in item
    assert "lineno" in item
