"""TypeScript/TSX parser using tree-sitter."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

from .entities import CodeEntity, EntityType
from .relationships import Relationship, RelationshipType


def _get_text(node: Node, source_code: bytes) -> str:
    """Get text content of a node."""
    return source_code[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


class TypeScriptParser:
    """Parse TypeScript/TSX files to extract entities and relationships."""

    def __init__(self, use_tsx: bool = True) -> None:
        # TSX grammar handles both .ts and .tsx
        lang_fn = tsts.language_tsx if use_tsx else tsts.language_typescript
        self._language = Language(lang_fn())
        self._parser = Parser(self._language)

    def parse_file(self, file_path: str) -> Tuple[List[CodeEntity], List[Relationship]]:
        """
        Parse a TypeScript/TSX file and extract entities and relationships.

        Args:
            file_path: Absolute path to file (str, normalized posix).

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

        for child in root.children:
            if child.type == "import_statement":
                for rel in self._extract_import(child, file_path, source_code):
                    relationships.append(rel)
            elif child.type == "export_statement":
                for ent, rels in self._extract_export_statement(
                    child, file_path, source_code
                ):
                    entities.append(ent)
                    relationships.extend(rels)
            elif child.type == "function_declaration":
                ent, rels = self._extract_function_declaration(
                    child, file_path, source_code, parent_class=None
                )
                entities.append(ent)
                relationships.extend(rels)
            elif child.type == "class_declaration":
                class_entities, class_rels = self._extract_class(
                    child, file_path, source_code, parent_class=None
                )
                entities.extend(class_entities)
                relationships.extend(class_rels)
            elif child.type == "lexical_declaration":
                for ent, rels in self._extract_lexical_declaration(
                    child, file_path, source_code
                ):
                    entities.append(ent)
                    relationships.extend(rels)

        return entities, relationships

    def _extract_export_statement(
        self, node: Node, file_path: str, source_code: bytes
    ) -> List[Tuple[CodeEntity, List[Relationship]]]:
        """Extract entities from export statement (export function/class/const)."""
        result: List[Tuple[CodeEntity, List[Relationship]]] = []
        for i in range(node.child_count):
            c = node.child(i)
            if c.type == "function_declaration":
                ent, rels = self._extract_function_declaration(
                    c, file_path, source_code, parent_class=None
                )
                result.append((ent, rels))
            elif c.type == "class_declaration":
                class_entities, class_rels = self._extract_class(
                    c, file_path, source_code, parent_class=None
                )
                for ent in class_entities:
                    rels = [
                        r
                        for r in class_rels
                        if r.from_entity_qualified_name == ent.qualified_name
                    ]
                    result.append((ent, rels))
            elif c.type == "lexical_declaration":
                result.extend(
                    self._extract_lexical_declaration(c, file_path, source_code)
                )
        return result

    def _extract_import(
        self, node: Node, file_path: str, source_code: bytes
    ) -> List[Relationship]:
        """Extract import statement - get module from 'from' string."""
        result: List[Relationship] = []
        for i in range(node.child_count):
            c = node.child(i)
            if c.type == "string":
                module = _get_text(c, source_code).strip('"\'')
                if module:
                    result.append(
                        Relationship(
                            relationship_type=RelationshipType.IMPORTS,
                            from_file=file_path,
                            to_file=module,
                            location=f"{file_path}:{node.start_point[0] + 1}",
                        )
                    )
                break
        return result

    def _extract_class(
        self,
        node: Node,
        file_path: str,
        source_code: bytes,
        parent_class: Optional[str],
    ) -> Tuple[List[CodeEntity], List[Relationship]]:
        """Extract class and its methods."""
        entities: List[CodeEntity] = []
        relationships: List[Relationship] = []

        name_node = node.child_by_field_name("name")
        if not name_node:
            return entities, relationships
        class_name = _get_text(name_node, source_code)
        qualified_name = f"{parent_class}.{class_name}" if parent_class else class_name

        class_entity = CodeEntity(
            file_path=file_path,
            type=EntityType.CLASS,
            name=class_name,
            qualified_name=qualified_name,
            parent_name=parent_class,
            lineno=node.start_point[0] + 1,
            end_lineno=node.end_point[0] + 1,
            docstring=None,
            signature=None,
            language="typescript",
        )
        entities.append(class_entity)

        superclass = node.child_by_field_name("superclass")
        if superclass:
            base_name = self._get_identifier_text(superclass, source_code)
            if base_name:
                relationships.append(
                    Relationship(
                        relationship_type=RelationshipType.INHERITS,
                        from_file=file_path,
                        to_file=base_name,
                        from_entity_qualified_name=qualified_name,
                        location=f"{file_path}:{superclass.start_point[0] + 1}",
                    )
                )

        body = node.child_by_field_name("body")
        if body:
            for i in range(body.child_count):
                child = body.child(i)
                if child.type == "method_definition":
                    method_ent, method_rels = self._extract_method_definition(
                        child, file_path, source_code, qualified_name
                    )
                    entities.append(method_ent)
                    relationships.extend(method_rels)

        return entities, relationships

    def _get_identifier_text(self, node: Node, source_code: bytes) -> str:
        """Get identifier or member_expression as qualified name."""
        if node.type == "identifier":
            return _get_text(node, source_code)
        if node.type == "member_expression":
            obj = node.child_by_field_name("object")
            prop = node.child_by_field_name("property")
            if obj and prop:
                obj_txt = self._get_identifier_text(obj, source_code)
                prop_txt = _get_text(prop, source_code)
                return f"{obj_txt}.{prop_txt}"
        return _get_text(node, source_code)

    def _extract_method_definition(
        self,
        node: Node,
        file_path: str,
        source_code: bytes,
        parent_class: str,
    ) -> Tuple[CodeEntity, List[Relationship]]:
        """Extract a class method."""
        relationships: List[Relationship] = []

        name_node = node.child_by_field_name("name")
        if not name_node:
            name_node = node.child(0)
        if not name_node:
            return (
                CodeEntity(
                    file_path=file_path,
                    type=EntityType.METHOD,
                    name="<anonymous>",
                    qualified_name=f"{parent_class}.<anonymous>",
                    parent_name=parent_class,
                    lineno=node.start_point[0] + 1,
                    end_lineno=node.end_point[0] + 1,
                    docstring=None,
                    signature="()",
                    language="typescript",
                ),
                [],
            )

        method_name = _get_text(name_node, source_code)
        qualified_name = f"{parent_class}.{method_name}"

        params_node = node.child_by_field_name("parameters")
        signature = _get_text(params_node, source_code) if params_node else "()"

        body = node.child_by_field_name("body")
        if body:
            for rel in self._extract_calls(
                body, file_path, source_code, caller_qualified_name=qualified_name
            ):
                relationships.append(rel)

        entity = CodeEntity(
            file_path=file_path,
            type=EntityType.METHOD,
            name=method_name,
            qualified_name=qualified_name,
            parent_name=parent_class,
            lineno=node.start_point[0] + 1,
            end_lineno=node.end_point[0] + 1,
            docstring=None,
            signature=signature,
            language="typescript",
        )
        return entity, relationships

    def _extract_function_declaration(
        self,
        node: Node,
        file_path: str,
        source_code: bytes,
        parent_class: Optional[str] = None,
    ) -> Tuple[CodeEntity, List[Relationship]]:
        """Extract function declaration."""
        relationships: List[Relationship] = []

        name_node = node.child_by_field_name("name")
        func_name = _get_text(name_node, source_code) if name_node else "<anonymous>"
        qualified_name = (
            f"{parent_class}.{func_name}" if parent_class else func_name
        )
        entity_type = EntityType.METHOD if parent_class else EntityType.FUNCTION

        params_node = node.child_by_field_name("parameters")
        signature = _get_text(params_node, source_code) if params_node else "()"

        body = node.child_by_field_name("body")
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
            docstring=None,
            signature=signature,
            language="typescript",
        )
        return entity, relationships

    def _extract_lexical_declaration(
        self, node: Node, file_path: str, source_code: bytes
    ) -> List[Tuple[CodeEntity, List[Relationship]]]:
        """Extract arrow functions and function expressions from const/let."""
        result: List[Tuple[CodeEntity, List[Relationship]]] = []
        decl = node.child_by_field_name("declarator")
        if not decl or decl.type != "variable_declarator":
            return result
        name_node = decl.child_by_field_name("name")
        value_node = decl.child_by_field_name("value")
        if not name_node or not value_node:
            return result
        if value_node.type not in ("arrow_function", "function"):
            return result

        func_name = _get_text(name_node, source_code)
        params_node = value_node.child_by_field_name("parameters")
        signature = _get_text(params_node, source_code) if params_node else "()"

        body = value_node.child_by_field_name("body")
        relationships: List[Relationship] = []
        if body:
            for rel in self._extract_calls(
                body, file_path, source_code, caller_qualified_name=func_name
            ):
                relationships.append(rel)

        entity = CodeEntity(
            file_path=file_path,
            type=EntityType.FUNCTION,
            name=func_name,
            qualified_name=func_name,
            parent_name=None,
            lineno=node.start_point[0] + 1,
            end_lineno=node.end_point[0] + 1,
            docstring=None,
            signature=signature,
            language="typescript",
        )
        result.append((entity, relationships))
        return result

    def _extract_calls(
        self,
        body: Node,
        file_path: str,
        source_code: bytes,
        caller_qualified_name: Optional[str] = None,
    ) -> List[Relationship]:
        """Recursively collect call expressions from a body node."""
        result: List[Relationship] = []

        def visit(n: Node) -> None:
            if n.type == "call_expression":
                func_node = n.child_by_field_name("function")
                if func_node:
                    called = self._get_called_name(func_node, source_code)
                    if called:
                        result.append(
                            Relationship(
                                relationship_type=RelationshipType.CALLS,
                                from_file=file_path,
                                to_file=called,
                                from_entity_qualified_name=caller_qualified_name,
                                location=f"{file_path}:{func_node.start_point[0] + 1}",
                            )
                        )
            for i in range(n.child_count):
                visit(n.child(i))

        visit(body)
        return result

    def _get_called_name(self, func_node: Node, source_code: bytes) -> Optional[str]:
        """Get the name of the called function."""
        if func_node.type == "identifier":
            return _get_text(func_node, source_code)
        if func_node.type == "member_expression":
            prop = func_node.child_by_field_name("property")
            if prop:
                return _get_text(prop, source_code)
        return _get_text(func_node, source_code)
