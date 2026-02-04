"""Python-specific parser using tree-sitter."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

from .entities import CodeEntity, EntityType
from .relationships import Relationship, RelationshipType


def _get_text(node: Node, source_code: bytes) -> str:
    """Get text content of a node."""
    return source_code[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _extract_docstring_from_body(body: Node, source_code: bytes) -> Optional[str]:
    """Extract docstring from a class/function body (first string in block)."""
    if not body or not body.child_count:
        return None
    first = body.child(0)
    if first.type == "expression_statement":
        expr = first.child(0)
        if expr and expr.type == "string":
            doc = _get_text(expr, source_code)
            for q in ('"""', "'''", '"', "'"):
                doc = doc.strip(q)
            return doc.strip() or None
    return None


class PythonParser:
    """Parse Python files to extract entities and relationships."""

    def __init__(self) -> None:
        self._language = Language(tspython.language())
        self._parser = Parser(self._language)

    def parse_file(self, file_path: str) -> Tuple[List[CodeEntity], List[Relationship]]:
        """
        Parse a Python file and extract entities and relationships.

        Args:
            file_path: Absolute path to Python file (str, normalized posix).

        Returns:
            Tuple of (entities, relationships).
        """
        path = Path(file_path)
        if not path.is_file():
            return [], []
        try:
            source_code = path.read_bytes()
        except OSError:
            return [], []

        tree = self._parser.parse(source_code)
        root = tree.root_node
        if not root or root.has_error:
            return [], []

        entities: List[CodeEntity] = []
        relationships: List[Relationship] = []

        # File-level imports
        for child in root.children:
            if child.type == "import_statement":
                for rel in self._extract_import_statement(child, file_path, source_code):
                    relationships.append(rel)
            elif child.type == "import_from_statement":
                for rel in self._extract_import_from(child, file_path, source_code):
                    relationships.append(rel)

        # Top-level classes and functions
        for child in root.children:
            if child.type == "class_definition":
                class_entities, class_rels = self._extract_class(
                    child, file_path, source_code, parent_class=None
                )
                entities.extend(class_entities)
                relationships.extend(class_rels)
            elif child.type == "function_definition":
                ent, rels = self._extract_function(
                    child, file_path, source_code, parent_class=None
                )
                entities.append(ent)
                relationships.extend(rels)

        return entities, relationships

    def _extract_import_statement(
        self, node: Node, file_path: str, source_code: bytes
    ) -> List[Relationship]:
        """Extract 'import foo' or 'import foo, bar'."""
        result: List[Relationship] = []
        for child in node.children:
            if child.type == "dotted_name":
                module = _get_text(child, source_code)
                result.append(
                    Relationship(
                        relationship_type=RelationshipType.IMPORTS,
                        from_file=file_path,
                        to_file=module,
                        location=f"{file_path}:{node.start_point[0] + 1}",
                    )
                )
        return result

    def _extract_import_from(
        self, node: Node, file_path: str, source_code: bytes
    ) -> List[Relationship]:
        """Extract 'from foo import bar' - one relationship per import (module or module.name)."""
        result: List[Relationship] = []
        module_node = node.child_by_field_name("module_name")
        if not module_node:
            return result
        module = _get_text(module_node, source_code)
        # Store as single import from this file to the module
        result.append(
            Relationship(
                relationship_type=RelationshipType.IMPORTS,
                from_file=file_path,
                to_file=module,
                location=f"{file_path}:{node.start_point[0] + 1}",
            )
        )
        return result

    def _extract_class(
        self,
        node: Node,
        file_path: str,
        source_code: bytes,
        parent_class: Optional[str],
    ) -> Tuple[List[CodeEntity], List[Relationship]]:
        """Extract a class and its methods."""
        entities: List[CodeEntity] = []
        relationships: List[Relationship] = []

        name_node = node.child_by_field_name("name")
        if not name_node:
            return entities, relationships
        class_name = _get_text(name_node, source_code)
        qualified_name = f"{parent_class}.{class_name}" if parent_class else class_name

        body = node.child_by_field_name("body")
        docstring = _extract_docstring_from_body(body, source_code) if body else None

        class_entity = CodeEntity(
            file_path=file_path,
            type=EntityType.CLASS,
            name=class_name,
            qualified_name=qualified_name,
            parent_name=parent_class,
            lineno=node.start_point[0] + 1,
            end_lineno=node.end_point[0] + 1,
            docstring=docstring,
            signature=None,
            language="python",
        )
        entities.append(class_entity)

        # Base classes (inheritance)
        superclass_node = node.child_by_field_name("superclasses")
        if superclass_node:
            for i in range(superclass_node.child_count):
                base = superclass_node.child(i)
                if base.type == "identifier":
                    base_name = _get_text(base, source_code)
                    relationships.append(
                        Relationship(
                            relationship_type=RelationshipType.INHERITS,
                            from_file=file_path,
                            to_file=base_name,
                            from_entity_qualified_name=qualified_name,
                            location=f"{file_path}:{base.start_point[0] + 1}",
                        )
                    )
                elif base.type == "attribute":
                    base_name = _get_text(base, source_code)
                    relationships.append(
                        Relationship(
                            relationship_type=RelationshipType.INHERITS,
                            from_file=file_path,
                            to_file=base_name,
                            from_entity_qualified_name=qualified_name,
                            location=f"{file_path}:{base.start_point[0] + 1}",
                        )
                    )

        # Methods
        if body:
            for i in range(body.child_count):
                child = body.child(i)
                if child.type == "function_definition":
                    method_ent, method_rels = self._extract_function(
                        child, file_path, source_code, parent_class=qualified_name
                    )
                    entities.append(method_ent)
                    relationships.extend(method_rels)

        return entities, relationships

    def _extract_function(
        self,
        node: Node,
        file_path: str,
        source_code: bytes,
        parent_class: Optional[str] = None,
    ) -> Tuple[CodeEntity, List[Relationship]]:
        """Extract a function or method."""
        relationships: List[Relationship] = []

        name_node = node.child_by_field_name("name")
        if not name_node:
            func_name = "<anonymous>"
        else:
            func_name = _get_text(name_node, source_code)

        if parent_class:
            qualified_name = f"{parent_class}.{func_name}"
            entity_type = EntityType.METHOD
        else:
            qualified_name = func_name
            entity_type = EntityType.FUNCTION

        params_node = node.child_by_field_name("parameters")
        signature = _get_text(params_node, source_code) if params_node else "()"

        body = node.child_by_field_name("body")
        docstring = _extract_docstring_from_body(body, source_code) if body else None

        if body:
            for rel in self._extract_calls(
                body, file_path, source_code, caller_qualified_name=qualified_name
            ):
                relationships.append(rel)

        entity = CodeEntity(
            file_path=file_path,
            type=entity_type,
            name=func_name,
            qualified_name=qualified_name,
            parent_name=parent_class,
            lineno=node.start_point[0] + 1,
            end_lineno=node.end_point[0] + 1,
            docstring=docstring,
            signature=signature,
            language="python",
        )
        return entity, relationships

    def _extract_calls(
        self,
        body: Node,
        file_path: str,
        source_code: bytes,
        caller_qualified_name: Optional[str] = None,
    ) -> List[Relationship]:
        """Recursively collect call expressions (foo() or obj.method()) from a body node."""
        result: List[Relationship] = []

        def visit(n: Node) -> None:
            if n.type == "call":
                func_node = n.child_by_field_name("function")
                if func_node:
                    if func_node.type == "identifier":
                        called = _get_text(func_node, source_code)
                    elif func_node.type == "attribute":
                        called = _get_text(
                            func_node.child_by_field_name("attribute")
                            or func_node,
                            source_code,
                        )
                    else:
                        called = _get_text(func_node, source_code)
                    rel = Relationship(
                        relationship_type=RelationshipType.CALLS,
                        from_file=file_path,
                        to_file=called,
                        from_entity_qualified_name=caller_qualified_name,
                        location=f"{file_path}:{func_node.start_point[0] + 1}",
                    )
                    result.append(rel)
            for i in range(n.child_count):
                visit(n.child(i))

        visit(body)
        return result
