"""Graph query API: callers, callees, imports, importers, inheritance, find definition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import overload

from paranoid.analysis.entities import CodeEntity, EntityType
from paranoid.storage.sqlite import SQLiteStorage


def _normalize_path(path: Path | str) -> str:
    """Return absolute, normalized path as posix string."""
    return Path(path).resolve().as_posix()


def _file_path_to_module_name(file_path: str, project_root: Path) -> str | None:
    """
    Derive module name from file path relative to project root.

    Python: src/foo/bar.py -> src.foo.bar; foo/__init__.py -> foo
    JS/TS: src/foo/bar.js -> src.foo.bar (same convention)
    """
    path = Path(file_path).resolve()
    root = project_root.resolve()
    try:
        rel = path.relative_to(root)
    except ValueError:
        return None
    parts = list(rel.parts)
    if not parts:
        return None
    # Replace __init__.py with package name (drop the __init__ part)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    elif parts[-1].endswith((".py", ".js", ".ts", ".tsx", ".jsx")):
        parts[-1] = parts[-1].rsplit(".", 1)[0]
    if not parts:
        return None
    return ".".join(parts)


def _resolve_js_import_to_path(
    from_file: str, to_file: str, project_root: Path
) -> str | None:
    """
    Resolve a JS/TS relative import (./ or ../) to an absolute file path.

    Returns the resolved path if it can be determined, else None.
    """
    if not to_file.startswith("."):
        return None
    from_dir = Path(from_file).parent.resolve()
    root = project_root.resolve()
    try:
        resolved = (from_dir / to_file).resolve()
        resolved.relative_to(root)  # ensure under project
    except (ValueError, OSError):
        return None
    if resolved.is_file():
        return resolved.as_posix()
    for ext in (".js", ".ts", ".tsx", ".jsx"):
        candidate = resolved.with_suffix(ext)
        if candidate.is_file():
            return candidate.as_posix()
    for name in ("index.js", "index.ts", "index.tsx"):
        candidate = resolved / name
        if candidate.is_file():
            return candidate.as_posix()
    return None


@dataclass
class CallerInfo:
    """Information about a caller of an entity."""

    qualified_name: str
    file_path: str
    location: str | None


@dataclass
class CalleeInfo:
    """Information about a callee (what an entity calls)."""

    target_name: str
    file_path: str | None
    location: str | None


@dataclass
class InheritanceNode:
    """A node in the inheritance tree."""

    entity: CodeEntity | None
    qualified_name: str
    file_path: str | None
    children: list[InheritanceNode]


class GraphQueries:
    """
    High-level graph query API for code relationships.

    Requires storage with graph tables (code_entities, code_relationships)
    and project_root for module resolution.
    """

    def __init__(self, storage: SQLiteStorage, project_root: Path | str) -> None:
        self._storage = storage
        self._project_root = Path(project_root).resolve()

    def _entity_id(self, entity: CodeEntity | int) -> int | None:
        """Resolve entity to id."""
        if isinstance(entity, int):
            return entity
        return entity.id

    @overload
    def get_callers(self, entity: CodeEntity) -> list[CallerInfo]: ...
    @overload
    def get_callers(self, entity: int) -> list[CallerInfo]: ...

    def get_callers(self, entity: CodeEntity | int) -> list[CallerInfo]:
        """
        Return who calls this function/method.

        Args:
            entity: CodeEntity or entity id.

        Returns:
            List of CallerInfo (qualified_name, file_path, location).
        """
        eid = self._entity_id(entity)
        if eid is None:
            return []
        raw = self._storage.get_callers_of_entity(eid)
        return [
            CallerInfo(qualified_name=q, file_path=f, location=loc)
            for q, f, loc in raw
        ]

    @overload
    def get_callees(self, entity: CodeEntity) -> list[CalleeInfo]: ...
    @overload
    def get_callees(self, entity: int) -> list[CalleeInfo]: ...

    def get_callees(self, entity: CodeEntity | int) -> list[CalleeInfo]:
        """
        Return what this function/method calls.

        Args:
            entity: CodeEntity or entity id.

        Returns:
            List of CalleeInfo (target_name, file_path, location).
        """
        eid = self._entity_id(entity)
        if eid is None:
            return []
        raw = self._storage.get_callees_of_entity(eid)
        return [
            CalleeInfo(target_name=t, file_path=f, location=loc)
            for t, f, loc in raw
        ]

    def get_imports(self, file_path: Path | str) -> list[str]:
        """
        Return what this file imports (module names).

        Args:
            file_path: Path to the file.

        Returns:
            List of imported module names (as stored in to_file).
        """
        key = _normalize_path(file_path)
        return self._storage.get_imports_for_file(key)

    def get_importers(self, file_path: Path | str) -> list[str]:
        """
        Return what files import this file.

        Uses module resolution: derives module name from file path,
        then finds imports where to_file matches. Supports Python
        module names and JS/TS relative imports (./, ../).

        Args:
            file_path: Path to the file.

        Returns:
            List of file paths that import this file.
        """
        key = _normalize_path(file_path)
        project_root = self._project_root

        # 1. Module-name-based (Python, and JS package names)
        module_name = _file_path_to_module_name(key, project_root)
        result_set: set[str] = set()

        if module_name:
            # Query: to_file = module_name OR module_name starts with to_file.
            # (e.g. "foo.bar" matches to_file="foo" or to_file="foo.bar")
            conn = self._storage._connect()
            rows = conn.execute(
                """
                SELECT DISTINCT from_file FROM code_relationships
                WHERE relationship_type = 'imports' AND from_file IS NOT NULL
                AND to_file IS NOT NULL
                AND (to_file = ? OR ? LIKE to_file || '.%')
                """,
                (module_name, module_name),
            ).fetchall()
            for row in rows:
                if row["from_file"]:
                    result_set.add(row["from_file"])

        # 2. JS/TS relative imports: find imports that resolve to this file
        conn = self._storage._connect()
        rows = conn.execute(
            """
            SELECT from_file, to_file FROM code_relationships
            WHERE relationship_type = 'imports' AND from_file IS NOT NULL
            AND to_file IS NOT NULL AND (to_file LIKE './%' OR to_file LIKE '../%')
            """
        ).fetchall()
        for row in rows:
            resolved = _resolve_js_import_to_path(
                row["from_file"], row["to_file"], project_root
            )
            if resolved and _normalize_path(resolved) == key:
                result_set.add(row["from_file"])

        return sorted(result_set)

    def get_inheritance_tree(
        self, class_entity: CodeEntity | int
    ) -> InheritanceNode | None:
        """
        Return the inheritance tree for a class (parents and children).

        Args:
            class_entity: CodeEntity (type class) or entity id.

        Returns:
            InheritanceNode with entity, qualified_name, file_path, and
            recursive children. None if entity not found or not a class.
        """
        if isinstance(class_entity, CodeEntity):
            if class_entity.type != EntityType.CLASS:
                return None
            eid = class_entity.id
            ent = class_entity
            qname = class_entity.qualified_name
            fpath = class_entity.file_path
        else:
            eid = class_entity
            ent = self._storage.get_entity_by_id(eid)
            if ent is None or ent.type != EntityType.CLASS:
                return None
            qname = ent.qualified_name
            fpath = ent.file_path

        children_raw = self._storage.get_inheritance_children(eid)
        children = []
        for cid, cname, _ in children_raw:
            child_node = self.get_inheritance_tree(cid)
            if child_node is None:
                child_node = InheritanceNode(
                    entity=None,
                    qualified_name=cname,
                    file_path=None,
                    children=[],
                )
            children.append(child_node)

        return InheritanceNode(
            entity=ent,
            qualified_name=qname,
            file_path=fpath,
            children=children,
        )

    def find_definition(self, name: str, scope_file: str | None = None) -> list[CodeEntity]:
        """
        Locate entity/entities by name (qualified or simple).

        Args:
            name: Entity name (e.g. "User.login", "greet").
            scope_file: Optional file path to prefer definitions from this file.

        Returns:
            List of matching CodeEntity (may be multiple for overloaded names).
        """
        return self._storage.get_entities_matching_name(name, scope_file=scope_file)
