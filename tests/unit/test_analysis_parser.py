"""Unit tests for the code entity parser (Phase 5B tree-sitter)."""

from __future__ import annotations

from pathlib import Path

import pytest

from paranoid.analysis import Parser
from paranoid.analysis.entities import EntityType
from paranoid.analysis.relationships import RelationshipType


@pytest.fixture
def parser() -> Parser:
    return Parser()


def test_parser_supports_python(parser: Parser) -> None:
    assert parser.supports_language("python") is True
    assert "python" in parser.supported_languages()


def test_parser_supports_javascript_and_typescript(parser: Parser) -> None:
    assert parser.supports_language("javascript") is True
    assert parser.supports_language("typescript") is True
    assert parser.supports_language("javascript-react") is True
    assert parser.supports_language("typescript-react") is True


def test_parser_unsupported_language_raises(parser: Parser) -> None:
    with pytest.raises(ValueError, match="No parser available"):
        parser.parse_file("/nonexistent/foo.go", "go")


def test_parse_file_extracts_entities_and_relationships(parser: Parser, tmp_path: Path) -> None:
    """Parse a small Python file and assert we get expected entities and relationship types."""
    py_file = tmp_path / "sample.py"
    py_file.write_text(
        '''
"""Sample module for parser test."""
from pathlib import Path

def greet(name: str) -> str:
    """Return a greeting."""
    return f"Hello, {name}"

class Helper:
    """A helper class."""
    def run(self) -> None:
        print(greet("world"))
'''
    )
    file_path_str = py_file.resolve().as_posix()
    entities, relationships = parser.parse_file(file_path_str, "python")

    # Expected: 1 class (Helper), 1 method (run), 1 top-level function (greet)
    assert len(entities) >= 3
    types = {e.type for e in entities}
    assert EntityType.CLASS in types
    assert EntityType.FUNCTION in types
    assert EntityType.METHOD in types

    names = {e.qualified_name for e in entities}
    assert "greet" in names
    assert "Helper" in names
    assert "Helper.run" in names

    # At least one import (pathlib)
    import_rels = [r for r in relationships if r.relationship_type == RelationshipType.IMPORTS]
    assert len(import_rels) >= 1
    assert any("pathlib" in (r.to_file or "") for r in import_rels)

    # At least one call (run calls greet or print)
    call_rels = [r for r in relationships if r.relationship_type == RelationshipType.CALLS]
    assert len(call_rels) >= 1


def test_parse_file_missing_returns_empty(parser: Parser) -> None:
    entities, relationships = parser.parse_file("/nonexistent/file.py", "python")
    assert entities == []
    assert relationships == []


def test_parse_file_extracts_docstrings(parser: Parser, tmp_path: Path) -> None:
    py_file = tmp_path / "doc.py"
    py_file.write_text('def foo() -> None:\n    """The docstring."""\n    pass\n')
    file_path_str = py_file.resolve().as_posix()
    entities, _ = parser.parse_file(file_path_str, "python")
    assert len(entities) == 1
    assert entities[0].docstring == "The docstring."


def test_parse_file_calls_have_from_entity_qualified_name(parser: Parser, tmp_path: Path) -> None:
    """CALLS relationships include from_entity_qualified_name for entity-level linking."""
    py_file = tmp_path / "calls.py"
    py_file.write_text(
        '''
def greet(name: str) -> str:
    return f"Hello, {name}"

def main() -> None:
    greet("world")
'''
    )
    file_path_str = py_file.resolve().as_posix()
    _, relationships = parser.parse_file(file_path_str, "python")
    call_rels = [r for r in relationships if r.relationship_type == RelationshipType.CALLS]
    assert len(call_rels) >= 1
    main_calls_greet = next((r for r in call_rels if r.to_file == "greet"), None)
    assert main_calls_greet is not None
    assert main_calls_greet.from_entity_qualified_name == "main"


def test_parse_file_inheritance_has_from_entity_qualified_name(
    parser: Parser, tmp_path: Path
) -> None:
    """INHERITS relationships include from_entity_qualified_name for entity-level linking."""
    py_file = tmp_path / "inherit.py"
    py_file.write_text(
        '''
class Base:
    pass

class Derived(Base):
    pass
'''
    )
    file_path_str = py_file.resolve().as_posix()
    _, relationships = parser.parse_file(file_path_str, "python")
    inherits_rels = [r for r in relationships if r.relationship_type == RelationshipType.INHERITS]
    assert len(inherits_rels) >= 1
    derived_inherits_base = next((r for r in inherits_rels if r.to_file == "Base"), None)
    assert derived_inherits_base is not None
    assert derived_inherits_base.from_entity_qualified_name == "Derived"


def test_parse_js_extracts_entities_and_relationships(
    parser: Parser, tmp_path: Path
) -> None:
    """Parse JavaScript file and assert entities and relationships."""
    js_file = tmp_path / "module.js"
    js_file.write_text(
        """
import { foo } from "bar";

function greet(name) {
  return "Hello " + name;
}

class User {
  login() {
    greet("world");
  }
}
"""
    )
    file_path_str = js_file.resolve().as_posix()
    entities, relationships = parser.parse_file(file_path_str, "javascript")

    assert len(entities) >= 3
    names = {e.qualified_name for e in entities}
    assert "greet" in names
    assert "User" in names
    assert "User.login" in names

    import_rels = [r for r in relationships if r.relationship_type == RelationshipType.IMPORTS]
    assert len(import_rels) >= 1
    assert any("bar" in (r.to_file or "") for r in import_rels)

    call_rels = [r for r in relationships if r.relationship_type == RelationshipType.CALLS]
    assert len(call_rels) >= 1


def test_parse_ts_extracts_entities_and_relationships(
    parser: Parser, tmp_path: Path
) -> None:
    """Parse TypeScript file and assert entities and relationships."""
    ts_file = tmp_path / "module.ts"
    ts_file.write_text(
        """
import { config } from "./config";

function run(): void {
  config();
}

class Service {
  start(): void {
    run();
  }
}
"""
    )
    file_path_str = ts_file.resolve().as_posix()
    entities, relationships = parser.parse_file(file_path_str, "typescript")

    assert len(entities) >= 3
    names = {e.qualified_name for e in entities}
    assert "run" in names
    assert "Service" in names
    assert "Service.start" in names

    import_rels = [r for r in relationships if r.relationship_type == RelationshipType.IMPORTS]
    assert len(import_rels) >= 1

    call_rels = [r for r in relationships if r.relationship_type == RelationshipType.CALLS]
    assert len(call_rels) >= 1
