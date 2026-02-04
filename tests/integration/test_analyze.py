"""Integration tests for paranoid analyze command (Phase 5B)."""

from __future__ import annotations

from pathlib import Path

import pytest

from paranoid.commands.analyze import run as analyze_run
from paranoid.commands.init_cmd import run as init_run
from paranoid.config import find_project_root
from paranoid.storage import SQLiteStorage


def test_analyze_extracts_entities_and_relationships(tmp_path: Path) -> None:
    """Run init + analyze; verify entities and entity-level relationships are stored."""
    # Create a Python file with call and inheritance
    src = tmp_path / "src"
    src.mkdir()
    py_file = src / "module.py"
    py_file.write_text(
        '''
"""Test module for analyze integration."""
from pathlib import Path

def greet(name: str) -> str:
    """Return greeting."""
    return f"Hello, {name}"

def main() -> None:
    greet("world")

class Base:
    """Base class."""
    pass

class Derived(Base):
    """Derived class."""
    def run(self) -> None:
        greet("derived")
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

    project_root = find_project_root(tmp_path)
    assert project_root is not None
    storage = SQLiteStorage(project_root)
    storage._connect()

    # Check entities
    file_path_str = py_file.resolve().as_posix()
    entities = storage.get_entities_by_file(file_path_str)
    assert len(entities) >= 5  # greet, main, Base, Derived, Derived.run
    names = {e.qualified_name for e in entities}
    assert "greet" in names
    assert "main" in names
    assert "Base" in names
    assert "Derived" in names
    assert "Derived.run" in names

    # Check that CALLS relationships have from_entity_id set
    rows = storage._conn.execute(
        """
        SELECT from_entity_id, to_entity_id, relationship_type, to_file
        FROM code_relationships
        WHERE relationship_type = 'calls'
        """
    ).fetchall()
    assert len(rows) >= 1
    # At least one call should have from_entity_id (main->greet or Derived.run->greet)
    calls_with_caller = [r for r in rows if r["from_entity_id"] is not None]
    assert len(calls_with_caller) >= 1

    # Check that INHERITS relationships have from_entity_id set
    inherits_rows = storage._conn.execute(
        """
        SELECT from_entity_id, to_entity_id, relationship_type, to_file
        FROM code_relationships
        WHERE relationship_type = 'inherits'
        """
    ).fetchall()
    assert len(inherits_rows) >= 1
    assert any(r["from_entity_id"] is not None for r in inherits_rows)

    # Check that at least one call has to_entity_id (when target is in graph)
    calls_with_callee = [r for r in rows if r["to_entity_id"] is not None]
    assert len(calls_with_callee) >= 1  # main->greet or Derived.run->greet


def test_analyze_extracts_js_and_ts_entities(tmp_path: Path) -> None:
    """Run init + analyze on a project with Python, JS, and TS; verify all are parsed."""
    src = tmp_path / "src"
    src.mkdir()

    (src / "main.py").write_text('def hello(): pass\n')
    (src / "util.js").write_text(
        'export function greet(x) { return "hi"; }\n'
    )
    (src / "service.ts").write_text(
        'export function run(): void {}\n'
    )

    init_args = type("Args", (), {"path": tmp_path})()
    init_run(init_args)

    analyze_args = type(
        "Args",
        (),
        {"path": tmp_path, "force": True, "verbose": False, "dry_run": False},
    )()
    analyze_run(analyze_args)

    project_root = find_project_root(tmp_path)
    assert project_root is not None
    storage = SQLiteStorage(project_root)
    storage._connect()

    entities = storage._conn.execute(
        "SELECT file_path, qualified_name, language FROM code_entities"
    ).fetchall()
    paths = {e["file_path"] for e in entities}
    assert any("main.py" in p for p in paths)
    assert any("util.js" in p for p in paths)
    assert any("service.ts" in p for p in paths)

    # Verify analysis metadata is stored
    assert storage.get_metadata("analysis_timestamp") is not None
    assert storage.get_metadata("analysis_parser_version") is not None


def test_analyze_incremental_skips_unchanged_files(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Second run without --force skips unchanged files."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("def hello(): pass\n")

    init_args = type("Args", (), {"path": tmp_path})()
    init_run(init_args)

    # First run: analyze all
    analyze_args = type(
        "Args",
        (),
        {"path": tmp_path, "force": False, "verbose": False, "dry_run": False},
    )()
    analyze_run(analyze_args)
    out1 = capsys.readouterr()
    assert "Analyzed 1 file(s)" in out1.err
    assert "skipped 0 unchanged" in out1.err

    # Second run: skip unchanged
    analyze_run(analyze_args)
    out2 = capsys.readouterr()
    assert "skipped 1 unchanged" in out2.err

    # Modify file: re-analyze that file only
    (src / "main.py").write_text("def hello(): pass\ndef bye(): pass\n")
    analyze_run(analyze_args)
    out3 = capsys.readouterr()
    assert "Analyzed 1 file(s)" in out3.err
    assert "skipped 0 unchanged" in out3.err

    # --force: re-analyze even when unchanged
    (src / "main.py").write_text("def hello(): pass\ndef bye(): pass\n")  # no change
    analyze_args_force = type(
        "Args",
        (),
        {"path": tmp_path, "force": True, "verbose": False, "dry_run": False},
    )()
    analyze_run(analyze_args_force)
    out4 = capsys.readouterr()
    assert "Analyzed 1 file(s)" in out4.err
