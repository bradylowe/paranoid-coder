"""Unit tests for graph query API (Phase 5B)."""

from __future__ import annotations

from pathlib import Path

import pytest

from paranoid.commands.analyze import run as analyze_run
from paranoid.commands.init_cmd import run as init_run
from paranoid.config import find_project_root
from paranoid.graph import GraphQueries
from paranoid.storage import SQLiteStorage


@pytest.fixture
def analyzed_project(tmp_path: Path) -> tuple[Path, SQLiteStorage]:
    """Create project with init + analyze, return (project_root, storage)."""
    src = tmp_path / "src"
    src.mkdir()
    # Module a.py: def greet(), def main() calls greet
    (src / "a.py").write_text(
        '''
"""Module a."""
from src.b import helper

def greet(name: str) -> str:
    return f"Hello, {name}"

def main() -> None:
    greet("world")
'''
    )
    # Module b.py: def helper(), imports from a
    (src / "b.py").write_text(
        '''
"""Module b."""
from src.a import greet

def helper() -> str:
    return greet("x")
'''
    )
    # Module c.py: class Base, class Derived(Base)
    (src / "c.py").write_text(
        '''
"""Module c."""
class Base:
    pass

class Derived(Base):
    def run(self) -> None:
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

    project_root = find_project_root(tmp_path)
    assert project_root is not None
    storage = SQLiteStorage(project_root)
    storage._connect()
    return project_root, storage


def test_get_callers(analyzed_project: tuple[Path, SQLiteStorage]) -> None:
    """get_callers returns who calls a function."""
    project_root, storage = analyzed_project
    gq = GraphQueries(storage, project_root)

    entities = storage.get_entities_by_file(
        str(project_root / "src" / "a.py")
    )
    greet = next(e for e in entities if e.qualified_name == "greet")
    assert greet is not None

    callers = gq.get_callers(greet)
    assert len(callers) >= 1
    names = {c.qualified_name for c in callers}
    assert "main" in names or "helper" in names  # main calls greet, helper (in b.py) calls greet


def test_get_callees(analyzed_project: tuple[Path, SQLiteStorage]) -> None:
    """get_callees returns what a function calls."""
    project_root, storage = analyzed_project
    gq = GraphQueries(storage, project_root)

    entities = storage.get_entities_by_file(
        str(project_root / "src" / "a.py")
    )
    main = next(e for e in entities if e.qualified_name == "main")
    assert main is not None

    callees = gq.get_callees(main)
    assert len(callees) >= 1
    targets = {c.target_name for c in callees}
    assert "greet" in targets


def test_get_imports(analyzed_project: tuple[Path, SQLiteStorage]) -> None:
    """get_imports returns what a file imports."""
    project_root, storage = analyzed_project
    gq = GraphQueries(storage, project_root)

    imports = gq.get_imports(project_root / "src" / "a.py")
    assert "src.b" in imports or "b" in imports


def test_get_importers(analyzed_project: tuple[Path, SQLiteStorage]) -> None:
    """get_importers returns what files import a given file."""
    project_root, storage = analyzed_project
    gq = GraphQueries(storage, project_root)

    # a.py is imported by b.py (from src.a import greet)
    importers = gq.get_importers(project_root / "src" / "a.py")
    assert len(importers) >= 1
    paths = [Path(p).name for p in importers]
    assert "b.py" in paths


def test_get_inheritance_tree(analyzed_project: tuple[Path, SQLiteStorage]) -> None:
    """get_inheritance_tree returns class hierarchy."""
    project_root, storage = analyzed_project
    gq = GraphQueries(storage, project_root)

    entities = storage.get_entities_by_file(
        str(project_root / "src" / "c.py")
    )
    base = next(e for e in entities if e.qualified_name == "Base")
    assert base is not None

    tree = gq.get_inheritance_tree(base)
    assert tree is not None
    assert tree.qualified_name == "Base"
    assert len(tree.children) >= 1
    child_names = [c.qualified_name for c in tree.children]
    assert "Derived" in child_names


def test_find_definition(analyzed_project: tuple[Path, SQLiteStorage]) -> None:
    """find_definition locates entities by name."""
    project_root, storage = analyzed_project
    gq = GraphQueries(storage, project_root)

    results = gq.find_definition("greet")
    assert len(results) >= 1
    assert any(e.qualified_name == "greet" for e in results)

    results = gq.find_definition("Derived")
    assert len(results) >= 1
    assert any(e.qualified_name == "Derived" for e in results)


def test_get_callers_with_entity_id(analyzed_project: tuple[Path, SQLiteStorage]) -> None:
    """get_callers accepts entity id."""
    project_root, storage = analyzed_project
    gq = GraphQueries(storage, project_root)

    entities = storage.get_entities_by_file(
        str(project_root / "src" / "a.py")
    )
    greet = next(e for e in entities if e.qualified_name == "greet")
    assert greet is not None and greet.id is not None

    callers = gq.get_callers(greet.id)
    assert isinstance(callers, list)


def test_get_callees_with_entity_id(analyzed_project: tuple[Path, SQLiteStorage]) -> None:
    """get_callees accepts entity id."""
    project_root, storage = analyzed_project
    gq = GraphQueries(storage, project_root)

    entities = storage.get_entities_by_file(
        str(project_root / "src" / "a.py")
    )
    main = next(e for e in entities if e.qualified_name == "main")
    assert main is not None and main.id is not None

    callees = gq.get_callees(main.id)
    assert isinstance(callees, list)


def test_get_inheritance_tree_with_entity_id(
    analyzed_project: tuple[Path, SQLiteStorage],
) -> None:
    """get_inheritance_tree accepts entity id."""
    project_root, storage = analyzed_project
    gq = GraphQueries(storage, project_root)

    entities = storage.get_entities_by_file(
        str(project_root / "src" / "c.py")
    )
    base = next(e for e in entities if e.qualified_name == "Base")
    assert base is not None and base.id is not None

    tree = gq.get_inheritance_tree(base.id)
    assert tree is not None
    assert tree.qualified_name == "Base"


def test_get_inheritance_tree_non_class_returns_none(
    analyzed_project: tuple[Path, SQLiteStorage],
) -> None:
    """get_inheritance_tree returns None for non-class entity."""
    project_root, storage = analyzed_project
    gq = GraphQueries(storage, project_root)

    entities = storage.get_entities_by_file(
        str(project_root / "src" / "a.py")
    )
    greet = next(e for e in entities if e.qualified_name == "greet")
    assert greet is not None

    tree = gq.get_inheritance_tree(greet)
    assert tree is None


def test_find_definition_with_scope_file(
    analyzed_project: tuple[Path, SQLiteStorage],
) -> None:
    """find_definition with scope_file prefers entities from that file."""
    project_root, storage = analyzed_project
    gq = GraphQueries(storage, project_root)

    a_path = (project_root / "src" / "a.py").resolve().as_posix()
    results = gq.find_definition("greet", scope_file=a_path)
    assert len(results) >= 1
    # When scope is a.py, greet from a.py should be first or in results
    assert any(e.file_path == a_path for e in results)
